from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.rendering.models import Document

logger = logging.getLogger(__name__)

_PACKAGE_DIR = Path(__file__).parent


class PdfRenderer:
    """Renders a Document to PDF.

    The template directory is injected so alternative layouts can be tried
    without touching this class; the default is the package's own
    templates/ + static/ pair.
    """

    def __init__(
        self,
        template_dir: Optional[Path] = None,
        template_name: str = "devis.html",
    ) -> None:
        self._template_dir = template_dir or _PACKAGE_DIR / "templates"
        self._template_name = template_name
        self._env = Environment(
            loader=FileSystemLoader(self._template_dir),
            autoescape=select_autoescape(["html"]),
        )

    def render_html(self, doc: Document) -> str:
        return self._env.get_template(self._template_name).render(d=doc)

    def render_pdf(self, doc: Document, pdf_path: str | Path) -> Path:
        from weasyprint import HTML

        out_dir = _PACKAGE_DIR / "out"
        out_dir.mkdir(exist_ok=True)
        preview = out_dir / "last_render.html"
        preview.write_text(self.render_html(doc), encoding="utf-8")  # browser preview

        pdf_path = Path(pdf_path)
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        HTML(filename=str(preview)).write_pdf(str(pdf_path))
        logger.info("PDF written: %s", pdf_path)
        return pdf_path
