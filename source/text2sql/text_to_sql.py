import os
import json
import hydra
import _jsonnet
from config.path import ABS_CONFIG_DIR
from omegaconf import DictConfig
from source.utils import One_time_Preprocesser, add_value_one_sql
from source.text2sql.ratsql.commands.infer import Inferer
from source.text2sql.ratsql.models.spider import spider_beam_search


class Text2SQL:
    def __init__(self, global_cfg, cfg, device="cuda:0"):
        self.cfg = cfg
        experiment_config_path = cfg.experiment_config_path
        model_ckpt_dir_path = cfg.model_ckpt_dir_path
        db_path = global_cfg.data.database_path
        table_path = global_cfg.data.table_path

        if os.path.isfile(experiment_config_path):
            exp_config = json.loads(_jsonnet.evaluate_file(experiment_config_path))
            model_config_file = exp_config["model_config"]
            model_config_args = exp_config["model_config_args"]
            model_config = json.loads(
                _jsonnet.evaluate_file(
                    model_config_file,
                    tla_codes={"args": json.dumps(model_config_args)},
                )
            )
            model_config["model"]["encoder_preproc"]["save_path"] = model_ckpt_dir_path
            model_config["model"]["decoder_preproc"]["save_path"] = model_ckpt_dir_path
        else:
            raise RuntimeError(f"config file does not exist: {experiment_config_path}")

        self.preprocessor = One_time_Preprocesser(
            db_path, table_path, model_config["model"]["encoder_preproc"]
        )

        inferer = Inferer(model_config)
        model, _ = inferer.load_model(model_ckpt_dir_path)
        model.to(device)
        self.model = model

    def translate(self, text, text_history, db_id):
        orig_item, preproc_item = self.preprocess(text, text_history, db_id)
        if not text_history.endswith(text):
            text_history += " <s> " + text

        beams = spider_beam_search.beam_search_with_heuristics(
            self.model,
            orig_item,
            (preproc_item, None),
            beam_size=self.cfg.beam_size,
            max_steps=self.cfg.max_steps,
        )

        _, inferred_code = beams[0].inference_state.finalize()

        inferred_code = add_value_one_sql(
            question=text, db_name=db_id, sql=inferred_code, history=text_history
        )

        return beams, inferred_code

    def preprocess(self, text, text_history, db_id):
        input_text = "<s> " + text + text_history
        orig_item, preproc_item = self.preprocessor.run(input_text, db_id)
        return orig_item, preproc_item


@hydra.main(version_base=None, config_path=ABS_CONFIG_DIR, config_name="config")
def main(cfg: DictConfig) -> None:
    translator = Text2SQL(cfg, cfg.text2sql)
    _, inferred_code = translator.translate(
        "<s> How many concerts are there in",
        "<s> How many concerts are there in",
        "concert_singer",
    )

    print(inferred_code)


if __name__ == "__main__":
    main()
