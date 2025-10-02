import argparse
import json

import _jsonnet
import tqdm
import os

# These imports are needed for registry.lookup
# noinspection PyUnresolvedReferences
from source.text2sql.ratsql import datasets

# noinspection PyUnresolvedReferences
from source.text2sql.ratsql import grammars

# noinspection PyUnresolvedReferences
from source.text2sql.ratsql import models

# noinspection PyUnresolvedReferences
from source.text2sql.ratsql.utils import registry

# noinspection PyUnresolvedReferences
from source.text2sql.ratsql.utils import vocab


class Preprocessor:
    def __init__(self, config):
        self.config = config
        self.model_preproc = registry.instantiate(
            registry.lookup("model", config["model"]).Preproc, config["model"]
        )

    def preprocess(self):
        def load_cache(path, is_toy=False):
            cache = {}
            if os.path.isfile(path):
                with open(path, "r") as f:
                    cnt = 0
                    for line in tqdm.tqdm(f.readlines()):
                        if is_toy and cnt > 100:
                            break
                        tmp = json.loads(line)
                        if any(key in cache for key in tmp.keys()):
                            print("already exist")
                        else:
                            cache.update(tmp)
                        cnt += 1
            return cache

        def write_cache(path, data):
            with open(path, "a") as f:
                f.write(json.dumps(data, ensure_ascii=False) + "\n")

        self.model_preproc.clear_items()
        sections = [item for item in self.config["data"].keys()]
        if "test" in sections:
            sections.remove("test")
            sections.append("test")
        for section in sections:
            data = registry.construct("dataset", self.config["data"][section])
            # Load Cache (TODO: call it outside the loop)
            cache = load_cache(data.cache_path)
            for idx, item in enumerate(
                tqdm.tqdm(data, desc=f"{section} section", dynamic_ncols=True)
            ):
                """jjkim - Sep 30, 2021
                validate_item checks whether len(item) > bert max token length
                but after preprocessing, the length can be changed,
                so I execute validate_item at the end of add_item.
                """
                # Use cached data if possible
                key = f"<db_id>:[{item.schema.db_id}]<text>:{item.text}<query>:[{item.orig['query']}]"
                if key in cache:
                    redo_decoder_preproc = True
                    if redo_decoder_preproc:
                        dec_result, dec_info = (
                            self.model_preproc.dec_preproc.validate_item(item, section)
                        )
                        dec_preproc = (dec_info, item.code)
                        cached_enc_preproc, cached_dec_preproc = cache[key]
                        self.model_preproc.add_item_from_cache(
                            (cached_enc_preproc, dec_preproc), section
                        )
                    else:
                        self.model_preproc.add_item_from_cache(cache[key], section)
                else:
                    to_add, validation_info = self.model_preproc.validate_item(
                        item, section
                    )
                    if to_add:
                        is_added, enc_dec_preproc_item = self.model_preproc.add_item(
                            item, section, validation_info
                        )
                        if is_added:
                            # Save cache
                            write_cache(data.cache_path, {key: enc_dec_preproc_item})
                    if not to_add or not is_added:
                        print(f"Skipping... section:{section} idx:{idx}")
        self.model_preproc.save()


def add_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--config-args")
    args = parser.parse_args()
    return args


def main(args):
    if args.config_args:
        config = json.loads(
            _jsonnet.evaluate_file(args.config, tla_codes={"args": args.config_args})
        )
    else:
        config = json.loads(_jsonnet.evaluate_file(args.config))

    preprocessor = Preprocessor(config)
    preprocessor.preprocess()


if __name__ == "__main__":
    args = add_parser()
    main(args)
