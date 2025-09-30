import os
import json
import hydra
import logging
import _jsonnet
from config.path import ABS_CONFIG_DIR
from omegaconf import DictConfig
from source.utils import One_time_Preprocesser
from source.text2sql.ratsql.commands.infer import Inferer


class IntentInferer:
    def __init__(self, global_cfg, cfg):
        intent_experiment_config_path = cfg.experiment_config_path
        intent_model_ckpt_dir_path = cfg.model_ckpt_dir_path
        text2sql_experiment_config_path = global_cfg.text2sql.experiment_config_path
        text2sql_model_ckpt_dir_path = global_cfg.text2sql.model_ckpt_dir_path
        db_path = global_cfg.data.database_path
        table_path = global_cfg.data.table_path

        if os.path.isfile(intent_experiment_config_path):
            exp_config = json.loads(
                _jsonnet.evaluate_file(intent_experiment_config_path)
            )
            intent_model_config_file = exp_config["model_config"]
            intent_model_config_args = exp_config["model_config_args"]
            intent_model_config = json.loads(
                _jsonnet.evaluate_file(
                    intent_model_config_file,
                    tla_codes={"args": json.dumps(intent_model_config_args)},
                )
            )
        else:
            assert "config file does not exist"

        if os.path.isfile(text2sql_experiment_config_path):
            exp_config = json.loads(
                _jsonnet.evaluate_file(text2sql_experiment_config_path)
            )
            text2sql_model_config_file = exp_config["model_config"]
            text2sql_model_config_args = exp_config["model_config_args"]
            text2sql_model_config = json.loads(
                _jsonnet.evaluate_file(
                    text2sql_model_config_file,
                    tla_codes={"args": json.dumps(text2sql_model_config_args)},
                )
            )
            text2sql_model_config["model"]["encoder_preproc"][
                "save_path"
            ] = text2sql_model_ckpt_dir_path
            text2sql_model_config["model"]["decoder_preproc"][
                "save_path"
            ] = text2sql_model_ckpt_dir_path
        else:
            raise RuntimeError(
                f"config file does not exist: {text2sql_experiment_config_path}"
            )

        self.preprocessor = One_time_Preprocesser(
            db_path, table_path, text2sql_model_config["model"]["encoder_preproc"]
        )

        inferer = Inferer(intent_model_config)
        self.model, _ = inferer.load_model(intent_model_ckpt_dir_path)

    def infer(self, input_text, db_id):
        model_input = self.preprocess(input_text, db_id)
        enc_features = self.model.encoder(model_input)
        logits = self.model.decoder.decoder_layers(enc_features)
        pred_ids = logits.argmax(dim=1)
        pred_labels = [self.model.decoder.output_classes[id] for id in pred_ids]
        return pred_labels

    def preprocess(self, input_text, db_id):
        input_changed = input_text[len("<s> ") :]
        input_changed = input_changed.replace("<s>", "[CLS]")
        _, preproc_item = self.preprocessor.run(input_changed, db_id)
        return [preproc_item]


@hydra.main(version_base=None, config_path=ABS_CONFIG_DIR, config_name="config")
def main(cfg: DictConfig) -> None:
    inferer = IntentInferer(cfg, cfg.text2intent)
    print(inferer.infer("<s> How many concerts are there in <s>", "concert_singer"))


if __name__ == "__main__":
    main()
