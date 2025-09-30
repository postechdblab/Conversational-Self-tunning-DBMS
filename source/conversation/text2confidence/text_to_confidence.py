import os
import json
import torch
import hydra
import _jsonnet
from config.path import ABS_CONFIG_DIR
from omegaconf import DictConfig
from source.utils import token_score_to_noun_score
from source.text2sql.ratsql.commands.analysis import Attribution
from source.text2sql.ratsql.commands.infer import Inferer
from source.text2sql.text_to_sql import Text2SQL


class Text2Confidence:
    def __init__(self, cfg, device="cuda:0"):
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

    def calculate(self, beams, inferred_code):
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

    def analyze(self, input_text, orig_item, preproc_item):
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
