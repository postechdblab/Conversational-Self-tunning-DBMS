import os
import abc
import json
import hydra
import _jsonnet
import requests
from typing import Tuple, List, Any
from config.path import ABS_CONFIG_DIR
from omegaconf import DictConfig
from source.utils import One_time_Preprocesser, add_value_one_sql
from source.text2sql.ratsql.commands.infer import Inferer
from source.text2sql.ratsql.models.spider import spider_beam_search

from source.text2sql.prompt.llama import llama_prompt, llama_fix_prompt
from source.text2sql.prompt.oss import gpt_prompt, gpt_fix_prompt
from source.text2sql.prompt.qwen import qwen_prompt, qwen_fix_prompt
from source.text2sql.M_Schema.schema_engine import (
    SchemaEngine,
)
from sqlalchemy import create_engine


# abstract class
class BaseText2SQL(abc.ABC):
    @abc.abstractmethod
    def __init__(self, global_cfg, cfg, device: str = "cuda:0"):
        pass

    @abc.abstractmethod
    def translate(
        self,
    ):
        pass

    @abc.abstractmethod
    def preprocess(
        self,
    ):
        pass


class LLMBasedText2SQL(BaseText2SQL):
    def __init__(self, global_cfg, cfg):
        self.database_path = global_cfg.data.database_path
        self.llm_address = f"http://{cfg.host}:{cfg.port}/generate"
        self.max_new_tokens = cfg.max_new_tokens
        self.temperature = cfg.temperature
        if cfg.model_type == "llama":
            self.prompt_template = llama_prompt
            self.prompt_template_fix = llama_fix_prompt
        elif cfg.model_type == "qwen":
            self.prompt_template = qwen_prompt
            self.prompt_template_fix = qwen_fix_prompt
        else:  # default to gpt
            self.prompt_template = gpt_prompt
            self.prompt_template_fix = gpt_fix_prompt
        self.is_fix_mode = cfg.is_fix_mode
        if self.is_fix_mode:
            self.slm_translator = Text2SQL(global_cfg, cfg)

    def translate(
        self, text: str, text_history: str, db_id: str
    ) -> Tuple[List[Any], str]:

        # Load database schema
        sqlite_path = f"{self.database_path}/{db_id}/{db_id}.sqlite"
        db_engine = create_engine(f"sqlite:///{sqlite_path}")
        schema_engine = SchemaEngine(engine=db_engine, db_name=db_id)
        mschema = schema_engine.mschema
        mschema_str = mschema.to_mschema()
        original_inferred_code = None
        beams = []
        if self.is_fix_mode:
            beams, original_inferred_code = self.slm_translator.translate(
                text,
                text_history,
                db_id,
            )

        # Prepare prompts
        prompt = self.preprocess(
            text,
            text_history,
            mschema_str,
            db_engine.dialect.name,
            original_inferred_code,
        )

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
        inferred_code = self.postprocess(response_list[0]["text"])

        return beams, inferred_code

    def preprocess(
        self,
        text,
        text_history,
        mschema_str,
        dialect="SQLite",
        original_inferred_code=None,
    ):
        if self.is_fix_mode:
            return self.prompt_template_fix.format(
                dialect=dialect,
                db_schema=mschema_str,
                history=text_history,
                question=text,
                original_sql=original_inferred_code,
            )
        else:
            return self.prompt_template.format(
                dialect=dialect,
                db_schema=mschema_str,
                history=text_history,
                question=text,
            )

    def postprocess(self, response_text):
        # extract sql from response_text
        if "```" in response_text:
            inferred_code = (
                response_text.split("```")[0]
                .strip()
                .replace("\n", " ")
                .replace("  ", " ")
                .replace(";", "")
            )
        else:
            inferred_code = response_text.strip()
        return inferred_code


class Text2SQL(BaseText2SQL):
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
        self.db_path = db_path
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
            question=text,
            db_name=db_id,
            sql=inferred_code,
            history=text_history,
            is_postgresql=self.cfg.is_postgresql,
            database_path=self.db_path,
        )

        return beams, inferred_code

    def preprocess(self, text: str, text_history: str, db_id: str) -> Tuple[Any, Any]:
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
