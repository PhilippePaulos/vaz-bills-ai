import pytest

from src.extraction.errors import ExtractionError
from src.extraction.validators import lump_sum_on_one_level_only, vat_regime_resolved


def _chapter(prix_forfait=None):
    return {"titre": "", "lignes": [], "prix_forfait": prix_forfait}


def test_lump_sum_on_both_levels_is_refused(make_document):
    doc = make_document(prix_forfait=480.0, chapitres=[_chapter(prix_forfait=480.0)])
    with pytest.raises(ExtractionError, match="Lump-sum conflict"):
        lump_sum_on_one_level_only(doc)


def test_lump_sum_on_document_level_only_passes(make_document):
    doc = make_document(prix_forfait=480.0, chapitres=[_chapter()])
    lump_sum_on_one_level_only(doc)


def test_lump_sum_on_chapter_level_only_passes(make_document):
    doc = make_document(chapitres=[_chapter(prix_forfait=480.0)])
    lump_sum_on_one_level_only(doc)


def test_vat_mentioned_without_rate_is_refused(make_document):
    doc = make_document(
        decompte=[{"libelle": "TVA 5,5 %", "montant": 10.0, "est_sous_total": False}]
    )
    with pytest.raises(ExtractionError, match="VAT not recognized"):
        vat_regime_resolved(doc)


def test_vat_with_rate_passes(make_document):
    doc = make_document(
        tva_pct=10.0,
        decompte=[{"libelle": "TVA 10 %", "montant": 48.0, "est_sous_total": False}],
    )
    vat_regime_resolved(doc)


def test_reverse_charge_without_rate_passes(make_document):
    doc = make_document(
        autoliquidation=True,
        decompte=[{"libelle": "TVA — Autoliquidation", "montant": None, "est_sous_total": False}],
    )
    vat_regime_resolved(doc)


def test_no_vat_line_at_all_passes(make_document):
    doc = make_document(
        decompte=[{"libelle": "Total TTC", "montant": 528.0, "est_sous_total": True}]
    )
    vat_regime_resolved(doc)
