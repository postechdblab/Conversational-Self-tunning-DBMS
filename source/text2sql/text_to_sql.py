import os
import json
import hydra
import _jsonnet
from typing import Tuple, List, Any
from config.path import ABS_CONFIG_DIR
from omegaconf import DictConfig
from source.utils import One_time_Preprocesser, add_value_one_sql
from source.text2sql.ratsql.commands.infer import Inferer
from source.text2sql.ratsql.models.spider import spider_beam_search


class Text2SQL:
    """Translates natural language text to SQL queries using RAT-SQL model with beam search.

    This class handles the complete text-to-SQL pipeline including preprocessing,
    model inference, and post-processing with value filling.
    """

    def __init__(self, global_cfg, cfg, device: str = "cuda:0"):
        """Initialize Text2SQL translator with model and preprocessor.

        Args:
            global_cfg: Global configuration containing database and table paths
            cfg: Text2SQL-specific configuration with model paths and beam search params
            device: Device to load the model on (default: "cuda:0")

        Raises:
            RuntimeError: If experiment config file does not exist
        """
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

    def translate(
        self, text: str, text_history: str, db_id: str
    ) -> Tuple[List[Any], str]:
        """Translate natural language text to SQL query.

        Args:
            text: Current user query text
            text_history: Conversation history with previous queries
            db_id: Database identifier for schema context

        Returns:
            Tuple containing:
                - beams: List of beam search results with scores
                - inferred_code: Generated SQL query string with values filled
        """
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

    def preprocess(
        self, text: str, text_history: str, db_id: str
    ) -> Tuple[Any, Any]:
        """Preprocess input text with conversation history for model inference.

        Args:
            text: Current user query text
            text_history: Conversation history with previous queries
            db_id: Database identifier for schema context

        Returns:
            Tuple containing:
                - orig_item: Original preprocessed item with schema information
                - preproc_item: Model-ready preprocessed item with encoded features
        """
        input_text = "<s> " + text + text_history
        orig_item, preproc_item = self.preprocessor.run(input_text, db_id)
        return orig_item, preproc_item


@hydra.main(version_base=None, config_path=ABS_CONFIG_DIR, config_name="config")
def main(cfg: DictConfig) -> None:
    """Main function for testing Text2SQL translation."""
    translator = Text2SQL(cfg, cfg.text2sql)
    _, inferred_code = translator.translate(
        "<s> How many concerts are there in",
        "<s> How many concerts are there in",
        "concert_singer",
    )

    print(inferred_code)


if __name__ == "__main__":
    main()
