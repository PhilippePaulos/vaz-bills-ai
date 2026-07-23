from datetime import date
from decimal import Decimal

import pytest

from src.mapping import MappingError, parse_written_date, to_render_document


class TestParseWrittenDate:
    def test_full_french_date(self):
        assert parse_written_date("21 juillet 2026") == date(2026, 7, 21)

    def test_first_of_month(self):
        assert parse_written_date("1er août 2025") == date(2025, 8, 1)

    def test_numeric_short_year(self):
        assert parse_written_date("11/07/26") == date(2026, 7, 11)

    def test_numeric_full_year_with_dashes(self):
        assert parse_written_date("11-07-2026") == date(2026, 7, 11)

    def test_garbage_raises(self):
        with pytest.raises(MappingError, match="Unreadable issue date"):
            parse_written_date("un jour prochain")


class TestToRenderDocument:
    def test_lump_sum_invoice_maps_end_to_end(self, make_document):
        extrait = make_document(
            chapitres=[{"titre": "", "prix_forfait": None, "lignes": [
                {"designation": "Dépose d'une partie de terre", "detail": None,
                 "unite": None, "qte": None, "pu": None},
            ]}],
            tva_pct=10.0,
            prix_forfait=480.0,
            decompte=[
                {"libelle": "Prix de l'ensemble HT", "montant": 480.0, "est_sous_total": True},
                {"libelle": "TVA 10 %", "montant": 48.0, "est_sous_total": False},
                {"libelle": "Total TTC", "montant": 528.0, "est_sous_total": True},
            ],
        )

        doc = to_render_document(extrait)

        assert doc.numero == "15024/07/26"          # month/year appended from the issue date
        assert doc.date_emission == date(2026, 7, 21)
        assert doc.a_chiffrage is False           # description-only table
        assert doc.total_final == Decimal("528.0")
        assert [t.libelle for t in doc.decompte] == ["Prix de l'ensemble HT", "TVA 10 %", "Total TTC"]

    def test_floats_become_exact_decimals(self, make_document):
        extrait = make_document(
            chapitres=[{"titre": "Travaux", "prix_forfait": None, "lignes": [
                {"designation": "Sécurisation", "detail": None,
                 "unite": "ml", "qte": 44.6, "pu": 18.0},
            ]}],
            decompte=[{"libelle": "Total HT", "montant": 802.8, "est_sous_total": True}],
        )

        doc = to_render_document(extrait)

        ligne = doc.chapitres[0].lignes[0]
        assert ligne.qte == Decimal("44.6")       # not 44.600000000000001…
        assert ligne.total == Decimal("802.80")

    def test_numero_override_wins(self, make_document):
        doc = to_render_document(
            make_document(decompte=[{"libelle": "Total TTC", "montant": 1.0, "est_sous_total": True}]),
            numero="15030/07/26",
        )
        assert doc.numero == "15030/07/26"

    def test_bare_numero_gets_month_year_suffix(self, make_document):
        doc = to_render_document(
            make_document(decompte=[{"libelle": "Total TTC", "montant": 1.0, "est_sous_total": True}]),
            numero="15028",
        )
        assert doc.numero == "15028/07/26"          # from date_emission « 21 juillet 2026 »

    def test_already_suffixed_numero_is_kept_verbatim(self, make_document):
        # Suffix disagrees with the issue date: numbers are verbatim, human review decides.
        doc = to_render_document(
            make_document(decompte=[{"libelle": "Total TTC", "montant": 1.0, "est_sous_total": True}]),
            numero="15028/06/26",
        )
        assert doc.numero == "15028/06/26"

    def test_chapter_lump_sum_is_refused(self, make_document):
        extrait = make_document(
            chapitres=[{"titre": "Lot 1", "prix_forfait": 300.0, "lignes": []}],
            decompte=[{"libelle": "Total TTC", "montant": 300.0, "est_sous_total": True}],
        )
        with pytest.raises(MappingError, match="Chapter-level lump sums"):
            to_render_document(extrait)

    def test_lump_sum_decompte_disagreement_is_refused(self, make_document):
        extrait = make_document(
            prix_forfait=480.0,
            decompte=[{"libelle": "Prix de l'ensemble HT", "montant": 490.0, "est_sous_total": True}],
        )
        with pytest.raises(MappingError, match="disagree"):
            to_render_document(extrait)

    def test_reverse_charge_line_gets_display_text(self, make_document):
        extrait = make_document(
            autoliquidation=True,
            decompte=[
                {"libelle": "Total HT", "montant": 100.0, "est_sous_total": True},
                {"libelle": "TVA — Autoliquidation", "montant": None, "est_sous_total": False},
            ],
        )

        doc = to_render_document(extrait)

        assert doc.decompte[1].texte == "Autoliquidation"
        assert doc.autoliquidation is True        # triggers the legal notice in the PDF

    def test_missing_type_doc_is_refused(self, make_document):
        extrait = make_document(
            type_doc=None,
            decompte=[{"libelle": "Total TTC", "montant": 1.0, "est_sous_total": True}],
        )
        with pytest.raises(MappingError, match="type_doc"):
            to_render_document(extrait)
