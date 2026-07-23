from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.extraction.extractor import DEFAULT_MODEL, DocumentExtractor
from src.mapping import to_render_document
from src.rendering.renderer import PdfRenderer


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Photos of one quote/invoice → extraction → generated PDF."
    )
    parser.add_argument("photos", nargs="+", type=Path, help="Photos, in page order.")
    parser.add_argument("--out", type=Path, required=True, help="Output PDF path.")
    parser.add_argument("--numero", default=None, help="Override the document number.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model id. Default: {DEFAULT_MODEL}.")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )
    load_dotenv()

    result = DocumentExtractor(model=args.model).extract(args.photos)
    doc = to_render_document(result.document, numero=args.numero)
    PdfRenderer().render_pdf(doc, args.out)

    print(f"{doc.titre_doc} {doc.numero} -> {args.out}")
    print(" | ".join(f"{t.libelle} {t.montant_f}" for t in doc.decompte))
    print(f"{result.model} | {result.input_tokens} tokens in / {result.output_tokens} out",
          file=sys.stderr)


if __name__ == "__main__":
    main()
