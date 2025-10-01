import os
import json
import hydra
import logging
import _jsonnet
from typing import List, Any
from config.path import ABS_CONFIG_DIR
from omegaconf import DictConfig
from source.utils import One_time_Preprocesser
from source.text2sql.ratsql.commands.infer import Inferer


class IntentInferer:
    """Classifies user intent (query vs database_tuning) from natural language text.

    Uses a fine-tuned encoder-decoder model to detect whether the user wants to
    execute a query or perform database tuning/administration tasks.
    """

    def __init__(self, global_cfg, cfg):
        """Initialize IntentInferer with model and preprocessor.

        Args:
            global_cfg: Global configuration with database, table, and text2sql paths
            cfg: Intent-specific configuration with model paths

        Raises:
            RuntimeError: If text2sql experiment config file does not exist
            AssertionError: If intent experiment config file does not exist
        """
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

    def infer(self, input_text: str, db_id: str) -> List[str]:
        """Infer user intent from input text.

        Args:
            input_text: User query text with <s> tokens for conversation history
            db_id: Database identifier for schema context

        Returns:
            List of predicted intent labels (e.g., ['query'] or ['database_tuning'])
        """
        model_input = self.preprocess(input_text, db_id)
        enc_features = self.model.encoder(model_input)
        logits = self.model.decoder.decoder_layers(enc_features)
        pred_ids = logits.argmax(dim=1)
        pred_labels = [self.model.decoder.output_classes[id] for id in pred_ids]
        return pred_labels

    def preprocess(self, input_text: str, db_id: str) -> List[Any]:
        """Preprocess input text for intent classification.

        Args:
            input_text: User query text with <s> separator tokens
            db_id: Database identifier for schema context

        Returns:
            List containing preprocessed item ready for model input

        Note:
            Removes leading "<s> " and replaces remaining "<s>" with "[CLS]" tokens.
        """
        input_changed = input_text[len("<s> ") :]
        input_changed = input_changed.replace("<s>", "[CLS]")
        _, preproc_item = self.preprocessor.run(input_changed, db_id)
        return [preproc_item]


@hydra.main(version_base=None, config_path=ABS_CONFIG_DIR, config_name="config")
def main(cfg: DictConfig) -> None:
    """Main function for testing intent inference."""
    inferer = IntentInferer(cfg, cfg.text2intent)
    print(inferer.infer("<s> How many concerts are there in <s>", "concert_singer"))


if __name__ == "__main__":
    main()
