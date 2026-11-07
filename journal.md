# journal.md — Journal des actions (horodatage UTC)

Format : `AAAA-MM-JJ HH:MM — action — résultat — décision/lien`.
Lire ce fichier avant chaque session ; y ajouter chaque action.

---

## 2026-11-03 — Session 1 (cadrage)

- **23:20 — Création du projet** `/root/openwebui-android` + `git init` — OK.
  Répertoire de travail : `/root` (environnement PRoot-Distro sur Termux, aarch64).

- **23:21 — Reconnaissance de l'environnement** — résultats :
  - OS : `Linux 6.17.0-PRoot-Distro aarch64` (Debian 13, conteneur proot sur téléphone)
  - JDK : OpenJDK **21.0.13** (`/usr/bin/java`) — compatible AGP récent
  - Python hôte : **3.13.5** ; Node **v24.22.2** ; git, curl, unzip présents
  - **Absents** : `javac` dans le PATH(?), `gradle`, **Android SDK** (aucun
    `$ANDROID_HOME`) → à installer
  - Ressources : 8 cœurs, 11 Go RAM (≈3,5 Go dispo), **110 Go libres** sur `/`
  - `/opt/opencode-venv` (Python outils) présent, conforme aux règles globales

- **23:22 — Vérification réseau** — `pypi.org:200`, `github.com:200`,
  `dl.google.com:200` → téléchargements SDK/Gradle/sources possibles.

