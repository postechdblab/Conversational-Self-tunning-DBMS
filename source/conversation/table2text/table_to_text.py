import hydra
import logging
import requests
from config.path import ABS_CONFIG_DIR
from omegaconf import DictConfig
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class Table2Text:
    """Converts database query result tables to natural language summaries using LLM."""

    def __init__(self, cfg):
        """Initialize Table2Text with configuration.

        Args:
            cfg: Configuration object with host, port, max_new_tokens, and temperature
        """
        self.api_address = f"http://{cfg.host}:{cfg.port}"
        self.max_new_tokens = cfg.max_new_tokens
        self.temperature = cfg.temperature

    @property
    def instruction(self) -> str:
        """Returns the system instruction for the LLM."""
        return "Summarize the given table into one sentence. Do not include extra information."

    @property
    def few_shot_examples(self) -> List[Dict]:
        """Returns few-shot examples for in-context learning."""
        return [
            {
                "table": [
                    {
                        "singer_id": "1",
                        "name": "Joe Sharp",
                        "country": "Netherlands",
                        "song_name": "You",
                        "song_release_year": "1992",
                        "age": "52",
                        "is_male": "F",
                    },
                    {
                        "singer_id": "2",
                        "name": "Timbaland",
                        "country": "United States",
                        "song_name": "Dangerous",
                        "song_release_year": "2008",
                        "age": "32",
                        "is_male": "T",
                    },
                    {
                        "singer_id": "3",
                        "name": "Justin Brown",
                        "country": "Frane",
                        "song_name": "Hey Oh",
                        "song_release_year": "2013",
                        "age": "20",
                        "is_male": "T",
                    },
                    {
                        "singer_id": "4",
                        "name": "Rose White",
                        "country": "Frane",
                        "song_name": "Sun",
                        "song_release_year": "2003",
                        "age": "41",
                        "is_male": "F",
                    },
                    {
                        "singer_id": "5",
                        "name": "John Nizinik",
                        "country": "Frane",
                        "song_name": "Gentleman",
                        "song_release_year": "2014",
                        "age": "43",
                        "is_male": "T",
                    },
                ],
                "summary": "The table summarizes data on five singers from the Netherlands, United States, and France, detailing their names, song titles, release years, ages, and genders, with songs ranging from 1992 to 2014 and ages from 20 to 52.",
            },
            {
                "table": [
                    {
                        "stuid": "1001",
                        "Iname": "Smith",
                        "fname": "Linda",
                        "age": "18",
                        "sex": "F",
                        "major": "600",
                        "advisor": "1121",
                        "city_code": "BAL",
                    },
                    {
                        "stuid": "1002",
                        "Iname": "Kim",
                        "fname": "Tracy",
                        "age": "19",
                        "sex": "F",
                        "major": "600",
                        "advisor": "7712",
                        "city_code": "HKG",
                    },
                    {
                        "stuid": "1003",
                        "Iname": "Jones",
                        "fname": "Shiela",
                        "age": "21",
                        "sex": "F",
                        "major": "600",
                        "advisor": "7792",
                        "city_code": "WAS",
                    },
                ],
                "summary": "The table presents details of three female students aged 18 to 21, named Linda Smith, Tracy Kim, and Shiela Jones, all majoring in the same field (600), with different advisors and hailing from cities BAL, HKG, and WAS respectively.",
            },
            {
                "table": [
                    {
                        "stadium_id": "5",
                        "location": "Stirling Albion",
                        "name": "Forthbank Stadium",
                        "capacity": "3808",
                        "highest": "1125",
                        "lowest": "404",
                        "average": "642",
                    },
                ],
                "summary": "The table provides information on Forthbank Stadium, the home of Stirling Albion, with a capacity of 3,808 and attendance statistics showing a highest of 1,125, lowest of 404, and an average of 642.",
            },
        ]

    @property
    def table_prefix(self) -> str:
        """Returns the prefix for table input."""
        return "Table: "

    @property
    def summary_prefix(self) -> str:
        """Returns the prefix for summary output."""
        return "Summary: "

    def table_to_string(self, table: List[Dict]) -> str:
        """Converts table dictionary to formatted string representation.

        Args:
            table: List of dictionaries representing table rows

        Returns:
            Formatted string representation of the table
        """
        if not table:
            return ""

        # Extract column names from first row
        column_names = list(table[0].keys())

        # Build string representation
        lines = [f"Column Names: {', '.join(column_names)}."]

        for idx, row in enumerate(table, start=1):
            row_values = [str(value) for value in row.values()]
            lines.append(f"Row {idx}: ({', '.join(row_values)})")

        return "\n".join(lines) + "\n"

    def format_user_input(self, table_in_dict: List[Dict]) -> str:
        """Formats the user input with few-shot examples and the target table.

        Args:
            table_in_dict: Table to summarize as list of dictionaries

        Returns:
            Formatted prompt string with examples and target table
        """
        prompt_parts = []

        # Add few-shot examples
        for example in self.few_shot_examples:
            example_table = self.table_to_string(example["table"])
            prompt_parts.append(f"{self.table_prefix}{example_table}")
            prompt_parts.append(f"{self.summary_prefix}{example['summary']}\n")

        # Add target table
        target_table = self.table_to_string(table_in_dict)
        prompt_parts.append(f"{self.table_prefix}{target_table}")

        return "\n".join(prompt_parts)

    def parse_response(self, response: str) -> str:
        """Extracts summary from LLM response.

        Args:
            response: Raw response from LLM

        Returns:
            Parsed summary text
        """
        if self.summary_prefix in response:
            return response.split("\n")[0].split(self.summary_prefix)[-1].strip()
        return response.strip()

    def generate(self, table: List[Dict]) -> Optional[str]:
        """Generates a natural language summary for the given table.

        Args:
            table: List of dictionaries representing table rows

        Returns:
            Natural language summary of the table, or None if generation fails
        """
        if not table:
            logger.warning("Empty table provided for summarization")
            return None

        # Prepare prompts
        instruction_prompt = self.instruction
        user_prompt = self.format_user_input(table_in_dict=table)

        # Format for LLM (simple concatenation for Llama models)
        formatted_prompt = (
            f"{instruction_prompt}\n\n{user_prompt}\n{self.summary_prefix}"
        )

        try:
            # Call LLM API
            response = requests.post(
                f"{self.api_address}/generate",
                json={
                    "text": [formatted_prompt],
                    "sampling_params": {
                        "max_new_tokens": self.max_new_tokens,
                        "temperature": self.temperature,
                    },
                },
                timeout=30,
            )
            response.raise_for_status()

            response_data = response.json()

            if not response_data or not isinstance(response_data, list):
                logger.error(f"Unexpected API response format: {response_data}")
                return None

            generated_text = response_data[0].get("text", "")
            summary = self.parse_response(generated_text)

            return summary

        except requests.exceptions.Timeout:
            logger.error(f"Request to {self.api_address} timed out")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Request to {self.api_address} failed: {e}")
            return None
        except (KeyError, IndexError, ValueError) as e:
            logger.error(f"Failed to parse API response: {e}")
            return None


@hydra.main(version_base=None, config_path=ABS_CONFIG_DIR, config_name="config")
def main(cfg: DictConfig) -> None:
    # Initialize Table2Text with configuration
    table2text = Table2Text(cfg.conversation.table2text)

    # Example table data
    example_table = [
        {"product_id": "101", "product_name": "Laptop", "price": "1200", "stock": "15"},
        {"product_id": "102", "product_name": "Mouse", "price": "25", "stock": "150"},
        {"product_id": "103", "product_name": "Keyboard", "price": "75", "stock": "80"},
    ]

    logger.info("Generating summary for example table...")
    logger.info(f"Input table: {example_table}")

    # Generate summary
    summary = table2text.generate(example_table)

    if summary:
        logger.info(f"Generated summary: {summary}")
        print(f"\n{'='*60}")
        print(f"Summary: {summary}")
        print(f"{'='*60}\n")
    else:
        logger.error("Failed to generate summary")


if __name__ == "__main__":
    main()
