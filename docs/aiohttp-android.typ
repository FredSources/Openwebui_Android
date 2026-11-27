#import "@preview/ilm:2.1.0": *
#import "helpers.typ": *
#import "@preview/merman:0.3.0": show-mermaid-blocks

#set text(lang: "fr")
#set heading(numbering: "1.1")
#set par(justify: true)
#show figure.where(kind: table): set block(breakable: true)
#show raw.where(lang: "mermaid"): show-mermaid-blocks(
  width: 100%,
  document-context: true,
)

#show: ilm.with(
  title: [Recompilation d'aiohttp pour Android],
  authors: "Équipe projet openwebui-android",
  date: datetime.today(),
  date-format: "[day padding:none]/[month padding:none]/[year]",
  abstract: [Compte rendu technique de la recompilation croisée d'*aiohttp 3.14.5* — version exigée par le submodule Open WebUI `v0.13.5` — et de ses dépendances natives pour l'ABI Android `arm64-v8a`. Le document décrit la chaîne NDK/Chaquopy employée, la procédure reproductible (`scripts/build-aiohttp-wheels.sh`), les neuf wheels obtenus avec leurs empreintes SHA-256, les vérifications effectuées et les limites de cette tentative, réalisée dans un répertoire temporaire avant intégration sous `v0.0.82_beta`.],
  table-of-contents: outline(title: "Sommaire"),
)

#let empreinte(h) = {
  text(size: 8pt, h.slice(0, 32))
  linebreak()
  text(size: 8pt, h.slice(32))
}

= Objet et cible

Le fork épinglait *aiohttp 3.10.10* : l'index de wheels Chaquopy s'arrête à
cette version alors que `vendor/open-webui/backend/requirements-slim.txt`
demande `aiohttp==3.14.5`. Cet écart imposait quatre patchs de compatibilité
(`31`, `36`, `38` et un hunk de `20`) et masquait le risque P154 : l'amont passe
`middlewares=` aux sessions client, paramètre absent avant aiohttp 3.11.

L'objectif de cette tentative était de démontrer qu'une compilation croisée
locale permet de supprimer ce plafond. La cible est *aiohttp 3.14.5* sur
*Python 3.13 / Android API 24 / arm64-v8a*, avec toutes ses dépendances
natives.

#figure(
  caption: [Chaîne de recompilation des wheels natifs.],
)[
```mermaid
flowchart LR
  A["sdists PyPI<br/>aiohttp 3.14.5 + 4 natives"] --> B["pip wheel<br/>--no-build-isolation"]
  C["Cython 3.1.4 / 3.3.0"] --> B
  D["wrapper NDK clang API 24<br/>+ libpython3.13.so"] --> B
  B --> E["wheels android_24_arm64_v8a"]
  E --> F["APK v0.0.82_beta"]
```
]

= Chaîne utilisée

#figure(
  caption: [Composants de la compilation croisée.],
  table(
    columns: (1.4fr, 1fr, 3.2fr),
    inset: 7pt,
    table.header([Composant], [Version], [Emplacement / rôle]),
    [Python hôte], [3.13.5], [`.venv313/bin/python`, buildPython du projet (décision D7)],
    [Cython], [3.1.4 puis 3.3.0], [contraintes `requirements/cython.txt` des sdists],
    [Compilateur], [clang API 24], [`tools/ndk-cc/aarch64-linux-android24-clang`],
    [Headers Python], [3.13], [`tools/pyo3/prefix/include/python3.13`],
    [Bibliothèque], [libpython3.13.so], [`tools/pyo3/prefix/lib`, liée aux extensions],
    [Backend PEP 517], [expandvars], [requis par yarl, frozenlist et propcache],
  ),
)

Deux versions de Cython sont nécessaires : *3.1.4* pour `frozenlist`, *3.3.0*
pour `yarl` et `propcache`. Les sdists d'`aiohttp` et de `multidict` contiennent
déjà leurs sources C générées : aucun Cython n'est requis pour eux.

= Procédure reproductible

La méthode est figée dans `scripts/build-aiohttp-wheels.sh`, qui travaille
exclusivement dans l'arbre du projet (sdists et venv dans `.tmp/aiohttp/`,
résultats dans `wheels/`) et refuse de recompiler si les neuf wheels attendus
sont déjà présents. Variables essentielles :

```bash
export CC="$PROJ/tools/ndk-cc/aarch64-linux-android24-clang"
export CXX="$PROJ/tools/ndk-cc/aarch64-linux-android24-clang++"
export LDSHARED="$CC -shared"
export LDFLAGS="-L$PROJ/tools/pyo3/prefix/lib -lpython3.13 -L$PROJ/tools/ndk-cc/lib"
export CFLAGS="-fPIC -I$PROJ/tools/pyo3/prefix/include/python3.13"
export CPPFLAGS="$CFLAGS"
```

