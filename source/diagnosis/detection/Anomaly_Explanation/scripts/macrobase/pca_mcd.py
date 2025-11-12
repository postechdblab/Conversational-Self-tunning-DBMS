import argparse
import os
import pickle
import warnings

import numpy as np
from sklearn.covariance import MinCovDet
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from src.data_factory.dataset.dbsherlock import DBSherlockDataset
warnings.filterwarnings("ignore")


def get_accuracy(gt, pred):
    anomaly_state = False
    for i in range(len(gt)):
        if gt[i] == 1 and pred[i] == 1 and not anomaly_state:
            anomaly_state = True
            for j in range(i, 0, -1):
                if gt[j] == 0:
                    break
                else:
                    if pred[j] == 0:
                        pred[j] = 1
            for j in range(i, len(gt)):
                if gt[j] == 0:
                    break
                else:
                    if pred[j] == 0:
                        pred[j] = 1
        elif gt[i] == 0:
            anomaly_state = False
        if anomaly_state:
            pred[i] = 1
    pred = np.array(pred)
    gt = np.array(gt)
    from sklearn.metrics import accuracy_score, precision_recall_fscore_support

    accuracy = accuracy_score(gt, pred)
    precision, recall, f_score, support = precision_recall_fscore_support(
        gt, pred, average="binary"
    )
    return accuracy, precision, recall, f_score


def feature_extraction_with_pca(data, top_n=1):
    pca = PCA(n_components=top_n)
    pca.fit(data)
    component_weights = pca.components_[0]
    top_indicies = np.argsort(np.abs(component_weights))[-top_n:][::-1].tolist()
    return top_indicies


def normalize(dataset):
    return (dataset - np.min(dataset)) / (np.max(dataset) - np.min(dataset))

def load_dataset(data_path):
    dataset = DBSherlockDataset(data_path, 25, 25)
    dataset_dict = {}
    scaler = StandardScaler()
    for partition in ["train", "val", "test"]:
        length_list = []
        all_data = []
        label = []
        if partition == "train":
            dataset_loader = dataset.train_data_list
        elif partition == "val":
            dataset_loader = dataset.val_data_list
        else:
            dataset_loader = dataset.test_data_list
        for i in range(len(dataset_loader)):
            data = dataset_loader[i]
            all_data.extend(data.valid_values)
            length_list.append(len(data.valid_values))
            label.extend([1 if id in data.abnormal_regions else 0 for id, value in enumerate(data.valid_values)])
        dataset_dict[partition] = np.array(normalize(all_data))
        dataset_dict[partition + '_length'] = np.array(length_list)
        dataset_dict[partition + '_label'] = np.array(label)
    return dataset_dict

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data_path", type=str, default="dataset/dbsherlock/converted/tpcc_500w_test.json"
    )
    parser.add_argument("--dim", default=15)
    parser.add_argument("--find_best", default=True)
    parser.add_argument("--feature_extraction", default=True)
    return parser.parse_args()


if __name__ == "__main__":
    np.random.seed(300)
    args = parse_args()
    dim = args.dim
    data_path = args.data_path
    feature_extraction = args.feature_extraction
    dataset_dict = load_dataset(data_path)
    pca = PCA(n_components=dim)
    train_data_pca = pca.fit_transform(dataset_dict["train"])
    
    
    # if feature_extraction:
    #     top_idx = feature_extraction_with_pca(dataset_dict["test"], dim)
    #     principal_components = dataset_dict["test"][:, top_idx]
    # else:
    #     principal_components = dataset_dict["test"]

    try:
        mcd_train = MinCovDet(support_fraction=1).fit(train_data_pca)
    except:
        pass

    if args.find_best:
        principal_components_val = pca.transform(dataset_dict["val"])
        distances = mcd_train.mahalanobis(
            principal_components_val - mcd_train.location_
        ) ** (0.5)
        distances_with_idx = list(zip(range(0, len(distances)), distances))
        best_f1 = 0
        best_percentile = None
        for percentile in range(101):
            pctile_cutoff = np.percentile(distances_with_idx, percentile)
            filtered_distances = (distances.tolist() > pctile_cutoff).astype(int)
            accuracy, precision, recall, f_score = get_accuracy(
                dataset_dict["val_label"], filtered_distances.tolist()
            )
            if f_score >= best_f1:
                best_f1 = f_score
                best_percentile = percentile
                best_recall = recall
                best_precision = precision
        percentile = best_percentile
    else:
        percentile = 99
    principal_components_test = pca.transform(dataset_dict["test"])
    distances = mcd_train.mahalanobis(principal_components_test - mcd_train.location_) ** (0.5)
    distances_with_idx = list(zip(range(0, len(distances)), distances))
    pctile_cutoff = np.percentile(distances_with_idx, percentile)
    filtered_distances = (distances.tolist() > pctile_cutoff).astype(int)
    accuracy, precision, recall, f_score = get_accuracy(
        dataset_dict["test_label"], filtered_distances.tolist()
    )

    print(f"dim: {dim}")
    print(f"accuracy for that: {accuracy}")
    print(f"percentile for that: {percentile}")
    print(f"recall score: {recall}")
    print(f"precision score: {precision}")
    print(f"f1 score: {f_score}")
