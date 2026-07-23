from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, computed_field, model_validator

D2 = Decimal("0.01")


def q(x: Decimal) -> Decimal:
    return x.quantize(D2, rounding=ROUND_HALF_UP)


def fmt_eur(x: Decimal) -> str:
    s = f"{q(x):,.2f}".replace(",", " ").replace(".", ",")
    return f"{s} €"


def fmt_num(x: Decimal) -> str:
    return f"{q(x):,.2f}".replace(",", " ").replace(".", ",")


class TypeDoc(str, Enum):
    devis = "devis"
    facture = "facture"


class Client(BaseModel):
    nom: str
    adresse: list[str]                # address lines


class Ligne(BaseModel):
    designation: str                  # bold title
    detail: Optional[str] = None      # italic description (process, materials)
    unite: Optional[str] = None       # m², ml, U, Ens, PM, HL…
    qte: Optional[Decimal] = None
    pu: Optional[Decimal] = None      # unit price (HT)

    @computed_field
    @property
    def total(self) -> Optional[Decimal]:
        if self.qte is None or self.pu is None:
            return None               # PM / out of scope
        return q(self.qte * self.pu)

    # pre-formatted fields for the template
    @computed_field
    @property
    def qte_f(self) -> str: return fmt_num(self.qte) if self.qte is not None else "—"
    @computed_field
    @property
    def pu_f(self) -> str: return fmt_eur(self.pu) if self.pu is not None else "—"
    @computed_field
    @property
    def total_f(self) -> str:
        if self.total is not None: return fmt_eur(self.total)
        return self.unite if self.unite in ("PM", "HL", "Hors lot") else "—"


class LigneDecompte(BaseModel):
    """One line of the price block, replayed as written on the source document.
    VAT is not a mode: it is a line like any other, with a free label
    (« TVA 10 % », « TVA — Autoliquidation », « Compte prorata (2 %) »…).
    """
    libelle: str                      # free label, displayed as-is
    montant: Optional[Decimal] = None # signed: negative for deductions; None if no amount
    texte: Optional[str] = None       # displayed instead of the amount (e.g. « Autoliquidation »)
    est_sous_total: bool = False      # running-total line (Total HT, NET À PAYER…): emphasized

    @computed_field
    @property
    def montant_f(self) -> str:
        if self.montant is not None:
            return fmt_eur(self.montant)
        return self.texte or "—"


class Chapitre(BaseModel):
    titre: str
    lignes: list[Ligne]

    @computed_field
    @property
    def sous_total(self) -> Decimal:
        return q(sum((l.total for l in self.lignes if l.total is not None), Decimal("0")))
    @computed_field
    @property
    def sous_total_f(self) -> str: return fmt_eur(self.sous_total)


class Document(BaseModel):
    type_doc: TypeDoc = TypeDoc.devis
    numero: str                       # read from the source document (human-validated)
    date_emission: date
    lieu_emission: str = "Livry-Gargan"
    client: Client
    ref_chantier: list[str]           # lines of the « Réf. chantier » block
    nature_travaux: str
    chapitres: list[Chapitre]
    decompte: list[LigneDecompte]                       # price block, in document order
    mentions: list[str] = Field(default_factory=list)   # terms, validity…
    acompte_pct: Optional[Decimal] = None               # e.g. 30 for 30 %

    # ---- Totals ----
    @computed_field
    @property
    def total_ht(self) -> Decimal:
        """Sum of the priced lines — used to verify the décompte, not to display."""
        return q(sum((c.sous_total for c in self.chapitres), Decimal("0")))
    @computed_field
    @property
    def total_final(self) -> Optional[Decimal]:
        """Last amount of the décompte: the effective total / net payable."""
        for t in reversed(self.decompte):
            if t.montant is not None:
                return t.montant
        return None
    @computed_field
    @property
    def acompte(self) -> Optional[Decimal]:
        if self.acompte_pct is None or self.total_final is None: return None
        return q(self.total_final * self.acompte_pct / 100)

    # ---- Display modes (derived, never provided) ----
    @computed_field
    @property
    def a_chiffrage(self) -> bool:
        """At least one priced line (qty × unit price) → detail columns shown."""
        return any(l.total is not None for c in self.chapitres for l in c.lignes)
    @computed_field
    @property
    def a_chapitres_titres(self) -> bool:
        """Titled chapters → chapter headers and 1.1 numbering; flat numbering otherwise."""
        return any(c.titre.strip() for c in self.chapitres)
    @computed_field
    @property
    def autoliquidation(self) -> bool:
        return any("autoliquidation" in t.libelle.lower() for t in self.decompte)

    # ---- Lines ↔ décompte consistency ----
    @model_validator(mode="after")
    def verifie_decompte(self) -> "Document":
        if not self.decompte:
            raise ValueError("Empty décompte: the price block is mandatory.")
        if self.a_chiffrage:
            premier = next((t for t in self.decompte
                            if t.est_sous_total and t.montant is not None), None)
            if premier is not None and q(premier.montant) != self.total_ht:
                raise ValueError(
                    f"Inconsistent décompte: « {premier.libelle} » = {fmt_eur(premier.montant)} "
                    f"but the lines sum to {fmt_eur(self.total_ht)}."
                )
        return self

    # ---- Formatted ----
    @computed_field
    @property
    def total_ht_f(self) -> str: return fmt_eur(self.total_ht)
    @computed_field
    @property
    def acompte_f(self) -> Optional[str]:
        return fmt_eur(self.acompte) if self.acompte is not None else None
    @computed_field
    @property
    def date_f(self) -> str:
        mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
                "août", "septembre", "octobre", "novembre", "décembre"]
        d = self.date_emission
        jour = "1er" if d.day == 1 else str(d.day)
        return f"{jour} {mois[d.month-1]} {d.year}"
    @computed_field
    @property
    def titre_doc(self) -> str:
        return "DEVIS" if self.type_doc == TypeDoc.devis else "FACTURE"
