import pytest

from src.extraction.schema import DocumentExtrait

_FULL_CONFIDENCE = {"client": 1, "date_emission": 1, "lignes": 1, "tva": 1, "decompte": 1}


@pytest.fixture
def make_document():
    """Factory for a minimal valid DocumentExtrait, overridable field by field."""

    def _make(**overrides) -> DocumentExtrait:
        base = {
            "type_doc": "facture",
            "numero": "15024",
            "date_emission": "21 juillet 2026",
            "client": {"nom": "SCI du Temple", "adresse": []},
            "ref_chantier": [],
            "nature_travaux": None,
            "chapitres": [],
            "tva_pct": None,
            "autoliquidation": False,
            "mentions": [],
            "acompte_pct": None,
            "prix_forfait": None,
            "decompte": [],
            "confiance": _FULL_CONFIDENCE,
        }
        base.update(overrides)
        return DocumentExtrait.model_validate(base)

    return _make