- **23:25 — Tentative `pip download open-webui --no-deps`** — **ÉCHEC** :
  `open-webui` exige `Requires-Python >=3.11,<3.13` (dernières versions 0.13.x
  exclues par l'hôte 3.13.5). Aucun wheel téléchargeable avec Python 3.13.
  → **Décision D1** : obtenir le code via `git clone` du dépôt GitHub
    (ou via un python3.12 pour le wheel). Le frontend sera soit récupéré
    compilé depuis une release, soit buildé avec npm (Node 24 disponible).
  → **Décision D2** : installer **Python 3.12** sur la machine de build,
    indispensable aussi comme `buildPython` de Chaquopy (open-webui ne
    s'installera pas sous 3.13).

- **23:30 — Rédaction des fichiers de pilotage** : `AGENTS.md` (objectif,
  périmètre, décisions), `todo.md` (5 phases), `journal.md` (ce fichier) — OK.

- **23:32 — Contrainte utilisateur : « ne pas polluer l'environnement,
  tout doit être contenu dans le répertoire de travail »** —
  → **Décision D5 (isolation)** : aucune installation globale ; Android SDK dans
    `android-sdk/`, Gradle + caches dans `tools/` et `.gradle-cache/`, Python 3.12
    portable dans `tools/python312/`, venv dans `.venv/`, caches npm dans
    `.npm-cache/` — le tout sous `/root/openwebui-android/`. Les scripts
    `scripts/*.sh` exporteront `ANDROID_HOME`, `GRADLE_USER_HOME`,
    `UV_PYTHON_INSTALL_DIR`, `npm_config_cache` en conséquence.
  — **Audit de non-pollution** : `/root` vérifié, seul `openwebui-android/`
    a été créé par cette session ; rien écrit dans `~/.config`, `/opt`, `/usr`,
    `/tmp` (`pip download` échoué n'a rien produit, dossier `vendor/wheel/` vide
    → à supprimer).

- **23:33 — Mise à jour `AGENTS.md`** avec la section « Règle d'isolation » — OK.

## 2026-11-04 — Session 2 (exécution Phase 0 → 3)

- **15:50 — Python 3.12.16 portable** copié de `/opt/uv-python/` (lecture seule)
  vers `tools/python312/` — OK (D5 respectée).
- **15:55 — Wheel `open_webui-0.13.0-py3-none-any.whl`** (108 Mo) récupéré avec le
  python3.12 du projet ; extraction dans `vendor/unpacked/` :
  `open_webui/` (255 Mo dont `frontend/` **déjà compilé** — pas de build npm)
  + `requirements-slim.txt` officiel (base sans torch/onnx/chromadb).
  → **Version cible figée : Open WebUI 0.13.0** (décision D6).
- **16:05 — Analyse des imports** : torch/sentence_transformers/chromadb/
  faster_whisper sont **lazy** (dans des fonctions) ; seuls 4 imports bloquants :
  `pycrdt` (socket), `tiktoken` (retrieval), `re2` (knowledge_fs), `pydub`
  (audio — exige `audioop`, retiré de la stdlib en Python 3.13 → **cause
  réelle du cap `Requires-Python <3.13`** d'open-webui).
- **16:10 — Index de wheels Android de Chaquopy** (`https://chaquo.com/pypi-13.1/`,
  134 paquets natifs) inventorié. Disponibles en **cp313** : numpy 1.26.2,
  aiohttp 3.10.10, cryptography 42.0.8, bcrypt 3.2.2, lxml 5.3.0, Pillow 11.0.0,
  regex, psutil, cffi, greenlet, pyyaml, markupsafe, multidict, yarl, frozenlist…
  Absents (→ shim/stub/repli) : pydantic-core, jiter, tiktoken, orjson,
  pycrdt, google-re2, hiredis, protobuf…
  → **Décision D7 : cible Python 3.13** (wheels repo dispo + pydantic-core
    cross-buildable via maturin + artefact Maven `com.chaquo.python:python`
    — technique pax0r, chaquo/chaquopy#1017). Contrainte `Requires-Python <3.13`
    contournée légitimement : son motif (pydub/audioop) est neutralisé par patch P5.
- **16:20 — `requirements-min.txt`** écrit (slim − RAG − natifs absents,
  pins calés sur le dépôt Android). Conflits résolus : `joserfc` 1.7.4→1.5.0 et
  `authlib` 1.7.2→1.6.4 (chaîne joserfc≥1.6 → cryptography≥45 > plafond 42.0.8).
- **16:30 — `scripts/prepare_src.py`** : copie `src/open_webui` + 6 patchs
  (P1-P6) + `NullVectorDB` + shims `tiktoken`/`pycrdt` — voir `PATCHES.md`.
- **16:43 — ✅ TEST DE FUMÉE HÔTE RÉUSSI** (venv `.venv313`, Python 3.13.5) :
  serveur démarré, `GET /health` → `{"status":true}`, frontend servi (`/`),
  `POST /api/v1/auths/signin` → 200 + JWT. Erreur non bloquante unique :
  `No module named 'sentence_transformers'` à l'init des modèles (attendu, RAG off).
- **16:45 — Projet Android écrit** : `settings.gradle` (AGP 8.7.3),
  `app/build.gradle` (Chaquopy 17.2, `version '3.13'`, buildPython = `.venv313`,
  abiFilters arm64-v8a, `--find-links wheels/`), `AndroidManifest.xml`
  (PyApplication, permissions mic/caméra/notification/FGS, cleartext 127.0.0.1),
  `MainActivity.java` (WebView + upload + micro/caméra + retry /health),
  `ServerService.java` (foreground service), `android_main.py` (env + clé
  secrète persistée + uvicorn thread), icônes générées (Pillow).
- **16:50 — Gros téléchargements** (arrière-plan) : cmdline-tools 154 Mo,
  Gradle 8.10.2 137 Mo, NDK r27c 664 Mo — terminés.
- **16:55 — `scripts/setup-sdk.sh`** (SDK dans `android-sdk/`) et
  **`scripts/build-wheels.sh`** (rustup + cross-build pydantic-core 2.46.4 +
  jiter 0.10.0 vers `wheels/`, tags normalisés `android_24_arm64_v8a`)
  lancés en parallèle.

- **17:05 — Échec de link du cross-build** : le NDK officiel ne fournit que des
  binaires **x86_64** (`prebuilt/linux-x86_64`), non exécutables sur cette machine
  **aarch64** (exit 127).
  → **Décision D8** : wrappers `tools/ndk-cc/` = **clang/lld hôte (Termux, pré-existants,
    en lecture seule)** + **sysroot du NDK** (headers + libs bionic, archi-indépendants).
    Équivalent exact du driver `aarch64-linux-android24-clang` du NDK. llvm-ar (hôte)
    pour les archives. Relance du build.

- **18:20 — Cross-build des wheels Rust réussi** ✅ : `pydantic_core-2.46.4`,
  `jiter-0.10.0`, `uuid_utils-0.12.0` (abi3), `orjson-3.11.9`, `rpds_py-2026.9.1`
  — tous en `android_24_arm64_v8a`, générés par `scripts/build-wheels.sh`.
- **18:30 — Itérations de résolution pip Chaquopy** (corrections `requirements-min.txt`) :
  `argon2-cffi` 20.1.0→23.1.0 (versions Android dispo) ; `uuid-utils` (Rust,
  requis par langchain-core) et `orjson`/`rpds-py` (requis par langsmith/
  jsonschema) ajoutés au cross-build. **Tâche `installDebugPythonRequirements`
  réussie** (toutes les dépendances Android résolues).
- **18:35 — JDK portable** : le JDK système est un **JRE sans javac** →
  **Décision D10** : JDK Temurin 21 téléchargé dans `tools/jdk/`, `JAVA_HOME`
  ancré dans `env.sh`/`build.sh`.
- **18:45 — aapt2/zipalign x86_64** : les outils Android officiels sont des
  ELF x86-64, inécutables sur la machine aarch64 (« Daemon startup failed »).
  → **Décision D9** : `qemu-user-static` (Debian 12, extrait dans `tools/qemu/`)
    + mini-sysroot x86_64 (`libc6`+`libgcc-s1` Debian 13, avec liens `lib64`).
    Wrappers `tools/wrappers/aapt2` (branché par `android.aapt2FromMavenOverride`)
    et `tools/wrappers/zipalign` (remplace celui des build-tools, original en
    `.bin`). Tests : `aapt2 version` et `zipalign` OK sous qemu.
- **20:02 — 🎉 BUILD SUCCESSFUL** — `dist/app-debug.apk` (193 Mo,
  `org.openwebui.android` v0.1.0, minSdk 24, arm64-v8a). Contenu vérifié :
  `libpython3.13.so` + runtime Chaquopy en libs natives, `app.imy` 110 Mo
  (open_webui patché + frontend), `requirements-common.imy` 71 Mo (dépendances).

## 2026-11-06 — Session 3 (retour de test appareil)

- **Test appareil (Phase 4)** : « accès microphone refusé et accès aux appareils
  multimédia refusé » dans l'UI (dictée/vidéo).
  → **Cause** : `MainActivity` n'avait pas les **permissions Android au runtime**
    (RECORD_AUDIO / CAMERA) — la WebView exige que l'app les détienne avant
    d'accorder les accès web (`getUserMedia`). Deux manques identifiés via la
    doc (Zoom SDK WebView, Microsoft ACS, Hotwire Android) :
    1. pas de `requestPermissions()` au lancement ;
    2. `MODIFY_AUDIO_SETTINGS` absent du manifeste (la chaîne audio Chromium
       échoue « Unable to select communication device » même avec RECORD_AUDIO) ;
    3. `onPermissionRequest` accordait `getResources()` en bloc (contre la
       recommandation Android).
  → **Correctifs** : manifeste + `MODIFY_AUDIO_SETTINGS` + `uses-feature`
    camera/microphone `required=false` ; `MainActivity` demande micro/caméra/
    notifications au lancement, et `onPermissionRequest` n'accorde que
    `RESOURCE_AUDIO_CAPTURE`/`RESOURCE_VIDEO_CAPTURE` si la permission système
    correspondante est détenue (sinon prompt système + refus propre, l'utilisateur
    réessaie). `onRequestPermissionsResult` relance le chargement.
  → Rebuild `dist/app-debug.apk` (installation en surimpression possible,
    même signature debug).

- **Suite du test : « No module named 'faster_whisper' »** — la dictée tombait
  sur le STT local (retiré : chaîne C++ ctranslate2 inembarquable).
  → **Décision D11 : dictée native**. Le mode STT « web » d'Open WebUI utilise
    l'API `SpeechRecognition` du navigateur ; un **shim JS** injecté dans la
    WebView (`SPEECH_POLYFILL`, `MainActivity`) la délègue au **SpeechRecognizer
    d'Android** via `AndroidSpeech.java` (`addJavascriptInterface`), souvent
    disponible **hors-ligne**. Contrat frontend respecté : `onresult` (résultats
    avec `isFinal` + `[0].transcript`), `onend`, `onerror` (codes standard).
  → Correctifs : `AndroidSpeech.java` + polyfill JS + `AUDIO_STT_ENGINE=web`
    (P8 config.py) + forçage en base si déjà semée à vide
    (`_force_web_stt()` dans `android_main.py`, SQLite direct avant démarrage).
  → **P7a-c** : `faster-whisper`/`transformers`/`soundfile+torch` en try/except
    → HTTP 503 explicite (fini les `ModuleNotFoundError` bruts).
  → Test de fumée hôte revalidé (`/health` OK), rebuild APK lancé.

## 2026-11-07 — Session 4 (SearXNG embarqué + taille APK)

- **Anomalie de taille APK** (193 → 303 Mo) : la packaging **incrémentale** d'AGP
  (zipflinger) réutilise l'APK précédent et append les entrées modifiées —
  `app.imy` (110 Mo) étant réécrit à chaque patch, ses anciennes copies
  s'accumulaient (7 EOCD, ~110 Mo d'entrées orphelines). **Correctif** :
  `build.sh` supprime `app/build/{outputs,intermediates}/apk` avant packaging.
  → APK vérifié (signature OK), retour à **193 Mo**.
- **Recherche web** : `ddgs` ajouté puis **retiré** — sa dépendance `primp`
  (Rust) tire `aws-lc-sys` qui refuse le cross-build en API 24
  (`getentropy` = API 28+). Remplacé par SearXNG embarqué (demande utilisateur).
- **Décision D12 : SearXNG embarqué**, vendor **figé sur `a30b2d4749`**
  (2026-08-28, dernier état avant la migration `curl_cffi` — seuls
  `fasttext-predict`/`uvloop`/`curl_cffi` étaient natifs et sont évités) ;
  seul `msgspec` (C, setuptools) reste à cross-builder :
  wrapper clang + en-têtes du **Python Android cible** (`--include-dirs`),
  `libunwind.a` (copie locale) pour le link, suffixe `.so` `-gnu` → `-android`
  (sinon le module n'est pas trouvé par l'import Android), et version
  `0.0.0` → `0.21.1` corrigée (`scripts/fix-wheel-version.py`, setuptools_scm
  sans git). → wheel `msgspec-0.21.1-cp313-android_24_arm64_v8a` ✅.
- **Provider « embedded-searxng »** : P9 (dispatch `search_web()` →
  `http://127.0.0.1:8888/search?q=<query>`) + P10 (ajout à la liste du dropdown,
  libellé = valeur brute) + SearXNG servi sur `127.0.0.1:8888` (thread wsgiref,
  réglages générés avec clé secrète propre à l'appareil, JSON activé).
  Moteur par défaut : `web.search.engine = 'embedded-searxng'` (forcé en base si vide).
- **Test de fumée hôte (via `android_main`)** ✅ : `/health` OK +
  `http://127.0.0.1:8888/search?format=json` répond en JSON (résultats vides
  derrière une IP de datacenter : CAPTCHA/timeouts des moteurs amont — attendu,
  bien meilleur depuis l'IP résidentielle du téléphone).

- **Correctif nom** : la coquille « embeded » → **`embedded-searxng`** corrigée
  partout (P9/P10, android_main, docs). Migration de l'ancienne valeur en base
  (`_force_config_value(..., also_replace=('embeded-searxng',))`) pour les
  appareils ayant déjà l'ancien nom forcé.
- **« Je ne le vois pas dans la liste »** : la liste des providers n'existe
  qu'**en un seul exemplaire** dans le bundle (`nodes/2.DwSK4ZlF.js`) et le patch
  y est bien présent → cause = **ancien APK installé ou cache WebView périmé**.
  Consigne : installer le nouvel APK, puis forcer l'arrêt de l'app et vider son
  cache avant de rouvrir les réglages.
- **Décision D13 : purge auto du cache WebView à chaque version d'APK** (reprise
  de la suggestion utilisateur) : `MainActivity` compare le `versionCode` courant
  à celui mémorisé (SharedPreferences) et appelle `webView.clearCache(true)` au
  changement ; `build.sh` incrémente `version_code` à chaque build et le passe
  via `-Pvcode` (fini les listes/menus périmés après mise à jour).
  `versionName` → 0.2.0.

## 2026-11-07 — Session 5 (recherche web, voix, diagnostic « pas d'internet »)

- **« L'IA dit qu'elle n'a pas d'accès internet » + aucun outil web** : deux
  causes distinctes. (a) Les outils `search_web`/`fetch_url` d'Open WebUI ne sont
  pas attachés à l'assistant par défaut (à activer dans Espace de travail →
  Outils) ; (b) le endpoint `/process/web/search` échouait dans mes tests.
- **Diagnostic « Something went wrong »** : un **ancien serveur de fumée
  (09:39) resté vivant** servait encore l'API avec le code pré-patch (mon
  `fuser -k` échoue silencieusement sous proot : le mapping socket→PID casse).
  Les deux processus écrivaient dans le même log — d'où les traces « anciennes »
  (message sans le nom du moteur, n° de ligne décalés). Nettoyage par PID
  explicite. **Le code neuf fonctionne** : `POST /process/web/search` →
  vrais résultats via `embedded-searxng` (futura-sciences, frandroid…).
  → Durcissements : P9b (le message d'erreur porte désormais le moteur lu),
    alias `embeded-searxng` accepté dans le dispatch, et leçon consignée :
    **toujours tuer par PID, jamais par fuser/pkill sous proot**.
- **Reconnaissance vocale « no speech »** : deux correctifs cumulés —
  (a) `AndroidSpeech` relance silencieusement l'écoute sur NO_MATCH/TIMEOUT
  (3 essais max) avant de conclure ; (b) le shim JS remplace désormais le flux
  `getUserMedia` audio par un **flux silencieux** quand le STT est en mode « web »
  (le `MediaRecorder` de l'UI monopolisait le micro au détriment du
  SpeechRecognizer natif ; le blob enregistré est de toute façon ignoré dans ce
  mode). Mode STT distant : le flux réel est conservé.
- **Question utilisateur : outil Typst pour compiler du PDF** → voir décision D14.
- **⚠️ Violation d'isolation (D5) signalée par l'utilisateur** : `rustup-init`
  avait ajouté une ligne `. "$CARGO_HOME/env"` dans `~/.profile` (utilisateur :
  ligne commentée à la main), et un `~/.cargo` parasite s'était créé (00:04) —
  cache cargo de mon `pip download` manuel de `primp` lancé **sans** `CARGO_HOME`
  (build de dépendances de maturin). → **Nettoyage** : ligne supprimée de
  `~/.profile` (fichier restauré), `~/.cargo` supprimé, audit maison revérifié
  (rien d'autre modifié hors projet). → **Garde-fous** : `--no-modify-path`
  ajouté au rustup-init de `build-wheels.sh`, et `env.sh` exporte désormais
  `CARGO_HOME`/`RUSTUP_HOME` dans le projet. Règle rappelée : toute commande
  manuelle Rust/cargo/pip doit passer par `source scripts/env.sh` d'abord.
- **Outil Typst (D14) implémenté** : `typst-0.15.2` cross-buildé
  (`cp39-abi3-android_24_arm64_v8a`, 7e wheel), outil `compile_typst` ajouté à
  `tools/builtin.py` (P11) + registration dans `utils/tools.py` (P11a/P11b) :
  compile `.typ` → PDF, l'enregistre dans les fichiers de l'utilisateur
  (FileModel/Storage) et retourne un `file_id` affichable via `display_file`.
  20 opérations de préparation, syntaxe validée.

## 2026-11-07 — Session 6 (RAG : clarifications produit → architecture finale)

- **Clarifications utilisateur successives** (les deux font foi) :
  1. « le RAG est possible mais pas de moteur de RAG local ; un service tiers est
     possible » ;
  2. « la base de RAG peut être locale, seul le calcul d'embedding est distant,
     la plateforme ne le permet pas ».
  → **Architecture retenue (D15)** : embeddings **obligatoirement distants**
    (API openai/ollama/azure — configurables dans Admin → Documents) +
    **base vectorielle LOCALE** embarquée.
- **Décision D15 : `LocalVectorDB`** — nouveau backend maison
  (`retrieval/vector/dbs/local.py`) : **SQLite + numpy**, force brute vectorisée
  (exacte, confortable jusqu'à ~10⁵ fragments), score cosinus ramené dans [0,1]
  (convention chroma), filtres `$eq`/`$in` via `metadata_matches_filter` amont.
  `VECTOR_DB=local` par défaut (P1/P2/P3 mis à jour), `VECTOR_DB=none` = off.
  Zéro nouvelle dépendance native. **Tests unitaires verts** (search, filtres,
  query/get, upsert, delete, reset) + création de la base au démarrage ✔.
- **Clients de bases distantes retirés** (qdrant/elasticsearch/opensearch/
  weaviate) : inutiles avec la base locale, et sources de blocages Android
  (qdrant-client 1.13+ exige numpy≥2.1 — plafond 1.26.2 ; 1.12.1 exige
  `grpcio-tools` introuvable ; weaviate tire protobuf). Le code amont reste
  compatible si on les réactive plus tard.
- **Mécanisme `data/openwebui.env`** (android_main) : variables `KEY=VALUE`
  chargées au démarrage (override possible sans rebuild) — utile pour
  `VECTOR_DB`, `RAG_*`, etc.

## 2026-11-07 — Session 7 (documentation Typst + reproductibilité + git)

- **`docs/maintenance.typ` / `.pdf`** (18 p.) : guide de maintenance complet —
  architecture, portage (actions effectuées, cross-build, pièges), ajouts,
  patchs P1-P11, **procédures de mise à jour d'Open WebUI et des composants**,
  build, configuration appareil, dépannage, isolation. Thème `ilm 2.1.0` +
  helpers canoniques + diagrammes `merman` ; cache de paquets Typst ancré dans
  le projet (isolation). Format de date corrigé (JJ/MM/AAAA, `date-format`).
- **Décision D16 : reproductibilité totale** — `scripts/setup-env.sh` reconstruit
  l'environnement complet à partir du dépôt seul (10 étapes idempotentes :
  Python 3.12, venv 3.13, JDK, SDK, Gradle, NDK, Rust `--no-modify-path`, qemu +
  sysroot, sources vendor avec pins, wheels cross-buildés) + `--check` (audit)
  et `--build`. Doc associée `docs/environnement.typ` / `.pdf` (9 p.).
  Vérifié : audit 14/14 OK sur l'environnement courant.
- **Dépôt git** : import initial complet — sources, scripts, docs, wheels natifs,
  wrappers de compilation (`tools/ndk-cc`, `tools/wrappers` avec `libunwind.a`),
  APK non versionné (rebuildable ; `git add -f` possible) ; SDK/JDK/NDK/Rust/
  qemu/caches exclus car **reconstruits par `setup-env.sh`**.

## 2026-11-07 — Session 8 (outils internet de l'assistant)

- **Retour appareil** : l'inventaire d'outils de l'assistant (DeepSeek) contient
  `compile_typst` ✔ (outil Typst opérationnel sur l'appareil) mais **aucun outil
  internet** (`search_web`/`fetch_url` absents). Diagnostic : le filtre
  `features.get('web_search')` dans `get_builtin_tools` est le **seul sans défaut
  True** — un modèle dont les métadonnées ne déclarent pas la capacité est
  évalué falsy et perd les outils web, alors que `web.search.enable` est actif.
- **Décision D17 / patch P12** : `features.get('web_search', True)` — les outils
  internet sont exposés dès que la recherche web est activée globalement (et la
  permission utilisateur satisfaite). Un refus *explicite* par le modèle reste
  respecté. `search_web` utilise le moteur `embedded-searxng` ; `fetch_url` est
  l'équivalent « webfetch » (lecture de page) — aucun nouvel outil à ajouter.
- Smoke OK, rebuild APK, commit.
- **Règle ajoutée aux règles de travail (AGENTS.md)** : la *documentation Typst
  doit être toujours maintenue* — tout changement du projet y est répercuté,
  suivi de la recompilation des PDF ; c'est un livrable au même titre que l'APK.
  Appliquée immédiatement : `docs/maintenance.typ` complété avec P12.

## 2026-11-07 — Session 9 (performance de démarrage)

- **Retour utilisateur** : « le démarrage est maintenant très long », puis
  « ça bloque sur démarrage du serveur Open WebUI » — et « avant tes dernières
  modifications le temps était correct » → régression introduite par les
  dernières livraisons, pas par le code amont.
- **Mesures** (import de `open_webui.main` profilé avec `-X importtime`, sur le
  CPU de l'appareil) : **35,5 s** à l'import ; centres de coût : `env` 2,2 s,
  `ldap3` 1,7 s, `boto3` 1,4 s, `black` 0,9 s, `mcp_types` ~0,9 s. + contention
  CPU : SearXNG importait **en parallèle** du démarrage d'Open WebUI.
  + le frontend embarqué (248 Mo) alourdissait l'extraction à chaque MAJ.
- **Correctifs** :
  - P13 : frontend allégé de **169 Mo** (source maps, `pyodide/`, `wasm/` —
    ML navigateur interdit par la règle « pas de calcul local »). 248 → 85 Mo ;
  - P14 : imports différés (`ldap3` dans les fonctions LDAP, `black` dans
    `format_code`, `MCPClient` dans sa branche) : import **35,5 → 32,1 s** ;
  - `android_main` : `_warm_up_then_searxng` démarre SearXNG **après** la
    réponse de `/health` (fin de contention) ;
  - `MainActivity` + `android_main._set_status` : l'écran de chargement affiche
    l'étape réelle (`data/startup-status.txt`) — diagnostic intégré.
- **Résultat mesuré** : `/health` en **29 s** (vs ~35 s + contention avant),
  SearXNG se réchauffe en arrière-plan, APK attendu ≈ 130 Mo.
- **Suite (retour appareil)** : blocage persistant sur « Démarrage du serveur
  Open WebUI… ». Cause racine : le frontend (85 Mo, des milliers de fichiers)
  vit dans le paquet Python → **extraction Chaquopy pendant l'import du
  serveur**, invisible et sans retour.
- **Décision D18 / patch P15** : le frontend sort des assets Python
  (`src-assets/frontend/` = *assets Android*) — `MainActivity` l'extrait
  **une fois par versionCode** dans `filesDir/frontend` (avec message
  « Préparation de l'interface »), `FRONTEND_BUILD_DIR` y pointe.
  Compléments : compteur de secondes sur l'écran de démarrage, **erreurs
  d'import écrites dans `startup-status.txt`** (un blocage devient lisible),
  retries portés à 15 min, et premier lancement documenté.
- **Résultat** : import serveur **35,5 s → 11 s** mesuré, `src/open_webui`
  264 Mo → 9,9 Mo, APK en cours de build (assets compressés).
- **Suite (demande utilisateur)** : « je voudrais une barre de progression du
  démarrage avec commentaire et message d'erreur au cas où ».
  → **Écran de démarrage complet** : `ProgressBar` horizontale (0-100),
    pourcentage **réel** pendant l'extraction des assets (fichiers comptés puis
    copiés avec mise à jour tous les 100), étapes Python transmises au format
    `PCT|message` via `data/startup-status.txt` (45 % démarrage serveur,
    85 % recherche web, 100 % prêt), commentaires d'étape + compteur de
    secondes, et **zone d'erreur rouge** (`Erreur au démarrage : …`) dès qu'une
    étape échoue — un blocage devient visible et lisible, jamais silencieux.
    Reprises : retry porté à 15 min, échec d'extraction signalé lui aussi.
- **Retour appareil (la barre d'erreur fonctionne)** : « erreur import
  migration/env.py » affichée en rouge à l'écran de démarrage.
  → **Cause** : Chaquopy compile les `.py` en `.pyc` et **retire les sources**
    de l'APK ; or Alembic *charge* `migrations/env.py` et `versions/*.py` depuis
    le disque (`load_python_file`). Les smoke tests hôte ne le voyaient pas
    (sources présentes).
  → **Correctif P16** : `open_webui/migrations` et `migrations/versions` marqués
    paquets (`__init__.py`) + `extractPackages` dans `build.gradle` — Chaquopy
    conserve alors les `.py` pour ces paquets. Symptôme ajouté au
    dépannage de `maintenance.pdf`.
- **Retour appareil** : « dlopen failed `_uuid_utils.abi3.so` ».
  → **Cause** (prouvée par `readelf`/`nm`) : les wheels **abi3** (PyO3) ne lient
    PAS `libpython` — 95 symboles `Py*` indéfinis, aucune `DT_NEEDED` sur
    libpython → dlopen impossible sur Android (sur desktop, les symboles se
    résolvent à l'exécution). `pydantic_core` (non-abi3) liait libpython et
    chargeait bien. `typst` (abi3 aussi) était concerné au même titre.
  → **Correctif** : `build-wheels.sh` génère un **`PYO3_CONFIG_FILE`** avec
    `suppress_build_script_link_lines=false` (mécanisme officiel PyO3) +
    `CARGO_TARGET_..._RUSTFLAGS` en renfort. Les deux wheels ont été
    rebâtis : `readelf -d` confirme `NEEDED libpython3.13.so` ✅.
    Plan B documenté : `patchelf --add-needed` (installé dans le venv hôte).
    Vérification systématique ajoutée au dépannage (`readelf | grep NEEDED`).
- **Suite : « toujours la même erreur »** après le build précédent.
  → **Cause** (prouvée) : la tâche pip de Chaquopy ne suit que le *fichier*
    de requirements — un wheel **reconstruit sous le même nom/version**
    n'est jamais réinstallé. Les tâches Python étaient `UP-TO-DATE` et l'APK
    contenait l'ancien `_uuid_utils.abi3.so` (sans libpython). 
  → **Correctif** : `build.sh` supprime désormais `app/build/python`,
    `app/build/generated` et `intermediates/assets` avant chaque build
    (réinstallation pip + régénération des assets forcées), et le `.so`
    empaqueté est vérifié par `readelf` avant livraison.

## Décisions cumulées (suite)

| # | Décision | Motif |
|---|----------|-------|
| D1 | Sources Open WebUI via `git clone` (pas le wheel PyPI) | hôte Python 3.13 incompatible avec `Requires-Python <3.13` |
| D2 | Installer Python 3.12 (buildPython Chaquopy) | open-webui `>=3.11,<3.13` |
| D3 | Chaquopy 17.x, ABI arm64-v8a seul | voir AGENTS.md §Décisions techniques |
| D4 | Suppression RAG = stub `open_webui.retrieval` no-RAG + retrait des dépendances lourdes | demande explicite : « enlevant juste le RAG » |
| D5 | **Isolation totale** : tout sous `openwebui-android/` (SDK, Gradle, Python 3.12, caches, venv), aucune installation globale | contrainte utilisateur : ne pas polluer l'environnement |
| D6 | Version cible : **Open WebUI 0.13.0** (wheel PyPI, frontend déjà compilé dedans) | évite un build npm ; `requirements-slim.txt` officiel comme base |
| D7 | Cible Android : **Python 3.13** + Chaquopy 17.2 ; `pydantic-core`/`jiter` cross-buildés (maturin + NDK + Python Maven) | wheels repo cp313 dispo ; cap `<3.13` d'open-webui dû à pydub/audioop, neutralisé (P5) |
| D8 | Cross-compilation Rust : **clang/lld hôte (Termux, lecture seule) + sysroot du NDK** via wrappers `tools/ndk-cc/` | NDK officiel = binaires x86_64 inécutables sur aarch64 |
| D9 | Outils Android x86_64 (aapt2, zipalign) exécutés via **qemu-user-static** + mini-sysroot (`tools/qemu/`), wrappers branchés par `aapt2FromMavenOverride` | idem : build-tools/maven = x86_64 |
| D10 | **JDK Temurin 21 portable** dans `tools/jdk/` (`JAVA_HOME` dans les scripts) | le JDK système est un JRE sans `javac` |
| D11 | Dictée native via shim `SpeechRecognition` → `SpeechRecognizer` Android + arbitrage micro (flux silencieux en mode web) | STT local inembarquable ; « no speech » causé par le conflit MediaRecorder/reconnaissance |
| D12 | SearXNG embarqué (commit `a30b2d4749`, pré-curl_cffi), provider `embedded-searxng` | demande utilisateur ; seul `msgspec` à cross-builder |
| D13 | Purge auto du cache WebView à chaque `versionCode` | fini les UI périmées après mise à jour |
| D14 | **Outil Typst** : `typst-py` (compilateur Typst en lib Rust, maturin) cross-buildé + outil Open WebUI `compile_typst` (`.typ` → PDF) via un patch `tools/builtin.py` | demande utilisateur ; pipeline Rust déjà rodé (msgspec) |
| D15 | **RAG final** : embeddings distants (API) + `LocalVectorDB` (SQLite + numpy, force brute) en stockage local — `VECTOR_DB=local` par défaut | plateforme = pas de calcul d'embedding local ; la base vectorielle peut être locale ; clients distants (qdrant…) retirés (blocages numpy/grpcio-tools/protobuf) |
| D16 | **Reproductibilité** : `scripts/setup-env.sh` (+ `docs/environnement.pdf`) reconstruit l'environnement complet depuis le dépôt git seul ; ne versionner que sources/scripts/docs/wheels/wrappers | reprendre le projet sur machine neuve sans doc perdue ni environnement fantôme |

## 2026-11-07 — Leçon majeure : serveurs zombies et tests faussés (incidents #7-#8)

**Ce qui s'est passé** : lors du diagnostic « écran blanc après la barre 100 % », toute une
série de tests (404 sur `/_app/**.js`, traces invisibles, fichiers introuvables) ont fait
croire à un bug de `SPAStaticFiles`. Vraie cause : `fuser`/`pkill` ne marchent pas sous proot
et les motifs `ps aux | grep '[.]venv313/bin/python'` se tuaient parfois eux-mêmes → **des
serveurs périmés restaient vivants sur 8080** et répondaient aux tests avec l'ancien code.
L'appareil Android, lui, tournait avec le code courant.

**Règles de test désormais obligatoires** :
1. Tuer par PID avec motif insécable : `pgrep -f 'venv313/bin/pyth[o]n'` (classe de
   caractères : ne matche pas la commande de kill elle-même) ; jamais `pkill`/`fuser`.
2. Vérifier l'extinction : `pgrep -f "$PAT" | wc -l` doit valoir 0.
3. Un seul serveur par test ; attendre `/health` en boucle (3 s, ~40 s de démarrage) avant
   tout test — jamais de `sleep` fixe trop court.
4. Ne jamais inférer un bug applicatif d'un test sans identité de serveur confirmée.

**Validé sur serveur propre** : `/_app/immutable/entry/start.BHzHmkW5.js` → 200
(`text/javascript`), `/assets/welcome.mp4` → 200, `/favicon.png` → 200. Le service du
frontend est sain ; l'écran blanc est un phénomène propre à la WebView de l'appareil.

**Correctifs embarqués (v14)** pour le rendre visible et le résoudre :
- `MainActivity` : `onReceivedError` + `checkLogs()` → toute erreur de chargement ou console
  JS s'affiche dans un écran de diagnostic au lieu d'un blanc.
- Barre de progression temps réel (estimation 90 × 3 s) : ne reste plus figée.
- P15 : premier lancement migre les données créées dans la mauvaise arborescence.
- P16 : purge des services/pids orphelins et `System.exit` en `onDestroy` (sécurité).

## 2026-11-07 — Recherche web absente de l'inventaire d'outils (v15)

**Symptôme** : l'UI fonctionne (v14 OK) mais le modèle déclare n'avoir aucun outil de
recherche web ; `search_web`/`fetch_url` absents de la liste function-calling.

**Cause** : `ENABLE_WEB_SEARCH` défaut à `'False'` en amont → la clé `web.search.enable`
est éteinte, ce qui coupe `get_builtin_tools` (outils) *et* `chat_web_search_handler`
(pipeline du chat, middleware ligne 2412). P12 n'avait débloqué qu'une des cinq
conditions du gate ; les autres (capacités modèle, permissions) défautent à `True`.

**Correctif (android_main, v15)** : `os.environ.setdefault('ENABLE_WEB_SEARCH', 'true')`
+ `_force_config_value(data_dir, 'web.search.enable', True)` (migration des DB existantes
où la clé est stockée à `false`). Effet de bord assumé : une désactivation manuelle dans
l'admin est réactivée au redémarrage — la recherche web est une fonctionnalité centrale.

**Validé hôte** : `get_builtin_tools` avec un modèle sans métadonnées (cas DeepSeek via
API) retourne 31 outils dont `search_web` et `fetch_url`.

## 2026-11-07 — Recherche web : toujours absente après v15 (v16, P18)

**Symptôme** : malgré `web.search.enable=true` (v15), le modèle déclare toujours
n'avoir aucun outil web.

**Cause** : deux autres filtres du gate de `get_builtin_tools` valent *false explicite* :
- `model.info.meta.capabilities.web_search` et `builtinTools.web_search` — l'UI
  *Admin → Modèles* écrit ces valeurs dans la fiche modèle, souvent à `false` pour
  les API tierces (DeepSeek) ;
- `features.web_search` — le frontend envoie `false` dans la requête de chat quand
  le globe n'est pas actionné. P12 ne traitait que la clé *absente* (`.get(..., True)`).

**Correctif P18** (`utils/tools.py` via `prepare_src.py`) : gate réduit à
`web.search.enable` + permission utilisateur — `search_web`/`fetch_url` sont exposés
sans condition de modèle ni de toggle. Rationale : la recherche web est une
fonctionnalité centrale de l'app ; c'est au modèle de décider d'appeler l'outil.
Le pipeline automatique (globe) reste conditionné au toggle (comportement amont).

**Validé hôte** : scénario hostile (`capabilities.web_search=false`,
`builtinTools.web_search=false`, `features={web_search: false}`) → 31 outils,
`search_web` et `fetch_url` présents.

## 2026-11-07 — Publication GitHub (FredSources/Openwebui_Android)

- Dépôt public `git@github.com:FredSources/Openwebui_Android.git`, clé RSA 4096
  dans `~/.ssh/id_rsa` (publique ajoutée au compte GitHub par l'utilisateur).
- **Purge de l'historique** : les APK (`dist/`, ~148 Mo × 6 versions) étaient
  committés en force — GitHub refuse > 100 Mo/fichier. `git filter-branch
  --index-filter 'git rm -r --cached --ignore-unmatch dist'` + gc :
  dépôt 1,6 Go → 93 Mo. Convention changée : l'APK n'est *jamais* versionné
  (il est rebuildable par `build.sh`) — docs/environnement.typ à jour.

## 2026-11-07 — CI/CD GitHub Actions + correction de nommage

**Nommage** : le projet était décrit « sans RAG » (README, AGENTS.md) — faux depuis
D15 : le RAG est actif avec `LocalVectorDB` (vecteurs locaux SQLite+numpy) et des
**embeddings distants par API** (la plateforme interdit le calcul d'embedding local).
Corrigé : « APK autonome avec RAG » dans README, diagramme AGENTS.md, PATCHES.md.

**CI/CD** (`.github/workflows/build-apk.yml`) : build debug + release
**uniquement au push d'un tag `v*`** (souhait utilisateur — pas de build à chaque
commit), Release GitHub avec les APK attachés :
- runner x86_64 : la surcharge aapt2/qemu est retirée (`sed` sur gradle.properties)
  et `build.sh`/`env.sh` acceptent un JDK système si `tools/jdk` (aarch64) est absent ;
- `.venv313` recréé avec CPython 3.13 (chemin attendu par `buildPython`) ;
- SearXNG cloné au commit figé ; wheels Rust déjà committés ;
- `build.sh` accepte plusieurs tâches Gradle (debug+release, même versionCode) ;
- versionCode CI = 10000 + run number ; signature release via secrets GitHub
  (`KEYSTORE_BASE64`, `KEYSTORE_PASSWORD`, `KEY_ALIAS`, `KEY_PASSWORD`), repli
  clé debug si absents.

**Keystore release** : générée dans `~/.openwebui-release/` (PKCS12, RSA 4096,
alias `openwebui-release`, 10 000 jours) — **hors du dépôt**, `chmod 600`, avec
`CREDENTIALS.txt` (mots de passe + procédure de sauvegarde). Empreinte certificat
SHA-256 `7F:A2:58:45:…:66:DC:34:E4`. À injecter en secrets GitHub pour la CI.

## 2026-11-07 — Version 1.0.0 (tag v1.0.0)

`versionName` passé à `1.0.0` (build.gradle). Tag `v1.0.0` poussé : première
exécution de la CI « build sur tag » → Release GitHub avec APK debug + release.
Les secrets de signature (`KEYSTORE_*`) n'étant pas encore posés, l'APK release
est signé avec la clé debug (re-signable dès que les secrets sont injectés).

## 2026-11-07 — CI : échec v1.0.0 diagnostiqué et corrigé

**Échec du premier build tag `v1.0.0`** : `prepare_src.py` exigeait
`vendor/unpacked/open_webui` (wheel amont) — or `vendor/` n'est pas versionné et
aucun script ne le reconstruisait en CI (`fetch_src.sh` était référencé mais
n'existait pas). Correctifs :
- `scripts/fetch_src.sh` créé (télécharge le wheel `open-webui==0.13.0` depuis
  PyPI et l'extrait dans `vendor/unpacked/`) ;
- workflow : étape « Sources Open WebUI amont » ajoutée ;
- `build.sh` : création de `.tmp`/`.pip-cache` absents d'un checkout neuf.

**Signature cohérente dès la 1.0.0** : les secrets `KEYSTORE_*` sont injectés AVANT
le re-tag, pour que la première release publique sorte déjà signée avec la clé de
release définitive (jamais la clé debug) — sinon Android refuserait les mises à jour
ultérieures (signature différente).

## Points ouverts

- Version Open WebUI cible à figer (release stable recommandée).
- Paquets pip natifs indisponibles dans l'index Chaquopy → à inventorier dès la
  Phase 1 (risque principal du projet).
- `javac` absent du PATH : vérifier que le JDK 21 est complet (`-jdk` pas `-jre`).
