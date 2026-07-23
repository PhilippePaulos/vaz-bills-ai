# Prompt Claude Code — Projet VAZ (extraction de devis par photo)

## Contexte

Je construis un outil interne pour l'entreprise familiale VAZ (couverture-étanchéité, Livry-Gargan).
Mes parents photographient des devis/factures manuscrits ou imprimés (via WhatsApp) ; l'outil doit :
photo → extraction LLM (vision) → JSON validé → écran de correction humaine → génération PDF
dans la charte de l'entreprise.

Le dossier `vaz-devis/` est un **état de référence** produit en chat : on le lit, on ne le
prolonge pas. Le code vit dans `src/`, construit étape par étape. Ce que la référence
contient :

- `models.py` — contrat Pydantic `Document` : `client`, `numero`, `date_emission`, `ref_chantier`,
  `nature_travaux`, `chapitres[].lignes[]` (designation, detail, unite, qte, pu), `mode_tva`
  (`tva_20` | `autoliquidation`), `mentions`, `acompte_pct`. Tous les totaux et formats FR
  (`26 993,30 €`, « 11 juillet 2026 ») sont des `computed_field` : c'est la source de vérité unique.
- `templates/devis.html` + `static/styles.css` — rendu Jinja2, DA ardoise `#2A3138` / acier `#4E7186`
  / blanc cassé `#F0F2F4` / zinc `#7C868D`, bandeau répété sur toutes les pages via
  `position: running()` (piège WeasyPrint déjà réglé : `#band{width:210mm}`).
- `render.py` — JSON → validation → HTML (`out/last_render.html`) → PDF WeasyPrint.
- `data/devis_15029.json` — cas de test réel de référence (HT 26 993,30 / TVA 5 398,66 / TTC 32 391,96).

## Règles d'architecture (non négociables)

1. Le LLM **extrait**, le code **calcule** — quand il y a de quoi calculer. Un prix forfaitaire
   (« prix de l'ensemble ») est une **donnée commerciale**, pas le résultat d'un calcul : il est
   extrait, pas recalculé. Là où `qte × pu` existe, on recalcule et on stocke l'écart avec le
   total lu pour l'afficher à la validation. Là où il n'existe pas, il n'y a **aucune
   redondance** : le montant n'est corroboré par rien et doit être relu par l'humain
   systématiquement (voir la hiérarchie tarifaire ci-dessous).

   **Hiérarchie tarifaire — trois niveaux, une seule règle : un forfait renseigné prime sur
   la somme de ses enfants.**
   - Ligne : `total = qte × pu` (ou `None` : PM, hors lot, ligne descriptive).
   - Chapitre : `prix_forfait` s'il est renseigné, sinon la somme des lignes chiffrées,
     sinon `None` (chapitre non chiffrable — jamais `0`).
   - Document : `prix_forfait` s'il est renseigné (forfait global, il peut enjamber plusieurs
     chapitres), sinon la somme des chapitres chiffrés.
   - Un `model_validator` **refuse** un document que rien ne chiffre, et refuse un forfait
     global coexistant avec des forfaits de chapitre (total ambigu). `sum([]) == 0` est le
     piège : sans ce garde-fou, un devis non chiffré s'imprime `0,00 €` chez le client.

   **Arrondi : arrondir chaque ligne (ROUND_HALF_UP), puis sommer les valeurs arrondies.**
   Jamais l'inverse. Sur une facture, ce que le client additionne à la calculatrice doit
   tomber sur le total imprimé — la cohérence visible prime sur l'exactitude mathématique.
   Conséquence assumée : la facture 15016 imprime `Total des travaux 103 215,15` (somme
   brute) alors que ses propres sous-totaux imprimés somment à `103 215,16`. Elle ne se
   somme pas elle-même ; le nouveau code produira `103 215,16` et signalera l'écart.

   **Le décompte est une grammaire, pas un schéma.** Le bloc de totaux n'est pas un trio
   figé HT/TVA/TTC : il peut enchaîner acomptes réglés, retenue de garantie, compte prorata,
   suppléments… (cf. facture 15016). Énumérer les cas est perdu d'avance. On modélise la
   structure, avec **deux concepts et zéro vocabulaire métier** :
   - **terme** : montant signé, ajouté au cumul courant ;
   - **sous-total** : la ligne *affirme* un cumul → point de contrôle.

   Le code rejoue la chaîne et compare à chaque sous-total **sans savoir ce qu'est une retenue
   de garantie**. Le métier reste dans les libellés (donnée), jamais dans le code. Le cumul
   démarre à ce que le corps calcule (chapitres ou `prix_forfait`), et chaque sous-total repart
   de la **valeur lue** — pour qu'une erreur reste localisée au lieu de cascader en fausses
   alertes. Le trio simple n'est qu'un décompte à trois lignes : un seul mécanisme pour tous
   les documents.
