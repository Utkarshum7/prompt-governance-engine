"""Dataset reader service for reading prompts from Dataset folder."""

import csv
import json
from pathlib import Path
from typing import Generator, List, Optional, Union

import structlog

logger = structlog.get_logger(__name__)


class DatasetReader:
    """Service to read prompts from Dataset folder."""

    def __init__(self, dataset_path: Optional[Union[str, Path]] = None):
        """
        Initialize dataset reader.

        Args:
            dataset_path: Path to Dataset folder. If None, uses Dataset/ relative to project root.
        """
        if dataset_path is None:
            # Look for Dataset/ folder relative to project root
            project_root = Path(__file__).parent.parent.parent.parent
            dataset_path = project_root / "Dataset"

        self.dataset_path = Path(dataset_path)

        if not self.dataset_path.exists():
            logger.warning("Dataset folder not found", path=str(self.dataset_path))
        else:
            logger.info("Dataset reader initialized", path=str(self.dataset_path))

    def _read_json(self, file_path: Path) -> Generator[dict, None, None]:
        """
        Read JSON file and yield prompts.

        Args:
            file_path: Path to JSON file

        Yields:
            Prompt data dictionaries
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Handle different JSON structures
            if isinstance(data, list):
                # List of prompts
                for item in data:
                    yield item
            elif isinstance(data, dict):
                # Single object or object with prompts array
                if "prompts" in data:
                    for item in data["prompts"]:
                        yield item
                elif "data" in data:
                    for item in data["data"]:
                        yield item
                else:
                    # Single prompt object
                    yield data

        except json.JSONDecodeError as e:
            logger.error("JSON decode error", file=str(file_path), error=str(e))
            raise
        except Exception as e:
            logger.error("Error reading JSON file", file=str(file_path), error=str(e))
            raise

    def _read_jsonl(self, file_path: Path) -> Generator[dict, None, None]:
        """
        Read JSONL file and yield prompts.

        Args:
            file_path: Path to JSONL file

        Yields:
            Prompt data dictionaries
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                        yield data
                    except json.JSONDecodeError as e:
                        logger.warning(
                            "JSONL line decode error",
                            file=str(file_path),
                            line=line_num,
                            error=str(e),
                        )
                        continue

        except Exception as e:
            logger.error("Error reading JSONL file", file=str(file_path), error=str(e))
            raise

    def _read_csv(self, file_path: Path) -> Generator[dict, None, None]:
        """
        Read CSV file and yield prompts.

        Args:
            file_path: Path to CSV file

        Yields:
            Prompt data dictionaries (row as dict)
        """
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    yield row

        except Exception as e:
            logger.error("Error reading CSV file", file=str(file_path), error=str(e))
            raise

    def _read_txt(self, file_path: Path) -> Generator[dict, None, None]:
        """
        Read TXT file and yield prompts (one per line).

        Args:
            file_path: Path to TXT file

        Yields:
            Prompt data dictionaries with 'content' key
        """
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    yield {"content": line, "line_number": line_num}

        except Exception as e:
            logger.error("Error reading TXT file", file=str(file_path), error=str(e))
            raise

    def _extract_prompt_content(self, data: dict) -> Optional[str]:
        """
        Extract prompt content from data dictionary.

        Args:
            data: Data dictionary

        Returns:
            Prompt content string or None
        """
        # Try common field names
        for field in ["prompt", "content", "text", "message", "input", "query"]:
            if field in data:
                value = data[field]
                if isinstance(value, str):
                    return value
                elif isinstance(value, dict) and "content" in value:
                    return value["content"]

        # If no standard field, try to get first string value
        for key, value in data.items():
            if isinstance(value, str) and value.strip():
                return value

        return None

    def read_file(self, file_path: Union[str, Path]) -> Generator[dict, None, None]:
        """
        Read prompts from a file based on its extension.

        Args:
            file_path: Path to file

        Yields:
            Prompt data dictionaries

        Raises:
            ValueError: If file format is not supported
        """
        file_path = Path(file_path)
        suffix = file_path.suffix.lower()

        logger.debug("Reading file", file=str(file_path), format=suffix)

        if suffix == ".json":
            yield from self._read_json(file_path)
        elif suffix == ".jsonl":
            yield from self._read_jsonl(file_path)
        elif suffix == ".csv":
            yield from self._read_csv(file_path)
        elif suffix in [".txt", ".text"]:
            yield from self._read_txt(file_path)
        else:
            raise ValueError(f"Unsupported file format: {suffix}")

    def list_files(self) -> List[Path]:
        """
        List all supported files in dataset folder.

        Returns:
            List of file paths
        """
        if not self.dataset_path.exists():
            return []

        supported_extensions = {".json", ".jsonl", ".csv", ".txt", ".text"}
        files = []

        for file_path in self.dataset_path.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                files.append(file_path)

        logger.info("Found dataset files", count=len(files), path=str(self.dataset_path))
        return files

    def read_all(self) -> Generator[tuple[Path, dict], None, None]:
        """
        Read all prompts from all files in dataset folder.

        Yields:
            Tuples of (file_path, prompt_data)
        """
        files = self.list_files()

        for file_path in files:
            try:
                logger.info("Processing file", file=str(file_path))
                file_count = 0

                for prompt_data in self.read_file(file_path):
                    file_count += 1
                    yield file_path, prompt_data

                logger.info("File processed", file=str(file_path), prompts=file_count)

            except Exception as e:
                logger.error(
                    "Error processing file, continuing",
                    file=str(file_path),
                    error=str(e),
                )
                # Continue processing other files
                continue


def get_dataset_reader(dataset_path: Optional[Union[str, Path]] = None) -> DatasetReader:
    """
    Get dataset reader instance.

    Args:
        dataset_path: Optional path to Dataset folder

    Returns:
        DatasetReader instance
    """
    return DatasetReader(dataset_path=dataset_path)

