import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, FunctionTransformer


def func(X, data_min=0, data_max=1):
    scale = 2 / (data_max - data_min)
    min_adj = -1 - data_min * scale
    return X * scale + min_adj


def inverse_func(X, data_min, data_max):
    # Calculate the scale factor used in the forward transformation
    scale = 2 / (data_max - data_min)
    min_adj = -1 - data_min * scale

    # Reverse the scaling transformation
    # First subtract the minimum adjustment, then divide by scale
    return (X - min_adj) / scale


class GetFeatureNamesOutFunctionTransformer(FunctionTransformer):
    def __init__(self, kw_args, func, feature_names, inverse_func):
        super().__init__(
            func=func, kw_args=kw_args, inverse_func=inverse_func, inv_kw_args=kw_args
        )
        self.feature_names = feature_names

    def get_feature_names_out(self, input_features=None):
        # Use provided feature names or fall back to input feature names
        return self.feature_names if self.feature_names else input_features


class InvertableColumnTransformer(ColumnTransformer):
    def inverse_transform(self, X):
        if isinstance(X, pd.DataFrame):
            X = X.to_numpy()

        arrays = []
        i = 0
        with open("OpAdviserPlus/categories") as f:
            for category in f:
                n = len(eval(category))
                logits = X[:, i : i + n]
                # Convert logits to probabilities using softmax
                exp_logits = np.exp(logits)
                probabilities = exp_logits / np.sum(exp_logits, axis=1, keepdims=True)

                # Convert to one-hot by taking argmax
                one_hot = np.zeros_like(probabilities)
                one_hot[np.arange(len(logits)), np.argmax(probabilities, axis=1)] = 1
                X[:, i : i + n] = one_hot
                i += n
        for name, indices in self.output_indices_.items():
            transformer = self.named_transformers_.get(name, None)
            arr = X[:, indices.start : indices.stop]

            if transformer in (None, "passthrough", "drop"):
                pass
            else:
                arr = transformer.inverse_transform(arr)
            arrays.append(arr)

        retarr = np.concatenate(arrays, axis=1)
        return retarr


def create_transformer():
    with open("scripts/experiment/gen_knobs/mysql_all_197_32G.json") as f:
        all = json.load(f)
        enum = {k: v for k, v in all.items() if v["type"] == "enum"}
        transformer = InvertableColumnTransformer(
            transformers=[
                (
                    "cat",
                    OneHotEncoder(
                        categories=list(
                            map(
                                lambda x: x["enum_values"],
                                enum.values(),
                            )
                        )
                    ),
                    list(enum.keys()),
                ),
            ]
            + [
                (
                    k,
                    GetFeatureNamesOutFunctionTransformer(
                        kw_args={
                            "data_min": v["min"],
                            "data_max": v["max"],
                        },
                        func=func,
                        feature_names=[k],
                        inverse_func=inverse_func,
                    ),
                    [k],
                )
                for k, v in {
                    k: v for k, v in all.items() if v["type"] == "integer"
                }.items()
            ],
            remainder="passthrough",
        )
        l = []
        for file_path in Path("repo").iterdir():
            with open(file_path) as f:
                for o in json.load(f)["data"]:
                    c = o["configuration"]
                    for key in all:
                        if key not in c:
                            c[key] = all[key]["default"]
                            if all[key]["type"] == "enum":
                                c[key] = str(c[key])
                    l.append(c)
        df = transformer.fit_transform(pd.DataFrame(l))
        return transformer, df


if __name__ == "__main__":
    transformer, transformed_data = create_transformer()
    transformed_data = pd.DataFrame(
        transformed_data, columns=transformer.get_feature_names_out()
    )
    transformed_data.to_csv("OpAdviserPlus/transformed.csv")
    print(transformed_data.describe())
