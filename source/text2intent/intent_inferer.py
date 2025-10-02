import os
import re
import json
import hydra
import requests
import _jsonnet
from typing import List, Any, Dict
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
        self.tune_check_example_num = cfg.tune_check_example_num
        self.llm_address = f"http://{cfg.host}:{cfg.port}/generate"
        self.max_new_tokens = cfg.max_new_tokens
        self.temperature = cfg.temperature

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

    @property
    def tune_check_instruction(self) -> str:
        return """
                <|begin_of_text|><|start_header_id|>system<|end_header_id|>
                Using f_tune() API, return True to detect when an user message involves performing tuning operations on the database. 
                Strictly follow the format of the below examples. 

                {few_shot_examples}

                <|eot_id|><|start_header_id|>user<|end_header_id|>
                user: {question}
                intent: <|eot_id|><|start_header_id|>assistant<|end_header_id|>
                """

    @property
    def tune_check_few_shot_examples(self) -> List[Dict]:
        return [
            """
                user: Please tune the database.
                intent: f_tune([True])
                """,
            """
                user: Find the name of concerts happened in the years of both 2014 and 2015
                intent: f_tune([False])
                """,
            """
                user: Enhance the database's performance.
                intent: f_tune([True])
                """,
            """
                user: Show all stadiums
                intent: f_tune([False])
                """,
            """
                user: Only name and capacity
                intent: f_tune([False])
                """,
            """
                user: Optimize the database.
                intent: f_tune([True])
                """,
        ]

    def tune_check_prompt_generate(self, input_text):
        return self.tune_check_instruction.format(
            question=input_text,
            few_shot_examples="\n\n".join(
                self.tune_check_few_shot_examples[: self.tune_check_example_num]
            ),
        )

    def infer(self, input_text: str, db_id: str, is_tune_check=False) -> List[str]:
        """Infer user intent from input text.

        Args:
            input_text: User query text with <s> tokens for conversation history
            db_id: Database identifier for schema context

        Returns:
            List of predicted intent labels (e.g., ['query'] or ['database_tuning'])
        """
        if is_tune_check:
            # generate prompt
            prompt = self.tune_check_prompt_generate(input_text)

            # send request to llm
            response_list = requests.post(
                self.llm_address,
                json={
                    "text": [prompt],
                    "sampling_params": {
                        "max_new_tokens": self.max_new_tokens,
                        "temperature": self.temperature,
                    },
                },
                timeout=None,
            ).json()
            tune_check_result = response_list[0]["text"]
            is_tune = self.tune_check_preprocess(tune_check_result)
            return [is_tune]

        else:
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

    def tune_check_preprocess(self, input_text: str) -> List[Any]:
        # parse response
        pattern_col = r"f_tune\(\[(.*?)\]\)"

        try:
            pred = re.findall(pattern_col, input_text, re.S)[0].strip()
        except:
            return False

        if "true" == pred.lower():
            return True
        else:
            return False


@hydra.main(version_base=None, config_path=ABS_CONFIG_DIR, config_name="config")
def main(cfg: DictConfig) -> None:
    """Main function for testing intent inference."""
    inferer = IntentInferer(cfg, cfg.text2intent)
    print(inferer.infer("<s> How many concerts are there in <s>", "concert_singer"))


if __name__ == "__main__":
    main()
