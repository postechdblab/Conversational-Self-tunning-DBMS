import os
import json
import torch
import hydra
import _jsonnet
from typing import List, Dict, Any
from config.path import ABS_CONFIG_DIR
from omegaconf import DictConfig
from source.utils import token_score_to_noun_score
from source.text2sql.ratsql.commands.analysis import Attribution
from source.text2sql.ratsql.commands.infer import Inferer
from source.text2sql.text_to_sql import Text2SQL


class Text2Confidence:
    """Calculates confidence scores for SQL predictions and analyzes low-confidence queries.

    This class uses beam search scores to compute confidence and applies Captum
    attribution analysis to identify ambiguous tokens in low-confidence queries.
    """

    def __init__(self, cfg, device: str = "cuda:0"):
        """Initialize Text2Confidence with model and attribution analyzer.

        Args:
            cfg: Configuration with experiment and model checkpoint paths
            device: Device to load the model on (default: "cuda:0")

        Raises:
            RuntimeError: If experiment config file does not exist
        """
        self.cfg = cfg
        experiment_config_path = cfg.experiment_config_path
        model_ckpt_dir_path = cfg.model_ckpt_dir_path

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

        self.analyser = Attribution(model_config)

        inferer = Inferer(model_config)
        model, _ = inferer.load_model(model_ckpt_dir_path)
        model.to(device)
        self.model = model

    def calculate(self, beams: List[Any], inferred_code: str) -> float:
        """Calculate confidence score from beam search results with heuristic refinement.

        Args:
            beams: List of beam search results with scores
            inferred_code: Generated SQL query string

        Returns:
            Confidence score as percentage (0-100)

        Note:
            Applies heuristic boost (+20%) for WHERE clause queries below 70% confidence,
            as these often have valid but lower-scored alternatives.
        """
        confidence = (
            torch.softmax(torch.tensor([tmp.score for tmp in beams]), dim=0)
            .cpu()
            .numpy()[0]
        )
        if (
            "where" in inferred_code.lower()
            and "terminal" not in inferred_code.lower()
            and confidence < 0.7
        ):
            confidence = min(confidence + 0.2, 1.0)
        return confidence * 100

    def analyze(self, input_text: str, orig_item: Any, preproc_item: Any) -> Dict[str, Any]:
        """Analyze query to identify the most ambiguous token using attribution.

        Uses Captum attribution to compute word importance scores, then extracts
        the noun with the highest attribution score as the most likely source of confusion.

        Args:
            input_text: Original user query text
            orig_item: Original preprocessed item with schema information
            preproc_item: Model-ready preprocessed item

        Returns:
            Dictionary with:
                - raw_input: The most ambiguous noun word
                - word_attributions: Attribution score for that word

        Note:
            Retries up to 6 times on failure, falling back to uniform attribution.
        """
        while_cnt = 6
        while while_cnt:
            try:
                input_raw, word_attributions = self.analyser.run(
                    self.model, input_text, orig_item, preproc_item
                )
                print("input raw", input_raw)
                indices = [index for index, word in enumerate(input_raw) if word == "s"]
                if len(indices) > 1:
                    # Find the index of second s
                    index = indices[1]
                    input_raw = input_raw[: index - 1]
                    word_attributions = word_attributions[: index - 1]
                print("new input raw", input_raw)
                noun_words, noun_scores = token_score_to_noun_score(
                    tokens=input_raw[3:], token_scores=word_attributions[3:]
                )
                while_cnt = 0

            except:
                noun_words = input_text.split(" ")
                noun_scores = [0.1 for _ in range(len(noun_words))]
                noun_words, noun_scores = token_score_to_noun_score(
                    tokens=noun_words, token_scores=noun_scores
                )
                while_cnt -= 1

        print("Noun words:", noun_words)
        print("Noun scores:", noun_scores)

        # Filter only one noun word with highest score
        if noun_scores:
            highest_score = max(noun_scores)
            noun_words = [
                noun_words[idx]
                for idx, score in enumerate(noun_scores)
                if score == highest_score
            ]
            noun_scores = [highest_score]
        if len(noun_words) > 0:
            noun_word = noun_words[0]
            noun_score = noun_scores[0]
        else:
            noun_word = ""
            noun_score = 0.0

        print(noun_word, noun_score)
        analyze_result = {
            "raw_input": noun_word,
            "word_attributions": noun_score,
        }

        return analyze_result


@hydra.main(version_base=None, config_path=ABS_CONFIG_DIR, config_name="config")
def main(cfg: DictConfig) -> None:
    """Main function for testing confidence calculation and analysis."""
    translator = Text2SQL(cfg, cfg.text2sql)
    input_text = "<s> How many concerts are there in"
    orig_item, preproc_item = translator.preprocess(
        input_text,
        input_text,
        "concert_singer",
    )
    calculator = Text2Confidence(cfg.conversation.text2confidence)
    beams, inferred_code = translator.translate(
        input_text,
        input_text,
        "concert_singer",
    )
    confidence = calculator.calculate(beams, inferred_code)

    print(f"Confidence: {confidence}")
    analyze_result = {}

    if float(confidence) < 80:
        analyze_result = calculator.analyze(input_text, orig_item, preproc_item)

    print("Analyze result:", analyze_result)


if __name__ == "__main__":
    main()
