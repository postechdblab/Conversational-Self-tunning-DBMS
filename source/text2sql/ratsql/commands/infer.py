import argparse
import itertools
import json
import os
import sys

import _jsonnet
import torch
import tqdm
import pickle

# These imports are needed for registry.lookup
# noinspection PyUnresolvedReferences
from source.text2sql.ratsql import beam_search

# noinspection PyUnresolvedReferences
from source.text2sql.ratsql import datasets

# noinspection PyUnresolvedReferences
from source.text2sql.ratsql import grammars

# noinspection PyUnresolvedReferences
from source.text2sql.ratsql import models

# noinspection PyUnresolvedReferences
from source.text2sql.ratsql import optimizers
from source.text2sql.ratsql.models.spider import spider_beam_search
from source.text2sql.ratsql.utils import registry
from source.text2sql.ratsql.utils import saver as saver_mod
from source.text2sql.ratsql.utils.relation_names import RELATION_NAMES
from torch.utils.tensorboard import SummaryWriter


class Inferer:
    def __init__(self, config, model_dir=None):
        self.config = config
        if torch.cuda.is_available():
            self.device = torch.device("cuda")
        else:
            self.device = torch.device("cpu")
            torch.set_num_threads(1)

        # 0. Construct preprocessors
        self.model_preproc = registry.instantiate(
            registry.lookup("model", config["model"]).Preproc, config["model"]
        )
        self.model_preproc.load(saver_mod.get_model_ckpt_path(model_dir))

    def filter_examples(self, orig_data, preproc_data):
        tmp = []
        preproc_idx = 0
        for idx, item in enumerate(orig_data.examples):
            target_component = preproc_data.components[0][preproc_idx]
            if (
                item.orig["question"] == target_component["raw_question"]
                and item.orig["db_id"] == target_component["db_id"]
            ):
                tmp.append(item)
                preproc_idx += 1
            if preproc_idx == len(preproc_data.components[0]):
                break

        assert len(tmp) == len(preproc_data.components[0])
        orig_data.examples = tmp
        return orig_data

    def load_model(self, logdir, step=None):
        """Load a model (identified by the config used for construction) and return it"""
        # 0. Load model preproc
        if step:
            self.model_preproc.load(f"{logdir}/model_checkpoint-{step:06d}.pt")
        elif os.path.isfile(f"{logdir}/best_model.pt"):
            self.model_preproc.load(f"{logdir}/best_model.pt")

        # 1. Construct model
        model = registry.construct(
            "model",
            self.config["model"],
            preproc=self.model_preproc,
            device=self.device,
        )
        model.to(self.device)
        model.eval()

        # 2. Restore its parameters
        saver = saver_mod.Saver({"model": model}, logdir)
        last_step = saver.restore(
            step=step, map_location=self.device, item_keys=["model"]
        )
        if last_step:
            print(f"loaded model has last_step:{last_step}")
        else:
            raise Exception(
                f"Attempting to infer on untrained model in {logdir}, step={step}"
            )

        return model, last_step

    def filter_examples(self, orig_data, preproc_data):
        tmp = []
        preproc_idx = 0
        for idx, item in enumerate(orig_data.examples):
            target_component = preproc_data.components[0][preproc_idx]
            if (
                item.orig["question"] == target_component["raw_question"]
                and item.orig["db_id"] == target_component["db_id"]
            ):
                tmp.append(item)
                preproc_idx += 1
            if preproc_idx == len(preproc_data.components[0]):
                break

        assert len(tmp) == len(preproc_data.components[0])
        orig_data.examples = tmp
        return orig_data

    def infer(self, model, output_path, args):
        output = open(output_path, "w")

        with torch.no_grad():
            if args.mode == "infer":
                orig_data = registry.construct(
                    "dataset", self.config["data"][args.section]
                )
                preproc_data = self.model_preproc.dataset(args.section)

                # orig_data = self.filter_examples(orig_data, preproc_data)
                if args.limit:
                    sliced_orig_data = itertools.islice(orig_data, args.limit)
                    sliced_preproc_data = itertools.islice(preproc_data, args.limit)
                else:
                    sliced_orig_data = orig_data
                    sliced_preproc_data = preproc_data
                assert len(orig_data) == len(preproc_data)
                self._inner_infer(
                    model,
                    args.beam_size,
                    args.output_history,
                    sliced_orig_data,
                    sliced_preproc_data,
                    output,
                    args.use_heuristic,
                )
            elif args.mode == "debug":
                data = self.model_preproc.dataset(args.section)
                if args.limit:
                    sliced_data = itertools.islice(data, args.limit)
                else:
                    sliced_data = data
                self._debug(model, sliced_data, output)

    def _inner_infer(
        self,
        model,
        beam_size,
        output_history,
        sliced_orig_data,
        sliced_preproc_data,
        output,
        use_heuristic=True,
    ):

        for i, (orig_item, preproc_item) in enumerate(
            tqdm.tqdm(
                zip(sliced_orig_data, sliced_preproc_data), total=len(sliced_orig_data)
            )
        ):
            decoded = self._infer_one(
                model, orig_item, preproc_item, beam_size, output_history, use_heuristic
            )
            output.write(
                json.dumps(
                    {
                        "index": i,
                        "question": preproc_item[0]["raw_question"],
                        "question_toks": preproc_item[0]["question"],
                        "schema": {
                            "columns": preproc_item[0]["columns"],
                            "tables": preproc_item[0]["tables"],
                            "tables_bounds": preproc_item[0]["table_bounds"],
                            "table_to_columns": preproc_item[0]["table_to_columns"],
                            "colmn_to_table": preproc_item[0]["column_to_table"],
                            "primary_keys": preproc_item[0]["primary_keys"],
                            "foreign_keys": preproc_item[0]["foreign_keys"],
                            "foreign_keys_tables": preproc_item[0][
                                "foreign_keys_tables"
                            ],
                        },
                        "sc_link": preproc_item[0]["sc_link"],
                        "cv_link": preproc_item[0]["cv_link"],
                        "db_id": orig_item.schema.db_id,
                        "beams": decoded,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            output.flush()

    def _infer_one(
        self,
        model,
        data_item,
        preproc_item,
        beam_size,
        output_history=False,
        use_heuristic=True,
    ):
        if use_heuristic:
            # TODO: from_cond should be true from non-bert model
            beams = spider_beam_search.beam_search_with_heuristics(
                model,
                data_item,
                preproc_item,
                beam_size=beam_size,
                max_steps=1000,
                from_cond=model.preproc.dec_preproc.grammar.infer_from_conditions,
            )
        else:
            beams = beam_search.beam_search(
                model, data_item, preproc_item, beam_size=beam_size, max_steps=1000
            )
        decoded = []
        confidences = (
            torch.softmax(torch.tensor([tmp.score for tmp in beams]), dim=0)
            .cpu()
            .numpy()
        )
        for idx, beam in enumerate(beams):
            model_output, inferred_code = beam.inference_state.finalize(
                not self.config["model"]["decoder_preproc"]["grammar"][
                    "infer_from_conditions"
                ],
                data_item.text,
                model.decoder.get_value_vocabs(),
                data_item.schema,
            )
            decoded.append(
                {
                    "model_output": model_output,
                    "inferred_code": inferred_code,
                    "score": beam.score,
                    "confidence": float(confidences[idx]),
                    **(
                        {
                            "choice_history": beam.choice_history,
                            "score_history": beam.score_history,
                        }
                        if output_history
                        else {}
                    ),
                }
            )
        return decoded

    def _debug(self, model, sliced_data, output):
        return_dics = []
        for i, item in enumerate(tqdm.tqdm(sliced_data)):

            try:
                _, history, return_dic = model.compute_loss([item], debug=True)[0]
            except:
                print(f"Error in {i}-th item when running for caching debug info")
                history = []
            return_dics.append(return_dic)

            output.write(
                json.dumps(
                    {
                        "index": i,
                        "history": history,
                    }
                )
                + "\n"
            )
            output.flush()

        # Save all
        file_name = output.name.replace(".jsonl", ".pkl")
        with open(file_name, "wb") as f:
            pickle.dump(return_dics, f)
        print("Before summary writer...")
        # # Tensorboard projector
        # writer = SummaryWriter('tmps/test_1')
        # for key, value in return_dics[0].items():
        #     if '_relation_' in key:
        #         writer.add_embedding(value, RELATION_NAMES, tag=key)
        # print("Done writing summary!")


def add_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--logdir", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--config-args")
    parser.add_argument("--step", type=int)
    parser.add_argument("--section", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--beam-size", required=True, type=int)
    parser.add_argument("--output-history", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--mode", default="infer", choices=["infer", "debug"])
    parser.add_argument("--use_heuristic", action="store_true")
    args = parser.parse_args()
    return args


def main(args):
    if args.config_args:
        config = json.loads(
            _jsonnet.evaluate_file(args.config, tla_codes={"args": args.config_args})
        )
    else:
        config = json.loads(_jsonnet.evaluate_file(args.config))

    if "model_name" in config:
        args.logdir = os.path.join(args.logdir, config["model_name"])

    output_path = args.output.replace("__LOGDIR__", args.logdir)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    # if os.path.exists(output_path):
    #    print(f'Output file {output_path} already exists')
    #    sys.exit(1)

    inferer = Inferer(config, model_dir=args.logdir)
    model, _ = inferer.load_model(args.logdir, args.step)
    inferer.infer(model, output_path, args)


if __name__ == "__main__":
    args = add_parser()
    main(args)