Les sdists sont téléchargés avec `pip download --no-binary :all:`, puis chaque
extension est construite avec `pip wheel --no-deps --no-build-isolation`. Les
wheels produits par setuptools portent le tag `cp313-cp313-linux_aarch64` et
des fichiers `cpython-313-aarch64-linux-gnu.so` : le script les réécrit en
`cp313-cp313-android_24_arm64_v8a` et `cpython-313-aarch64-linux-android.so`,
conformément aux wheels Android déjà versionnés.

*Point critique (CI #46076329015)* : le renommage des `.so` doit aussi
*régénérer le `RECORD`* du wheel. Si le `RECORD` conserve l'ancien nom
`linux-gnu.so`, pip ajoute à l'installation une ligne vide pour le vrai fichier
`linux-android.so` ; l'installateur Chaquopy fait alors `int('')` sur la taille
et échoue avec `ValueError: invalid literal for int() with base 10: ''`.
`scripts/normalize-aiohttp-wheel.py` recalcule les empreintes SHA-256 et les
tailles de chaque entrée ; il est appelé par `build-aiohttp-wheels.sh` et peut
aussi corriger les wheels déjà versionnés :

```bash
./scripts/build-aiohttp-wheels.sh
./scripts/normalize-aiohttp-wheel.py --in-place wheels   # correction sur place
```

Une reproduction locale de l'installation pip (`--no-compile --no-deps
--platform android_24_arm64_v8a`) montre, après correction, zéro ligne de
`RECORD` vide hors la ligne réservée au `RECORD` lui-même.

= Résultats

Cinq wheels natifs et quatre wheels purs ont été obtenus. Les empreintes sont
celles des fichiers versionnés dans `wheels/`.

#figure(
  caption: [Wheels construits ou ajoutés, avec empreinte SHA-256.]
    + [ Les cinq premiers portent des extensions compilées pour Android. ],
  table(
    columns: (1.7fr, 0.8fr, 3.1fr),
    inset: 6pt,
    table.header([Paquet], [Version], [SHA-256]),
    [aiohttp], [3.14.5], [empreinte("9c2333144edd7b3b47f83776742b980325592fc77740ff3dc8ae5a1cbb06af71")],
    [multidict], [7.2.1], [empreinte("7351a0ba2ddad747c54f84cc03ed01878b0c6290cb337d92982c963937a60bc1")],
    [yarl], [1.25.1], [empreinte("00bc2365b2de807fc89bedbea3084a9b6702848284a78666d08002c0c0ff96f5")],
    [frozenlist], [1.8.0], [empreinte("cfa587b1698ac21d62fc6596db9fb1d03a9829e40bec4e67f76657fa7fc9f415")],
    [propcache], [0.5.4], [empreinte("3ed0ec8fc357a9b63852b073cc3104080d9b4419a3df70c55587c6f3f4657ad8")],
    [aiohappyeyeballs], [2.7.1], [empreinte("9243213661e29250eb41368e5daa826fc017156c3b8a11440826b2e3ed376472")],
    [aiosignal], [1.4.0], [empreinte("053243f8b92b990551949e63930a839ff0cf0b0ebbe0597b0f3fb19e1a0fe82e")],
    [attrs], [26.1.0], [empreinte("c647aa4a12dfbad9333ca4e71fe62ddc36f4e63b2d260a37a8b83d2f043ac309")],
    [idna], [3.20], [empreinte("ab7ae7122974553370f0bdb919e1a960b2cd1bc1ef0276416d896db81c14582c")],
  ),
)

= Vérifications

- *Résolution hors ligne* : `pip install --dry-run --no-index --find-links
  wheels --platform android_24_arm64_v8a --python-version 3.13 --implementation
  cp --abi cp313 aiohttp==3.14.5` résout les *neuf paquets* sans accès réseau.
- *Architecture* : `readelf -h` indique `Machine: AArch64` pour chaque `.so`.
- *Liaison* : `readelf -d` montre `NEEDED libpython3.13.so`, `libdl.so` et
  `libc.so` (bionic) ; aucune chaîne `GLIBC` n'est présente dans les binaires.
- *Suffixes* : tous les modules sont nommés
  `cpython-313-aarch64-linux-android.so`, forme attendue par le chargeur
  Chaquopy (contrôle `check_apk.py`).

= Limites et intégration

La compilation et la résolution sont validées, mais *aucun test d'exécution sur
appareil Android* n'a encore été réalisé. L'intégration sous `v0.0.82_beta`
consiste à remplacer les pins de `requirements-min.txt`, retirer les patchs de
compatibilité (`31`, `36`, `38` et le hunk de `20`), adapter les garde-fous
`check_apk.py` et `test_p154.py`, puis reconstruire et vérifier l'APK. La
release stable `v0.0.81` reste `Latest` et n'est pas modifiée.
