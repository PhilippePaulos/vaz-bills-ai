# VAZ — Génération de devis & factures

Pipeline de rendu : **JSON (Pydantic) → Jinja2/HTML → WeasyPrint → PDF**.
Charte : ardoise `#2A3138` · acier `#4E7186` · blanc cassé `#F0F2F4` · zinc `#7C868D`.

## Structure

```
vaz-devis/
├── models.py            # Contrat de données (Pydantic) : source de vérité des calculs
├── render.py            # JSON -> validation -> template -> PDF
├── templates/
│   └── devis.html       # Template Jinja2 (devis chapitré ; sert aussi aux factures via type_doc)
├── static/
│   ├── styles.css       # DA + mise en page print (@page, bandeau running toutes pages)
│   └── logo_vaz.svg     # Logo vectoriel (recolorable)
├── data/
│   ├── devis_15029.json   # Exemple réel : devis chapitré, lignes chiffrées (6 colonnes)
│   └── facture_15024.json # Exemple réel : facture au forfait, descriptions seules (2 colonnes)
└── out/                 # PDF générés + last_render.html (aperçu navigateur)
```

## Installation

```bash
pip install weasyprint jinja2 pydantic
```

WeasyPrint nécessite Pango (Linux : `apt install libpango-1.0-0 libpangocairo-1.0-0` ; macOS : `brew install pango`).
Sur macOS, WeasyPrint ne trouve pas les dylibs Homebrew tout seul :

```bash
export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib
```

## Usage

```bash
python render.py data/devis_15029.json out/Devis_15029.pdf
```

Aperçu rapide pendant le développement : ouvrir `out/last_render.html` dans un navigateur
(le rendu paginé exact reste celui du PDF).

## Règles d'architecture

1. **Toute la logique dans `models.py`** : formats monétaires, dates en toutes lettres,
   modes d'affichage dérivés. Le template ne fait qu'afficher des champs déjà formatés (`*_f`).
2. **Le bloc des prix est un `decompte`** : une liste ordonnée de lignes `libellé | montant`
   rejouée telle qu'écrite sur le document source, toujours rendue dans le tableau
   (disposition de la facture 15024). La TVA n'est pas un mode mais une ligne au libellé
   libre (« TVA 10 % », « TVA 20 % », « TVA — Autoliquidation »…). `est_sous_total`
   met une ligne en avant ; la dernière ligne est toujours le total final (fond ardoise).
   Garde-fou : si des lignes sont chiffrées, le premier sous-total du décompte doit égaler
   leur somme, sinon la validation Pydantic rejette le document.
3. **Colonnes de détail conditionnelles** : si aucune ligne n'est chiffrée (qté × PU),
   le tableau ne montre que N° + Description — mais les lignes restent toujours numérotées
   (plate 1, 2, 3 sans chapitres titrés ; 1.1, 1.2 avec).
4. **Le JSON est le pivot** : c'est lui que produit l'extraction LLM (vision) et que
   valide l'humain avant génération. Ne jamais laisser le LLM écrire du HTML.
5. **Le numéro de document est attribué par le code** (séquence en base), jamais par le LLM.
6. **Un template par type de document** quand la structure diverge (devis chapitré,
   facture simple, décompte de solde, rapport) ; blocs CSS partagés dans `styles.css`.

## Points CSS à connaître

- Le bandeau est un élément `position: running(band)` injecté dans `@top-center` :
  il se répète sur **toutes les pages**, pleine largeur (marges gauche/droite de page = 0).
- Piège WeasyPrint : la boîte de marge ne s'étire pas au contenu → largeur explicite
  `#band{ width:210mm }` (déjà en place).
- `thead { display: table-header-group }` répète l'en-tête du tableau quand il se coupe
  entre deux pages ; `tr { break-inside: avoid }` évite les lignes coupées.

## Étapes suivantes (roadmap projet)

1. **Extraction** : endpoint FastAPI `POST /extract` — photo → API Anthropic (vision +
   tool use) → JSON conforme à `models.Document` (le schéma Pydantic sert de JSON Schema).
2. **Validation humaine** : petite UI (Streamlit) qui affiche le JSON en formulaire
   éditable, recalcule les totaux en direct, signale les écarts LLM vs calcul.
3. **Numérotation & archivage** : SQLite (numéro séquentiel, client, montants, chemin PDF).
4. **Templates supplémentaires** : facture simple, décompte de solde, rapport d'intervention.
