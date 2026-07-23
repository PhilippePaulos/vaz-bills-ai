# -*- coding: utf-8 -*-
"""Rendu d'un document VAZ : JSON -> validation Pydantic -> Jinja2 -> WeasyPrint PDF.
Usage : python render.py data/devis_15029.json out/Devis_15029.pdf
"""
import json, sys
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML
from models import Document

ROOT = Path(__file__).parent

def render(json_path: str, pdf_path: str) -> Document:
    doc = Document.model_validate(json.loads(Path(json_path).read_text(encoding="utf-8")))
    env = Environment(loader=FileSystemLoader(ROOT / "templates"),
                      autoescape=select_autoescape(["html"]))
    html = env.get_template("devis.html").render(d=doc)
    tmp = ROOT / "out" / "last_render.html"
    tmp.write_text(html, encoding="utf-8")            # debug/preview navigateur
    HTML(filename=str(tmp)).write_pdf(pdf_path)       # ../static résolu depuis out/
    return doc

if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "data/devis_15029.json"
    dst = sys.argv[2] if len(sys.argv) > 2 else "out/Devis_15029.pdf"
    d = render(src, dst)
    print(f"{d.titre_doc} {d.numero} -> {dst}")
    print(" | ".join(f"{t.libelle} {t.montant_f}" for t in d.decompte))
