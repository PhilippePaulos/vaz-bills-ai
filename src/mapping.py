from __future__ import annotations

import re
import unicodedata
from datetime import date
from decimal import Decimal
from typing import Optional

from src.extraction.schema import DocumentExtrait
from src.rendering.models import Chapitre, Client, Document, Ligne, LigneDecompte, TypeDoc


class MappingError(ValueError):
    """The extracted document cannot be turned into a printable one as-is."""


_MONTHS = {
    "janvier": 1, "fevrier": 2, "février": 2, "mars": 3, "avril": 4, "mai": 5,
    "juin": 6, "juillet": 7, "aout": 8, "août": 8, "septembre": 9,
    "octobre": 10, "novembre": 11, "decembre": 12, "décembre": 12,
}


def _dec(x: Optional[float]) -> Optional[Decimal]:
    return None if x is None else Decimal(str(x))


_NUMERO_SUFFIX = re.compile(r"/\d{2}/\d{2}$")


def format_numero(numero: str, date_emission: date) -> str:
    """Document numbers always carry month/year: « 15028 » → « 15028/07/26 »."""
    if _NUMERO_SUFFIX.search(numero):
        return numero
    return f"{numero}/{date_emission:%m}/{date_emission:%y}"


def parse_written_date(text: str) -> date:
    """Parse dates as they appear on the documents:
    « 21 juillet 2026 », « 1er août 2025 », « 11/07/26 », « 11-07-2026 »."""
    cleaned = unicodedata.normalize("NFKC", text).strip().lower()

    m = re.search(r"(\d{1,2})(?:er)?\s+([a-zàâéèêîôûç]+)\s+(\d{4})", cleaned)
    if m:
        month = _MONTHS.get(m.group(2))
        if month:
            return date(int(m.group(3)), month, int(m.group(1)))

    m = re.search(r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})", cleaned)
    if m:
        day, month, year = (int(g) for g in m.groups())
        if year < 100:
            year += 2000
        return date(year, month, day)

    raise MappingError(f"Unreadable issue date: {text!r}")


def to_render_document(
    extrait: DocumentExtrait,
    *,
    numero: Optional[str] = None,
    date_emission: Optional[date] = None,
) -> Document:
    if extrait.type_doc is None:
        raise MappingError("type_doc missing: quote or invoice? Human review required.")
    final_numero = numero or extrait.numero
    if not final_numero:
        raise MappingError("No document number: extraction read none and no override given.")
    if extrait.client.nom is None:
        raise MappingError("Client name missing.")
    if date_emission is None:
        if not extrait.date_emission:
            raise MappingError("Issue date missing.")
        date_emission = parse_written_date(extrait.date_emission)
    final_numero = format_numero(final_numero, date_emission)

    # The renderer only knows two pricing forms: itemized lines, or a document
    # lump sum carried by the décompte. Chapter lump sums need template work first.
    forfait_chapters = [c.titre or "(untitled)" for c in extrait.chapitres if c.prix_forfait is not None]
    if forfait_chapters:
        raise MappingError(
            f"Chapter-level lump sums are not supported by the renderer yet: {forfait_chapters}"
        )

    decompte = [
        LigneDecompte(
            libelle=t.libelle,
            montant=_dec(t.montant),
            texte="Autoliquidation"
            if t.montant is None and "autoliquidation" in t.libelle.lower() else None,
            est_sous_total=t.est_sous_total,
        )
        for t in extrait.decompte
    ]

    # The document lump sum is displayed through the décompte: check they agree
    # instead of silently trusting one of the two.
    if extrait.prix_forfait is not None:
        premier = next((t for t in decompte if t.est_sous_total and t.montant is not None), None)
        if premier is not None and premier.montant != _dec(extrait.prix_forfait):
            raise MappingError(
                f"Lump sum ({extrait.prix_forfait}) and first décompte total "
                f"(« {premier.libelle} » = {premier.montant}) disagree. Human review required."
            )

    return Document(
        type_doc=TypeDoc(extrait.type_doc),
        numero=final_numero,
        date_emission=date_emission,
        client=Client(nom=extrait.client.nom, adresse=extrait.client.adresse),
        ref_chantier=extrait.ref_chantier,
        nature_travaux=extrait.nature_travaux or "",
        chapitres=[
            Chapitre(
                titre=c.titre,
                lignes=[
                    Ligne(
                        designation=ligne.designation,
                        detail=ligne.detail,
                        unite=ligne.unite,
                        qte=_dec(ligne.qte),
                        pu=_dec(ligne.pu),
                    )
                    for ligne in c.lignes
                ],
            )
            for c in extrait.chapitres
        ],
        decompte=decompte,
        mentions=extrait.mentions,
        acompte_pct=_dec(extrait.acompte_pct),
    )
