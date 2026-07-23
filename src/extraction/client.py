from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.extraction.extractor import DEFAULT_MODEL, DocumentExtractor


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Extract a quote/invoice from one or more photos of the same document."
    )
    parser.add_argument("photos", nargs="+", type=Path, help="Photos, in page order.")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Model id. Default: {DEFAULT_MODEL}.",
    )
    args = parser.parse_args(argv)

    # Logs on stderr: stdout is reserved for the extracted JSON (redirectable with >).
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )
    load_dotenv()

    result = DocumentExtractor(model=args.model).extract(args.photos)
    print(json.dumps(result.document.model_dump(), indent=2, ensure_ascii=False))
    print(
        f"\n{result.model} | {result.input_tokens} tokens in / {result.output_tokens} out",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
