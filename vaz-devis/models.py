# -*- coding: utf-8 -*-
"""Contrat de données VAZ : ce que le LLM extrait, ce que le template affiche.
Toute la logique métier (totaux, TVA, formatage) vit ici — jamais dans le template.
"""
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
    s = f"{q(x):,.2f}".replace(",", "\u202f").replace(".", ",")
    return f"{s}\u00a0\u20ac"

def fmt_num(x: Decimal) -> str:
    return f"{q(x):,.2f}".replace(",", "\u202f").replace(".", ",")


class TypeDoc(str, Enum):
    devis = "devis"
    facture = "facture"


class Client(BaseModel):
    nom: str
    adresse: list[str]                # lignes d'adresse


class Ligne(BaseModel):
    designation: str                  # intitulé en gras
    detail: Optional[str] = None      # descriptif italique (procédé, matériaux)
    unite: Optional[str] = None       # m², ml, U, Ens, PM, HL…
    qte: Optional[Decimal] = None
    pu: Optional[Decimal] = None      # prix unitaire HT

    @computed_field
    @property
    def total(self) -> Optional[Decimal]:
        if self.qte is None or self.pu is None:
            return None               # PM / hors lot
        return q(self.qte * self.pu)

    # champs formatés pour le template
    @computed_field
    @property
    def qte_f(self) -> str: return fmt_num(self.qte) if self.qte is not None else "\u2014"
    @computed_field
    @property
    def pu_f(self) -> str: return fmt_eur(self.pu) if self.pu is not None else "\u2014"
    @computed_field
    @property
    def total_f(self) -> str:
        if self.total is not None: return fmt_eur(self.total)
        return self.unite if self.unite in ("PM", "HL", "Hors lot") else "\u2014"


class LigneDecompte(BaseModel):
    """Une ligne du bloc des prix, rejouée telle qu'écrite sur le document source.
    La TVA n'est pas un mode : c'est une ligne comme une autre, au libellé libre
    (« TVA 10 % », « TVA 20 % », « TVA — Autoliquidation », « Compte prorata (2 %) »…).
    """
    libelle: str                      # texte libre, affiché tel quel
    montant: Optional[Decimal] = None # signé : négatif si déduction ; None si pas de montant
    texte: Optional[str] = None       # affiché à la place du montant (ex. « Autoliquidation »)
    est_sous_total: bool = False      # ligne de cumul (Total HT, NET À PAYER…) : mise en avant

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
    numero: str                       # attribué par le code (séquence), pas par le LLM
    date_emission: date
    lieu_emission: str = "Livry-Gargan"
    client: Client
    ref_chantier: list[str]           # lignes du bloc "Réf. chantier"
    nature_travaux: str
    chapitres: list[Chapitre]
    decompte: list[LigneDecompte]                       # bloc des prix, dans l'ordre du document
    mentions: list[str] = Field(default_factory=list)   # conditions, validité…
    acompte_pct: Optional[Decimal] = None               # ex. 30 pour 30 %

    # ---- Totaux ----
    @computed_field
    @property
    def total_ht(self) -> Decimal:
        """Somme des lignes chiffrées — sert à vérifier le décompte, pas à l'afficher."""
        return q(sum((c.sous_total for c in self.chapitres), Decimal("0")))
    @computed_field
    @property
    def total_final(self) -> Optional[Decimal]:
        """Dernier montant du décompte : le TTC / net à payer effectif."""
        for t in reversed(self.decompte):
            if t.montant is not None:
                return t.montant
        return None
    @computed_field
    @property
    def acompte(self) -> Optional[Decimal]:
        if self.acompte_pct is None or self.total_final is None: return None
        return q(self.total_final * self.acompte_pct / 100)

    # ---- Modes d'affichage (dérivés, jamais saisis) ----
    @computed_field
    @property
    def a_chiffrage(self) -> bool:
        """Au moins une ligne chiffrée (qté × PU) → colonnes de détail affichées."""
        return any(l.total is not None for c in self.chapitres for l in c.lignes)
    @computed_field
    @property
    def a_chapitres_titres(self) -> bool:
        """Chapitres titrés → en-têtes de chapitre et numérotation 1.1 ; sinon numérotation plate."""
        return any(c.titre.strip() for c in self.chapitres)
    @computed_field
    @property
    def autoliquidation(self) -> bool:
        return any("autoliquidation" in t.libelle.lower() for t in self.decompte)

    # ---- Cohérence lignes ↔ décompte ----
    @model_validator(mode="after")
    def verifie_decompte(self) -> "Document":
        if not self.decompte:
            raise ValueError("decompte vide : le bloc des prix est obligatoire.")
        if self.a_chiffrage:
            premier = next((t for t in self.decompte
                            if t.est_sous_total and t.montant is not None), None)
            if premier is not None and q(premier.montant) != self.total_ht:
                raise ValueError(
                    f"Décompte incohérent : « {premier.libelle} » = {fmt_eur(premier.montant)} "
                    f"mais la somme des lignes fait {fmt_eur(self.total_ht)}."
                )
        return self

    # ---- Formatés ----
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
        mois = ["janvier","f\u00e9vrier","mars","avril","mai","juin","juillet",
                "ao\u00fbt","septembre","octobre","novembre","d\u00e9cembre"]
        d = self.date_emission
        jour = "1er" if d.day == 1 else str(d.day)
        return f"{jour} {mois[d.month-1]} {d.year}"
    @computed_field
    @property
    def titre_doc(self) -> str:
        return "DEVIS" if self.type_doc == TypeDoc.devis else "FACTURE"