2. Le **numéro de document est extrait**, jamais fabriqué ni calculé. Les documents
   photographiés portent déjà leur numéro : en attribuer un autre romprait la correspondance
   avec ce que le client a reçu. Pas de séquence, pas de règle de préfixe. Si aucun numéro
   n'est lisible → `null`, et l'humain le saisit à l'écran de validation.
3. Le JSON `Document` est le pivot unique entre extraction, validation, rendu et archivage.
4. Aucune logique métier dans les templates Jinja2 (affichage de champs `*_f` déjà formatés).
5. Python 3.12, typage strict, Pydantic v2. Pas de framework front lourd : Streamlit suffit.

## Mission — implémenter dans cet ordre

### Étape 1 — Service d'extraction (priorité)
- `src/vaz/extraction/` : `schema.py` (contrat d'extraction), `prompt.py` (prompt système),
  `client.py` → `extract_document(image_paths: list[Path]) -> ExtractionResult`.
- Appel API Anthropic en vision (`claude-opus-4-8`), **structured outputs** :
  `client.messages.parse(output_format=DocumentExtrait)` rend une instance Pydantic déjà
  validée. Pas de tool use forcé : déclarer un faux outil comme porteur de schéma était le
  contournement d'avant `output_config.format` — même garantie, sans la fiction d'une
  fonction qu'on n'implémente jamais. (Le tool use reste la bonne réponse quand il y a de
  vrais outils à appeler ; ici il n'y en a aucun.)
- `DocumentExtrait` est écrit à la main, **distinct de `Document`** : le contrat d'extraction
  n'est pas le contrat de rendu. `numero: str | None` — lu sur le document, tel quel, sans
  reformatage (cf. règle 2). `Decimal` → `float` (format de transport ; conversion en
  `Decimal` au recalcul). `totaux_lus` / `confiance` sont des artefacts d'extraction et
  n'existent pas dans `Document`.
- `confiance` : objet à champs nommés (`client`, `date_emission`, `lignes`, `mode_tva`,
  `totaux`), **pas** un `dict[str, float]` — un schéma strict exige `additionalProperties:
  false`, incompatible avec des clés libres. À traiter comme un signal de tri pour l'UI,
  pas comme une probabilité : l'auto-évaluation d'un LLM est mal calibrée.
- `decompte: list[LigneDecompte]` — `(libelle, montant signé | null, est_sous_total)`, dans
  l'ordre, tel qu'écrit. **Remplace le `totaux_lus(total_ht, tva, total_ttc)` initial**, qui
  était précisément le schéma figé que la facture 15016 invalide. Sans lui, la règle 1
  (« stocker l'écart ») n'a qu'un seul terme à comparer.
- `prix_forfait` sur `ChapitreExtrait` **et** sur `DocumentExtrait` (cf. hiérarchie tarifaire).
  Le devis 14010 est le cas de référence : 7 lignes descriptives, 2 chapitres, un seul
  « PRIX DE L'ENSEMBLE HT » qui les enjambe. **Ne jamais** replier un forfait en une ligne
  `qte=1, pu=montant` : l'arithmétique tombe juste, mais ça écrase les lignes et les chapitres,
  et le PDF regénéré ne ressemble plus à l'original.
- Prompt système : documents BTP français manuscrits ; unités reportées **telles qu'écrites**
  (vocabulaire observé : m², ml, U, Ens, PM, HL, unité, forfait — `U`/`unité` et `Ens`/`forfait`
  cohabitent selon les documents ; on ne normalise pas, le code signale l'inconnue en alerte) ;
  distinguer document détaillé (qte/pu par ligne) et forfait (chapitre ou global) ; détecter
  « autoliquidation » vs TVA 20 % ; ne jamais inventer une valeur illisible → `null`.
- Gérer plusieurs photos = un seul document (pages multiples). Ne pas downscaler : Opus 4.8
  lit jusqu'à 2576 px de côté long (coût : jusqu'à ~4800 tokens/image).
- Clé API via variable d'env `ANTHROPIC_API_KEY` ; retries + timeout propres.

### Étape 2 — Post-traitement & contrôle de cohérence
- `src/vaz/models.py` : porter `Document` depuis la référence **en y ajoutant la hiérarchie
  tarifaire** (`prix_forfait` sur `Chapitre` et `Document`, `sous_total -> Optional[Decimal]`,
  le `model_validator` anti-`0,00 €`). Le modèle de la référence ne sait pas représenter le
  devis 14010 : il imprimerait `0,00 €` au lieu de `3 250,00 €`.
- `reconcile.py` : `DocumentExtrait` → `Document` valide (float → `Decimal` via `str`),
  recalcule les totaux, **rejoue la chaîne du décompte** (cumul depuis le corps, contrôle à
  chaque sous-total, redémarrage sur la valeur lue), et produit une liste d'`alertes` :
  écart à un point de contrôle du décompte ; **forfait non corroboré** (aucune redondance
  possible → relecture humaine obligatoire, pas seulement en cas d'alerte) ; champ null ;
  unité hors vocabulaire observé ; date illisible ou non parsable ; TVA ambiguë (`mode_tva` null).
- Cas de test de référence : la facture 15016 doit produire **exactement une** alerte d'écart,
  d'un centime, sur son premier point de contrôle (`Total des travaux`) — et aucune sur les
  trois suivants, ce qui vérifie que l'erreur ne cascade pas.

### Étape 3 — UI de validation (Streamlit)
- `app.py` : upload photo(s) → extraction → formulaire éditable (tableau des lignes),
  totaux recalculés en direct, alertes visibles, bouton « Générer le PDF » qui appelle
  `render.py` et propose le téléchargement. Afficher la photo à côté du formulaire.

### Étape 4 — Numérotation & archivage
- SQLite (`documents.db`) : table documents (numero **extrait**, type, client, date, montants,
  chemin JSON + PDF, statut brouillon/émis). Pas de séquence, pas de règle de préfixe : le
  numéro vient de l'extraction (règle 2).
- Le numéro n'étant plus généré, il n'est plus garanti unique : contrainte d'unicité en base
  et alerte à la validation si le numéro existe déjà (photo prise deux fois, doublon de saisie).

### Étape 5 — Tests
- `tests/test_models.py` : totaux du 15029 au centime, arrondis ROUND_HALF_UP, formats FR.
- `tests/test_extraction_eval.py` : harnais d'éval — dossier `eval/` de paires
  (photo, JSON attendu), score par champ ; `data/devis_15029.json` = premier golden file.
- `pytest` vert obligatoire avant de passer à l'étape suivante.

## Contraintes de qualité
- Chaque étape livrée = code + test + une ligne dans `README.md` (usage).
- Commits atomiques par étape. Pas de dépendance exotique sans justification.
- Ne pas toucher à la DA (`styles.css`) sans demande explicite.

## Environnement
- `uv` pour tout : `uv add` (déclare + résout + installe), `uv run` (exécute ; pas d'activation).
  `pyproject.toml` est la source de vérité unique des dépendances — pas de `requirements.txt`.
- Python 3.12 pinné (`.python-version`). `uv sync` reconstruit l'environnement depuis `uv.lock`.
- WeasyPrint (rendu, étape 3) exige `brew install pango` **et** `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`
  sur Apple Silicon — la lib est système, aucune commande `uv` n'y peut rien. Ne bloque pas l'étape 1.

Le schéma d'extraction et le prompt système de l'étape 1 sont validés : implémente.