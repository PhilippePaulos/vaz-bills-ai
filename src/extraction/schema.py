from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LigneExtraite(_Strict):
    designation: str = Field(
        description="The line-item title, cleaned up: spelling and accents fixed, abbreviations "
                    "expanded, trade terms corrected (« première d'accrochage » → « primaire "
                    "d'accrochage »), without changing the meaning."
    )
    detail: Optional[str] = Field(
        description="The description under the title (process, materials, brands), cleaned up, "
                    "trade terms and product names corrected. null if absent."
    )
    unite: Optional[str] = Field(
        description="The unit exactly as written (m², ml, U, Ens, PM, HL, unité, forfait…). "
                    "Do not translate, abbreviate or harmonize. null if absent."
    )
    qte: Optional[float] = Field(
        description="The quantity as read. null if the line is not individually priced."
    )
    pu: Optional[float] = Field(
        description="The unit price (HT) as read. null if the line is not individually priced."
    )


class ChapitreExtrait(_Strict):
    titre: str = Field(
        description='The chapter/lot title, cleaned up (spelling, accents). '
                    '"" if the document has no chapters.'
    )
    lignes: list[LigneExtraite]
    prix_forfait: Optional[float] = Field(
        description="Lump-sum price of THIS chapter if it is sold as a package. null if its "
                    "lines are priced one by one, or if the lump sum covers the whole document."
    )


class ClientExtrait(_Strict):
    nom: Optional[str] = Field(description="The recipient client name (« Adressé à » block).")
    adresse: list[str] = Field(
        description="Client address lines, one entry per written line, in proper postal form: "
                    "abbreviations expanded, hyphenated town names (« 93390 Clichy-sous-Bois »)."
    )


class LigneDecompte(_Strict):
    libelle: str = Field(
        description="The line label, cleaned up and completed into a standard invoice label "
                    "(« TTC » → « Total TTC », « Prix de l'ensemble » → « Prix de l'ensemble HT », "
                    "« Acomptes déjà réglés (HT) », « Retenue de garantie (5 %) »…)."
    )
    montant: Optional[float] = Field(
        description="The amount, strictly as read, SIGNED: negative when the document shows it "
                    "as a deduction (« − 61 929,09 € »). null when the line has no amount "
                    "(e.g. « TVA — Autoliquidation »)."
    )
    est_sous_total: bool = Field(
        description="True when the line ASSERTS a running total of the previous lines rather than "
                    "adding a new amount — spot it by bold text, a separator rule, or the words "
                    "TOTAL / NET / MONTANT TOTAL. "
                    "True: « Montant total HT du marché », « NET À PAYER TTC ». "
                    "False: « Suppléments divers », « TVA 20 % », « Compte prorata (2 %) »."
    )


class Confiance(_Strict):
    """0-to-1 score per field group: photo legibility and reading certainty."""
    client: float
    date_emission: float
    lignes: float
    tva: float
    decompte: float


class DocumentExtrait(_Strict):
    type_doc: Optional[Literal["devis", "facture"]]
    numero: Optional[str] = Field(
        description='The document number, exactly as written (e.g. "15029/07/26"). Do not '
                    "reformat or complete it, never invent one: unreadable or absent → null."
    )
    date_emission: Optional[str] = Field(
        description="The issue date exactly as written (e.g. « 2 octobre 2025 », « 11/07/26 »). "
                    "The code normalizes it: do not reformat or complete it."
    )
    client: ClientExtrait
    ref_chantier: list[str] = Field(
        description="Lines of the « Réf. chantier » block: work-site address, expert reference, "
                    "claim, insurer, policy number… One entry per written line, cleaned up "
                    "(abbreviations expanded, addresses in proper postal form)."
    )
    nature_travaux: Optional[str] = Field(
        description="The line (often in italics) describing the purpose of the works, cleaned up "
                    "(spelling, agreement: « Travaux réalisé » → « Travaux réalisés »)."
    )
    chapitres: list[ChapitreExtrait]
    tva_pct: Optional[float] = Field(
        description="The VAT rate as written on the document, as a percentage (10, 20, 5.5…), "
                    "strictly as read. Never derive it from the amounts and never guess it. "
                    "null if no rate is shown or the document is under reverse charge."
    )
    autoliquidation: bool = Field(
        description="True when the document states VAT reverse charge (« Autoliquidation », "
                    "« art. 283-2 nonies du CGI », « TVA due par le preneur »)."
    )
    mentions: list[str] = Field(
        description="Terms, validity, and free-text blocks outside the table (e.g. « INTERVENTION »)."
    )
    acompte_pct: Optional[float] = Field(description="The requested deposit percentage (e.g. 30 for 30 %).")
    prix_forfait: Optional[float] = Field(
        description="Lump-sum price of the whole document if it is sold as a package "
                    "(« PRIX DE L'ENSEMBLE HT »), including when it spans several chapters. "
                    "null if the document is itemized or if lump sums are set chapter by chapter."
    )
    decompte: list[LigneDecompte] = Field(
        description="The totals block at the bottom of the document, line by line, IN ORDER, "
                    "amounts strictly as read. May be a simple trio (total HT / VAT / TTC) or a "
                    "running account of several lines (deposits, retention, compte prorata…). "
                    "Do not reorder, merge or omit any line: the code replays the chain to verify it."
    )
    confiance: Confiance
