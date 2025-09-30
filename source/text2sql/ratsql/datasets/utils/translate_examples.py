import argparse
import json
from pathlib import Path

from google.cloud import translate as gc_translate
from tqdm import tqdm


class Translator():
    def __init__(self, key_path, project_id, location, src_lang, dest_lang) -> None:
        self.client = gc_translate.TranslationServiceClient.from_service_account_json(key_path)
        self.parent = f"projects/{project_id}/locations/{location}"
        self.src_lang = src_lang
        self.dest_lang = dest_lang

    def translate_one(self, text):
        response = self.client.translate_text(
            request={
                "parent": self.parent,
                "contents": [text],
                "mime_type": "text/plain",
                "source_language_code": self.src_lang,
                "target_language_code": self.dest_lang,
            }
        )
        return response.translations[0].translated_text

    def translate_list(self, text_list):
        response = self.client.translate_text(
            request={
                "parent": self.parent,
                "contents": [text_list],
                "mime_type": "text/plain",
                "source_language_code": self.src_lang,
                "target_language_code": self.dest_lang,
            }
        )
        return [translation.translated_text for translation in response.translations]    


def translate_example(example, translator):
    src_question = example["question"]

    dest_question = translator.translate_one(src_question)
    dest_question_toks = dest_question.split()

    example["question"] = dest_question
    example["question_toks"] = dest_question_toks
    example["language"] = translator.dest_lang
    example["src_question"] = src_question
    example["src_language"] = translator.src_lang

    return example


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input_dir', type=Path, default="data/spider")
    parser.add_argument('--output_dir', type=Path, default="data/spider-kor")
    parser.add_argument('--src_lang', type=str, default="en-US")
    parser.add_argument('--dest_lang', type=str, default="ko")
    parser.add_argument('--key_path', type=Path, default="/mnt/sdc/jjkim/NL2QGM/translator-332900-564039c925b0.json")
    parser.add_argument('--project_id', type=str, default="translator-332900")
    parser.add_argument('--location', type=str, default="global")
    parser.add_argument('--test_n', type=int, default=5)
    args = parser.parse_args()

    input_dir = args.input_dir
    output_dir = args.output_dir
    src_lang = args.src_lang
    dest_lang = args.dest_lang
    key_path = args.key_path
    project_id = args.project_id
    location = args.location
    test_n = args.test_n

    translator = Translator(key_path, project_id, location, src_lang, dest_lang)

    def __is_examples_file(path):
        if str(path).endswith('.json'):
            with open(path, 'r') as f:
                examples = json.load(f)
            if "question" in examples[0]:
                return True
        return False

    input_files = list(filter(__is_examples_file, list(input_dir.iterdir())))
    for input_file in tqdm(input_files):
        with open(input_file, 'r') as f:
            src_examples = json.load(f)

        dest_examples = []
        src_examples = src_examples[:test_n] if test_n else src_examples
        for src_example in tqdm(src_examples):
            dest_example = translate_example(src_example, translator)
            dest_examples.append(dest_example)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / input_file.name
        with open(output_file, 'w') as f:
            json.dump(dest_examples, f, indent=4, ensure_ascii=False)


if __name__ == '__main__':
    main()
