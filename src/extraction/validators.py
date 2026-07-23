from __future__ import annotations

from typing import Callable

from src.extraction.errors import ExtractionError
from src.extraction.schema import DocumentExtrait

Validator = Callable[[DocumentExtrait], None]


def lump_sum_on_one_level_only(doc: DocumentExtrait) -> None:
    """A lump sum lives at exactly one level — document OR chapters, never both.

    A price duplicated on both levels would be double-counted downstream.
    """
    if doc.prix_forfait is None:
        return
    doubled = [c.titre or "(untitled)" for c in doc.chapitres if c.prix_forfait is not None]
    if doubled:
        raise ExtractionError(
            f"Lump-sum conflict: prix_forfait is set at the document level "
            f"({doc.prix_forfait}) and on chapter(s) {doubled}. Human review required."
        )


def vat_regime_resolved(doc: DocumentExtrait) -> None:
    """The décompte mentions VAT: a rate or a reverse-charge flag must have been read.

    Refuse the document rather than letting an unresolved VAT regime through.
    """
    vat_labels = [t.libelle for t in doc.decompte if "tva" in t.libelle.lower()]
    if vat_labels and doc.tva_pct is None and not doc.autoliquidation:
        raise ExtractionError(
            f"VAT not recognized: the décompte mentions {vat_labels} but no rate could "
            "be read (tva_pct is null) and no reverse charge is stated. "
            "Human review required."
        )


DEFAULT_VALIDATORS: tuple[Validator, ...] = (
    lump_sum_on_one_level_only,
    vat_regime_resolved,
)
