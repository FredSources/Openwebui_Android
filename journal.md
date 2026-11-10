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

**Résultat** : la run `v1.0.0` aboutit (4 min 39 s) après un second correctif —
`fetch_src.sh` doit passer `--ignore-requires-python` (le wheel amont porte
`Requires-Python <3.13`, cap pydub/audioop de D7). Release `v1.0.0` publiée avec
`app-debug.apk` + `app-release.apk`, ce dernier signé avec la clé de release
(branche keystore prise, sans repli debug).

## 2026-11-07 — APK renommés `OpenWebUI_Android-<version>-<variante>.apk`

`build.sh` nomme désormais les livrables de façon explicite
(`OpenWebUI_Android-1.0.0-release.apk`) au lieu de `app-release.apk` — build local
et CI identiques ; vérification CI ajustée. La release `v1.0.0` est re-publée
(mêmes sources taggées, nommage explicite) — personne n'avait encore téléchargé.

## 2026-11-07 — v1.0.1 : isolation stricte de l'espace applicatif

Demande utilisateur : vérifier que TOUS les fichiers sont écrits dans
`/data/data/org.openwebui.android`. Audit : Java utilisait déjà `getFilesDir()`,
mais Python dépendait d'un `HOME` implicite (Chaquopy) et `TMPDIR`/caches n'étaient
pas garantis. Correctif : `MainActivity` passe `getFilesDir()` à `start_server` ;
`_prepare_env` force `HOME`, `TMPDIR`, `XDG_CACHE_HOME` dans l'espace privé
(`<files>/data`, `<files>/tmp`, `<files>/cache`) — validé par test. Documenté dans
`docs/maintenance.typ` (table des fichiers).

À suivre : le bug de démarrage de l'appli signalé par l'utilisateur (le serveur de
test masquait le vrai démarrage) reste à observer sur v1.0.1 — l'écran d'erreur
affiche désormais la cause exacte.

## 2026-11-07 — v1.0.2 : LE bug de l'écran figé — dossier `_app/` supprimé du packaging

**Symptôme réel** (capturé en direct par sondage réseau, l'appli partage le réseau
avec Termux) : serveur OK (`/health`, `/api/config`, index.html → 200) mais **tout
`/_app/**` en 404** → les JS de l'UI ne chargent pas → écran de chargement « oi »
figé. Le serveur de test masquait le bug (il servait le frontend depuis le disque).

**Cause racine (P20)** : le motif `ignoreAssetsPattern` PAR DÉFAUT d'Android
(AAPT/AGP) contient `<dir>_*` — tout *dossier* d'assets dont le nom commence par
`_` est **supprimé silencieusement** du packaging. Le frontend SvelteKit stocke
tous ses `.js` dans `_app/` → les 927 fichiers disparaissaient de l'APK (vérifié :
l'APK v1.0.1 contient 3880 fichiers frontend, zéro `_app/`). Les *fichiers* à
underscore (`_bz2.so`) survivent — d'où la subtilité.

**Correctif** : `androidResources { ignoreAssetsPattern }` personnalisé dans
`build.gradle`, identique au défaut SANS `<dir>_*`. Validé : les 927 fichiers
sont de retour dans les assets fusionnés. **Garde-fou CI** : l'étape de vérification
compte les `assets/frontend/_app/` dans l'APK et rejette tout APK < 500 fichiers.

Leçons : (1) vérifier le CONTENU de l'APK livré, pas seulement son build ;
(2) tester avec l'environnement réel de l'appli, jamais un serveur parallèle.

## 2026-11-07 — v1.0.3 : check complet de l'UI → 4 correctifs

Check utilisateur des outils dans l'appli (v1.0.2) : 4 pannes, 4 causes, 4 fixes —

1. **compile_typst** « os error 2 » : `typst.compile(str)` interprète la chaîne
   comme un CHEMIN de fichier (preuve hôte : identique). Fix : `source` passe en
   **octets** (une ligne de texte compile), `file_path` passe par son **vrai
   chemin** (contexte `#include`/images relatifs) — les deux cas demandés.
2. **search_web** (8888 injoignable) : `markdown_it` importe `linkify_it` au
   chargement — module **absent de l'APK** → le thread SearXNG meurt silencieusement.
   Fix : `linkify-it-py` ajouté à requirements-min (débusqué par test à import
   bloqué sur le code exact de l'APK).
3. **Fuseau horaire** « No time zone found with key UTC » (et worker des
   automatisations) : Android n'a pas `/usr/share/zoneinfo`. Fix : `tzdata`
   (base IANA embarquée) ajouté à requirements-min.
4. **execute_code** « loadPyodide is not defined » : Pyodide a été retiré du
   frontend (P13) — l'outil ne peut pas marcher. Fix : `code_interpreter.enable`
   forcé à false (outil masqué, réactivable en admin).

**Embeddings** : testé le relay LLM de l'utilisateur (`/embeddings` → 404) :
pas d'API d'embedding disponible. Options documentées : Ollama sur le PC
(`nomic-embed-text` via OLLAMA_BASE_URL) ou toute API compatible OpenAI
(Admin → Documents). Les outils sémantiques (query_knowledge_*, add_memory)
restent en erreur propre tant qu'aucune n'est configurée.

## 2026-11-07 — v1.0.4 : re-test complet (40 outils) → 4 causes profondes

Re-test utilisateur sans réutiliser les résultats : 24 OK, 2 dégradés, 12 en panne
regroupés en 6 causes. Corrections —

1. **compile_typst** « 'FilesTable' object has no attribute 'insert' » : l'outil
   appelait `Files.insert(...)` — l'API réelle est `Files.insert_new_file(user_id,
   FileForm(...))`. Corrigé (le compilateur, lui, fonctionnait déjà).
2. **grep_knowledge_files / grep_skill_files** « module 're' has no attribute
   'Options' » : `knowledge_fs` utilise l'API `re2.Options` (google-re2, natif
   absent) avec repli `import re as re2` — `re` n'a pas `Options`. Fix : shim
   `src/re2.py` (Options/compile/error sur `re`, littéral + case-insensitive
   testés).
3. **Automatisations** « Error during worker process initialization » : la source
   est `anyio.to_process.run_sync` (sous-processus impossible sur Android) dans
   `utils/recurrence.py`. Fix P21 : `to_thread.run_sync`.
4. **search_web** toujours injoignable malgré linkify-it-py : la trace du thread
   SearXNG était perdue. Maintenant écrite dans `data_dir/searxng.log` (P22) et
   **annexée au message d'erreur de search_web** — le prochain test porte la
   cause exacte. + `extractPackages "searx"` (settings.yml/locales/static sur
   disque, par sécurité).

Embeddings : le relay de l'utilisateur ne sert pas /embeddings (404) — attendons
l'URL + le modèle configurés côté appareil pour corriger (soupçon : nom de modèle).

## 2026-11-08 — v1.0.5 : Pyodide restauré (execute_code) + fix mémoire

**execute_code** : l'utilisateur veut l'exécution Python (analyse CSV/Excel/PDF,
calculs, graphiques). P23 restaure `pyodide/` (61 Mo : cœur + paquets) dans les
assets frontend — parti de `pyodide.worker` qui charge le runtime depuis
`/pyodide/` (local ; le CDN jsdelivr ne sert qu'aux paquets). Contrepartie
explicite de P13, la règle « pas de calcul local » ne vise que les embeddings
(D15). `code_interpreter.enable` est réactivé (env + force config) — la
désactivation de v1.0.3 n'avait de toute façon jamais remplacé la valeur `true`
déjà en base (le helper ne force que les valeurs falsy).

**add_memory / update_memory** « 'dict' object has no attribute 'id' » : notre
`LocalVectorDB._write` consommait `item.id` (attributs) alors que le pipeline
mémoire passe des **dicts bruts** — normalisation dict→VectorItem à l'entrée.
Validé hôte : dicts + modèles acceptés, query OK.

Reste ouvert : msgspec (recherche web) lie `libc.so.6`/`libm.so.6` (glibc) au
lieu du bionic — le wrapper ndk-cc est correct isolément, la commande de lien
réelle de setuptools reste à profiler (logging wrapper en place).

## 2026-11-08 — Renumérotation 1.0.N → 0.0.N + v0.0.6 (recherche web réparée)

**Renumérotation** (souhait utilisateur : le projet est en étape pré-stable) :
toutes les versions `1.0.N` deviennent `0.0.N`. Tags `v0.0.0`–`v0.0.5` recréés
aux **mêmes commits**, releases renommées via l'API GitHub (APK intacts,
Actions désactivés pendant l'opération pour éviter des rebuilds), anciens tags
`v1.0.N` supprimés. Les APK historiques gardent leur `versionName` interne
(1.0.N) ; à partir de v0.0.6, `versionName` suit la numérotation 0.0.N.

**Recherche web (msgspec) — cause racine et fix définitif** : la commande de lien
de setuptools révélait `-L/usr/lib/aarch64-linux-gnu` injecté par le sysconfig
de l'Python HÔTE → `-lm` résolvait sur la glibc (`libm.so.6`) au lieu du bionic
du sysroot NDK. Les builds maturin échappaient au piège (d'où « msgspec seul
cassé »). Fix : les wrappers `ndk-cc` filtrent les `-L/usr/lib*` et `-L/lib*`
hôtes. Vérifié `readelf -d` : `libm.so`, `libc.so`, `libdl.so` (bionic) — SearXNG
peut enfin importer msgspec sur l'appareil.

## 2026-11-08 — v0.0.7 : la VRAIE cause de la mort de SearXNG (git absent)

La trace P22 (annexée à l'erreur de search_web) a livré la cause exacte :
`searx/version.py` exécute `git show …` au chargement — **`git` n'existe pas sur
Android** → `FileNotFoundError` → le thread SearXNG meurt avant d'ouvrir le
port 8888. Les tests hôtes passaient car `git` y est présent (divergence
hôte/appareil) — ni msgspec, ni les dépendances.

Corrections (P24) :
- `searx/version_frozen.py` généré (mécanisme amont prévu pour les builds sans
  git) — les appels `git` sont court-circuités ;
- garde-fou P24b : les `except` de `version.py` élargis à `OSError` (dégradation
  propre si le module figé manque).

Validé avec `PATH=/nonexistent` (condition appareil) : `searx.version` charge la
version figée. À suivre : résidu cosmétique `_core…-gnu.so` dans le wheel msgspec
(jamais chargé sur Android) à nettoyer lors d'un prochain rebuild de wheels.

## 2026-11-08 — Confidentialité + jeu de test RAG neutre

**Règle utilisateur** : ne jamais commiter de donnée personnelle (IP même
locale, identifiants, chemins). Un fichier de test contenait l'IP LAN de
l'appareil — supprimé avant tout commit ; historique git vérifié propre.
Règle ajoutée à AGENTS.md (section Confidentialité) + balayage `grep` avant
tout commit de livrable.

**Jeu de test RAG** (`output/2026-11-08/jeu-test-rag/`) : 3 documents neutres
(cycle de l'eau, imprimerie, nutrition) + 10 questions calibrées (réponse
attendue + source) + 3 requêtes hors sujet pour calibrer le seuil de pertinence.
Zéro information liée à l'utilisateur ou au système.

**Releases** : l'utilisateur a lui-même nettoyé les releases problématiques —
seule v0.0.7 subsiste (mystère des « releases disparues » résolu : pas de bug
GitHub). La note de v0.0.7 inclut désormais la version Typst embarquée (ajoutée
aussi automatiquement aux futures releases).

## 2026-11-08 — v0.0.8 : notes réparées (pycrdt réel) + gestionnaire de fichiers

**Notes — « Tab is not connected. Reconnect before leaving this tab. »** :
l'éditeur collaboratif attend que la synchro CRDT soit `synced` avant tout
`flush()` ; notre stub `pycrdt` (accumulation d'octets sans fusion) ne
synchronise jamais avec le vrai Yjs client → erreur + blocage de l'UI
(reconnexion obligatoire). Fix : **pycrdt 0.14.8 réel cross-buildé** (wheel
Rust #8, yrs — même pipeline que msgspec/typst ; `readelf` = bionic ✓), le
stub n'est plus écrit. Piège corrigé au passage : le stub périmé survivait
dans `src/` (pas de rmtree) et aurait masqué le module natif — `write_stubs`
le supprime désormais.

**Gestionnaire de fichiers (P26)** : le Workspace 0.13 n'a aucune section
« Fichiers » (routes : models/tools/knowledge/skills/prompts uniquement) — ni
les PDF générés ni les téléversements n'étaient consultables. Ajout :
- route `/fm` : page HTML autonome (auth session) listant les fichiers avec
  liens de téléchargement `/api/v1/files/{id}/content` + pagination ;
- bouton flottant « Fichiers » injecté dans `index.html` (découvrable partout,
  sans chirurgie sur le JS minifié).

Validé hôte : serveur neuf, marqueur bouton présent, `/fm` → 401 (protégé).

## 2026-11-08 — v0.0.9 : correctif urgent — le .so de pycrdt mal nommé

« No module named pycrdt » au démarrage de v0.0.8 : maturin nomme le natif
`_pycrdt.cpython-313-aarch64-android-android.so`, alors que l'import Android
cherche `_pycrdt.cpython-313-aarch64-linux-android.so` (SOABI de Chaquopy —
le même piège de suffixe que msgspec, en plus subtil : le wheel était
correctement *installé*, seul le nom du `.so` ne correspondait à aucun suffixe
d'import). Fix : `scripts/fix-pycrdt-suffix.py` renomme le `.so` dans le wheel
(et met à jour le RECORD) ; branché dans `build-wheels.sh` pour tout rebuild.

## 2026-11-08 — v0.0.10 : vrai navigateur de fichiers + téléchargements WebView

**Navigation de fichiers (P27)** : le bouton 📂 ouvre désormais un vrai
navigateur : dossiers par type (Tous/PDF/Images/Documents/Autres), recherche
par nom, tri par date, aperçu intégré (`/fm/preview` : image, PDF, texte),
téléchargement et **suppression**. Robustesse : champs `meta`/dates tolérants
(types hétérogènes selon les fichiers — cause probable du « internal error »
de v0.0.9) et toute erreur rendue **lisible dans la page** (traceback affiché).
Validé hôte sur serveur neuf : upload → liste → aperçu ✓.

**Téléchargements dans les chats** : la WebView Android **ne gère aucun
téléchargement** par défaut — ajout d'un `DownloadListener` (DownloadManager +
cookie de session pour les URL authentifiées `/api/v1/files/…/content`), les
fichiers arrivent dans Téléchargements avec notification.

## Points ouverts

- Version Open WebUI cible à figer (release stable recommandée).
- Paquets pip natifs indisponibles dans l'index Chaquopy → à inventorier dès la
  Phase 1 (risque principal du projet).
- `javac` absent du PATH : vérifier que le JDK 21 est complet (`-jdk` pas `-jre`).

## 2026-11-08 — v0.0.11 : compile_typst libéré + retour navigateur

**compile_typst disparu de l'inventaire** : l'outil était enregistré *dans le
bloc `create_tool`/`workspace.tools`* (création d'outils) — il héritait donc de
ses permissions et pouvait disparaître (hypothèse utilisateur : lié à une
autorisation — exact, celle de création d'outils). Fix P28 : enregistrement
*indépendant et inconditionnel* (outil documentaire).

**Navigateur de fichiers** : bouton de retour « ← Open WebUI » fixe et visible
sur toutes les pages /fm (et aperçu).

**Conversations conservées à la mise à jour** : comportement normal — une mise
à jour Android conserve les données de l'appli ; seul « Effacer les données »
(Réglages → Apps) ou une désinstallation-suppression remet à zéro.

## 2026-11-08 — v0.0.12 : tailles du navigateur corrigées (cause racine FileMeta)

« La taille du fichier est fausse » dans /fm : la colonne montrait « — » et la
valeur brute était ambiguë (virgule de milliers à la française). Cause racine
découverte : l'API renvoie `meta` sous forme d'objet **`FileMeta`** (modèle
Pydantic : name/content_type/size), pas d'un dict — l'ancien `meta.get(...)`
levait une AttributeError (**= le « internal error » de v0.0.9**) et mon
`isinstance(meta, dict)` vidait les champs (taille, type). Fix : accès unifié
`_fm_get()` (dict ou objet) + affichage **humain français** (« 7,6 Ko ») prenant
la taille réelle du fichier sur disque en priorité, « — » si inconnue.
Validé hôte : 7 638 o affiché « 7,6 Ko », colonne Type rétablie.

## 2026-11-08 — v0.0.13 : contrôle automatique de la chaîne APK (check_apk.py)

Demande utilisateur : vérifier en fin de build que l'APK contient bien ce qui
est attendu. `scripts/check_apk.py` (exécuté en CI avant publication, rejet du
build si échec) contrôle les PIEGES RENCONTRES en production :
- modules pip critiques présents (typst, pycrdt, msgspec, pydantic_core…) ;
- code applicatif présent (open_webui, searx + settings.yml + version_frozen,
  shims tiktoken/re2, stub pycrdt absent) ;
- noms de `.so` importables (SOABI Android ou .abi3) — piège pycrdt ;
- liaison bionic des natifs (aucun libc.so.6 = glibc) — piège msgspec ;
- frontend complet (`_app/` ≥ 500, index + bouton /fm, pyodide) ;
- route /fm présente dans le code embarqué (recherche dans les .pyc) ;
- taille d'APK plausible.

Premier passage du contrôle sur la v0.0.11 : il a déniché le `.so` résiduel
`_core…-gnu.so` de msgspec (lié à la glibc !) — retiré du wheel par le nettoyeur
étendu (`fix-pycrdt-suffix.py` strip désormais tout `.so` parasite). Le message
d'erreur de `compile_typst` est aussi devenu auto-diagnostiquant (python, HOME,
sys.path) pour trancher le « No module named 'typst' » restant côté appareil.

## 2026-11-08 — v0.0.14 : le problème de FICHIERS réglé + check_patches.py

**Racine du problème de fichiers** : le prompt système promet au modèle d'écrire
dans `/mnt/uploads/` (« l'utilisateur pourra télécharger depuis le navigateur de
fichiers ») — chemin Docker qui n'existe pas sur Android. Conséquences : outils
en échec, fichiers invisibles au navigateur, tailles fausses. Correctifs (P30) :
- alias `/mnt/uploads/` → dossier uploads réel (Storage.get_file + display_file) ;
- le navigateur liste désormais AUSSI les **fichiers orphelins** (écrits hors
  base par les outils/skills) avec téléchargement `/fm/raw` et suppression ;
- tailles justes (taille réelle du disque en priorité) ;
- display_file oriente vers view_note pour les notes (au lieu de « File not found »).

**check_patches.py** (demande utilisateur) : vérifie l'application réelle des
patchs P1–P30 dans le code généré (motifs, placement de compile_typst hors des
blocs de permission, shims, SearXNG, frontend, build.gradle, syntaxe de tous les
.py, typos courantes) — exécuté en fin de prepare_src : un build s'arrête si un
patch est mal appliqué.

**Évolution des fichiers de diagnostic — justification** (règle ajoutée à
AGENTS.md) : `check_patches.py` a été calibré 3 fois à sa création, pour des
faux positifs avérés : (1) le frontend est déplacé par P15 → contrôle dans
src-assets/ ; (2) `<dir>_*` apparaît dans un commentaire → contrôle de la ligne
d'affectation uniquement ; (3) P5 cible `routers/audio/__init__.py` (et non
`audio/__init__.py`). Le `_os2.sub` (os au lieu de re) trouvé par la page
d'erreur auto-diagnostiquante est aussi ajouté à la liste des typos proscrites.

## 2026-11-08 — v0.0.15 : données visibles dans Android/data + purge au démarrage

**Demande utilisateur** : les fichiers doivent être dans
`/sdcard/Android/data/org.openwebui.android/` (comme les autres applis) et les
anciens fichiers sont à effacer au démarrage.

- Les données (base, uploads, frontend, statuts) migrent vers l'espace EXTERNE
  de l'app (`getExternalFilesDir`) — visible et effaçable depuis un gestionnaire
  de fichiers, donc consultable par l'utilisateur (l'espace interne
  `/data/data/…` est invisible par conception Android).
- **Purge au démarrage** des anciens fichiers de la mémoire interne (data/,
  frontend/, marqueurs) : efface les restes de versions antérieures — et la
  configuration « fantôme » restaurée par la sauvegarde Android, que
  l'utilisateur ne parvenait pas à supprimer. Ne touche pas au runtime Chaquopy.
- Manifeste : `allowBackup=false`, `fullBackupContent=false`,
  `dataExtractionRules` (aucun transfert), `hasFragileUserData=true` (Android
  propose de conserver les données à la désinstallation) — la persistance
  invisible est désormais impossible par conception.
- Tailles du navigateur : calcul robuste (max disque / métadonnées / contenu en
  base) — un 0 n'apparaît plus si une source connaît la vraie taille.

## 2026-11-08 — v0.0.16 : téléchargements blob + panneau de maintenance

**Téléchargements blob** (demande utilisateur) : les exports de l'interface
(export de base de données, etc.) passent par des URL `blob:` que le
DownloadManager refuse. Pont JavaScript ajouté dans la WebView : le blob est lu
en JS, transmis en base64 au bridge `AndroidDownload`, puis écrit dans
Téléchargements avec notification. Les URL http/https gardent le DownloadManager.

**Panneau de maintenance** (📂 → ⚙ Maintenance) : chemin exact des données,
taille de la base, sauvegarde `webui.db`, et bouton *Tout effacer* — la
réinitialisation (`data/reset-requested`) efface toutes les données au prochain
démarrage. La page explique aussi la persistance : la configuration ne provient
jamais de l'APK (vérifié : aucune base dans le paquet) — elle « survit » par la
sauvegarde Android (désactivée depuis v0.0.15) ou parce qu'une mise à jour
conserve les données ; l'effacement interne donne le contrôle total.

**check_patches en action** : le gardien a bloqué la génération sur une erreur
de syntaxe du code injecté (guillemets imbriqués dans un onsubmit) — preuve
en direct de son utilité.

## 2026-11-08 — v0.0.17 : cohérence index/fichiers + outils de suppression

Audit 48 outils (37 OK, 5 en échec) — cause racine de l'incohérence
`query_knowledge_files` vs `view_knowledge_file` : **ma route `/fm/delete`
supprimait la ligne en base sans purger l'index vectoriel** (l'API officielle
le fait : `ASYNC_VECTOR_DB_CLIENT.delete(file-<id>)`) → chunks orphelins citant
des fichiers disparus. Correctifs :

- P31 : `/fm/delete` purge aussi l'index vectoriel ; bouton *Nettoyer l'index
  des documents disparus* dans ⚙ Maintenance (`/fm/fix-index`) — soigne les
  orphelins déjà accumulés (l'état de l'appareil utilisateur).
- P29 : outils `delete_note`, `delete_skill`, `delete_tool` (aucun n'existait :
  toute sonde d'écriture était définitive — demande utilisateur).
- compile_typst : diagnostic enrichi (paquet typst présent sur chaque chemin ?
  espace disque libre ?) — pour trancher « module absent » vs « extraction
  ratée » sur l'appareil.

Incident de méthode : une découpe automatisée a tronqué `prepare_src.py`
(1074 lignes perdues) — restauré par `git checkout` + ré-application des ajouts
non committés. Leçons : toujours un commit avant manipulation lourde, et
préférer l'édition ciblée aux découpages regex.

Rappel de l'audit : execute_code fonctionne (Python 3.14, /mnt/uploads OK) ;
restent à traiter : compile_typst (infra), search_memories/search_knowledge_files
(sémantique), create_tool (méthodes non exposées).

## 2026-11-08 — v0.0.18 : version affichée dans l'app + leçon de diagnostic

« Config persistante » sur v0.0.17… mais le sondage par routes a prouvé que le
serveur qui répondait n'avait PAS les routes v0.0.17 (`POST /fm/fix-index` →
405) : le processus de l'appli n'avait pas été redémarré après la mise à jour
et servait l'ancien code. Leçon : la version *installée* ≠ version *en
exécution* — toujours forcer l'arrêt/relancer après mise à jour.

Correctif de diagnostic : le pied de page du navigateur 📂 affiche la
**version du code exécuté** (lue dans build.gradle à la génération), pour
distinguer instantanément les deux.

## 2026-11-08 — Bis du piège du zombie (et régulation)

La « config persistante » de l'utilisateur : mon serveur de test (smoke) tournait
**toujours sur 8080** — l'appli Android ne pouvait pas démarrer son propre
serveur, et toutes les interactions (utilisateur ET mes sondes) parlaient à la
base de test. D'où une config « indestructible » et des panneaux absents.
Régulation : `smoke.sh` sert désormais sur **8090** (règle AGENTS.md), et un
`pgrep` de vérification est exigé après chaque test.

## 2026-11-08 — v0.0.19 : téléchargement des blob réparé (« TypeError: Failed to fetch »)

Le pont de téléchargement fetchait l'URL `blob:` — échec systématique (le blob
n'est pas fetchable depuis le contexte natif). Correctif P32 : monkey-patch de
`URL.createObjectURL` dans `index.html` — l'objet Blob est capturé
(`window.__dlBlob`) et transmis **directement** en base64 au pont natif, sans
aucun fetch. Le fetch sur l'URL blob n'est plus qu'un repli.

## 2026-11-08 — v0.0.20 : honnêteté des outils fetch_url / execute_code (audit DeepSeek)

Audit externe (52 outils) : « un seul outil est réellement problématique
(fetch_url), un second est fragile (execute_code) ». Confirmé au code :

- fetch_url ne recevait AUCUN statut HTTP de `get_content_from_url` → un 404
  renvoyait la page d'accueil ou du vide **sans erreur**, un 302 renvoyait le
  corps de la redirection, une page anti-bot « Just a moment... » passait pour
  du contenu. P33 : sonde HTTP préalable `_probe_fetch_url` — statut réel,
  redirections suivies saut par saut **avec ré-validation SSRF** (validate_url
  à chaque hop), échec réseau/HTTP renvoyé en erreur JSON avec `status_code` +
  chaîne de redirections, en-tête `[HTTP xxx — url]` sur tout contenu,
  détection des interstitiels anti-bot (Cloudflare & co).
- execute_code renvoyait `'status': 'success'` **codé en dur**, même quand une
  exception restait dans stderr → l'agent croyait à une réussite. P34 :
  `status: error` dès que stderr est non vide (inclut « session disconnected »).
- Mesures locales (venv313) : 404 → statut 404 ; /redirect/2 → 2 sauts suivis →
  200 final avec chaîne ; page normale → 200. ✓

Reste à traiter (suite audit) : display_file (recherche du fichier écrit par le
bac à sable hors UPLOAD_DIR, message d'erreur trompeur), query_knowledge_bases
([] alors que search_knowledge_bases trouve), search_memories (requête vide →
[] au lieu d'énumérer), ask_user (doit rester seul dans l'appel — à documenter).

## 2026-11-08 — v0.0.21 : notifications natives (le réglage ne pouvait pas s'activer)

Cause : le bouton « Notifications » du frontend fait
`"Notification" in window ? await Notification.requestPermission() : "denied"`
— or l'API web Notification **n'existe pas dans une WebView Android** → le
tombait toujours sur `denied` → « Response notifications cannot be activ… ».

Correctif P35 :
- pont natif `AndroidNotify` (permissionState / requestPermission / show) →
  vraies notifications Android (canal « openwebui », BigTextStyle, icône
  vectorielle dédiée `ic_notification.xml`, tap → ouvre l'appli) ;
- shim `window.Notification` injecté dans `index.html` (P35) : le frontend croit
  manipuler l'API web standard, tout passe par le pont natif ;
- permission POST_NOTIFICATIONS : déjà demandée au démarrage
  (`requestAppPermissions`) ; le retour du dialogue système résout la promesse
  JS `Notification.requestPermission()` (via `window.__notifPermResolve`) —
  refus définitif → `denied` honnête + toast vers les réglages.

Note : `minifyEnabled false` → aucun risque de strip des @JavascriptInterface.

## 2026-11-08 — v0.0.22 : « no attribute get_collections » sur le nettoyage d'index

Le bouton ⚙ « Nettoyer l'index des documents disparus » levait AttributeError.
Cause : la route /fm/fix-index (P31) appelait
`ASYNC_VECTOR_DB_CLIENT.get_collections()` — méthode qui n'existait **ni** sur
le wrapper async **ni** sur LocalVectorDB (elle n'appartient à aucune interface
VectorDBBase : seuls les backends qdrant l'ont en interne).

Correctif P36 :
- `LocalVectorDB.get_collections()` implémenté (SELECT DISTINCT collection) —
  la base locale sait désormais s'énumérer ;
- route corrigée : énumération via le client **synchrone** (`ASYNC_VECTOR_DB_CLIENT.sync`,
  propriété) avec `hasattr` + repli → message « Index non inspectable » si le
  backend ne l'implémente pas ; index vide = « Aucune orphelin » (pas d'erreur).
- Test fonctionnel local : insertion 2 collections → liste correcte → suppression
  → liste mise à jour. ✓

Leçon de méthode : ma route P31 avait été testée par sonde HTTP (400/405) mais
jamais **exécutée** — un appel à une méthode inexistante ne se voit pas dans un
test de présence de route. Toute nouvelle route de maintenance doit être
*exécutée* au moins une fois (serveur de test sur 8090).

## 2026-11-08 — v0.0.23 : /fm à l'identique visuelle d'Open WebUI (P37)

Demande utilisateur : retirer le bouton « retour assistant » (doublon avec la
navigation Open WebUI/Android) et aligner le visuel du navigateur de fichiers.

- P37 : refonte `_FM_STYLE` — police Inter (pile officielle Open WebUI),
  palettes exactes du frontend (#fff/#000 clair, #171717/#eee sombre,
  noir pur oled-dark), thème lu dans localStorage["theme"] comme Open WebUI
  (dark/light/oled-dark + prefers-color-scheme en repli), coins arrondis,
  table survol, boutons secondaires, en-têtes de colonnes discrets.
- Boutons supprimés : pilule flottante « ← Open WebUI », liens « ← assistant »
  (page d'erreur + barre du navigateur), bouton « Voir » (×2) — le nom du
  fichier est déjà le lien vers l'aperçu ; il restait Télécharger + Suppr.
- Version conservée en pied de page discret (outil de diagnostic v0.0.18).

## 2026-11-08 — v0.0.24 : Pyodide pandas/sympy + comportements outils corrigés (P38–P40)

Contexte : l'appli de l'utilisateur tourne sur 8080 (tests maintenus sur 8090,
règle respectée — aucun contact avec l'instance utilisateur).

- P38 — bac à sable Pyodide : le worker ne préinstallait que micropip ;
  numpy/pandas/sympy (wheels déjà embarqués + pyodide-lock.json offline,
  364 paquets) n'étaient disponibles que via la détection regex d'import.
  Ils sont désormais chargés au boot : `packages:["micropip","numpy","pandas","sympy"]`.
- P39a — search_memories (« corriger le comportement », choix utilisateur) :
  la recherche de contenu cassait en français. Exécuté avant/après :
  | requête | avant | après |
  |---|---|---|
  | « sonde d'audit » (apostrophe droite) vs contenu « Sonde d'audit » | [] | [1] |
  | « sonde audit » (mots séparés) | [] | [1] |
  | apostrophe typographique | [1] | [1] |
  | requête vide (parcours) | [1,2] | [1,2] (inchangé) |
  | hors sujet | [] | [] (pas de faux positif) |
  Normalisation apostrophes/quotes + casefold + tous les mots requis.
- P39b — query_knowledge_bases : l'index sémantique des bases n'est rempli
  qu'à la création/édition ; toute base créée pendant la panne d'embeddings
  (audit passes 1-2) restait invisible. Auto-réparation : les bases accessibles
  non indexées sont réindexées (embed_knowledge_base_metadata) avant la
  recherche — la description de l'outil (sémantique sur nom+description)
  devient enfin vraie.
- P40 — FAB retour vers Open WebUI sur TOUTES les pages /fm : jumeau du bouton
  📂 du SPA (même style, icône 💬), navigable depuis chaque page.

Justification de l'évolution de scripts/check_patches.py (règle diagnostic) :
contrôle ÉTENDU aux patchs P31/P33/P36/P38/P39 (aucun affaiblissement). Le
contrôle P38 cible la destination FINALE du frontend (src-assets/ après le
déplacement P15) avec repli sur le chemin pré-déplacement — leçon : vérifier
les chemins APRÈS la chaîne complète de génération.

## 2026-11-08 — v0.0.25 : contrat /mnt/uploads tenu (P41) + audit 22:20 (P42, P43)

Audit 22:20 (3 anomalies + demande de vérification du mapping /mnt/uploads).
Tests menés sur ports de test uniquement (8090/8091/8092) ; instance utilisateur
sur 8080 jamais touchée (sondage lecture-seule) ; tout le banc a été tué après
usage (0 survivant vérifié).

- Mapping /mnt/uploads VÉRIFIÉ : dataHome = getExternalFilesDir() →
  files/ ; DATA_DIR = files/data ; UPLOAD_DIR = files/data/uploads — exactement
  le chemin attendu. Mais le /mnt/uploads de Pyodide vivait dans l'IndexedDB du
  navigateur : les fichiers écrits n'atteignaient JAMAIS ce dossier. P41
  (contrat du prompt système « écrivez dans /mnt/uploads pour les retrouver
  dans le navigateur ») : le worker renvoie les fichiers produits → le frontend
  les transmet → execute_code les enregistre dans UPLOAD_DIR (dédup par taille)
  et les signale au modèle. Test E2E chromium : fichier écrit dans /mnt/uploads
  renvoyé (rapport-test.txt, 35 o) ✓. Entrées déjà présentes ignorées.

- Anomalie 1 (paquets scientifiques) : PROUVÉE comme couverte par P38
  (v0.0.24). Matrice exécutée dans chromium réel avec les octets STRICTEMENT
  identiques à ceux servis par l'appareil (worker appareil == worker local,
  wheels servies en 200, lock 200) :
  | chemin | test | résultat |
  |---|---|---|
  | boot (P38, sans packages dans le message) | import numpy/pandas/sympy | numpy=2.4.3 pandas=3.0.2 sympy=1.14.0 ✓ |
  | message (regex → micropip) | import scipy/matplotlib | scipy=1.18.0 matplotlib=3.10.8 ✓ |
  L'audit a dû être tourné sur l'état antérieur à P38 — à retester sur v0.0.25
  après force-stop.

- Anomalie 2 (rappel mémoire irrégulier) — P43 : recherche à deux paliers
  (tous les mots → au moins la moitié). Testé : « préférence de présentation
  des rapports » → trouvé (avant : []) ; « rapports de diagnostic avec
  tableaux » → trouvé ; hors sujet → [] (pas de faux positif).

- Anomalie 3 (\n littéraux) — P42 : write_note et replace_note_content
  convertissent les \n/\t littéraux en vrais sauts, UNIQUEMENT si le texte ne
  contient aucun saut réel (jamais de mélange contenu/échappements). Testé.

Justification de l'évolution de scripts/check_patches.py (règle diagnostic) :
contrôle ÉTENDU aux chaînes P41 (worker→frontend→execute_code, 3 maillons dont
2 à nom haché → glob) et P42 (marqueurs write_note/replace_note_content) —
aucun affaiblissement.

## 2026-11-08 — v0.0.26 : cause racine de la régression Pyodide (P44/P44b) + rrule (P45)

Audit 22:59 : 4 corrections confirmées, 2 anomalies restantes. Investigation
poussée sur la régression scientifique (qui résistait à la preuve chromium) :

CAUSE RACINE (P44) — `ENABLE_PYODIDE_FILE_PERSISTENCE` vaut `false` par défaut
(env.py amont) : le SPA choisit alors l'exécuteur IFRAME (`class ap`) et non le
WORKER (`hp`). Or TOUTES mes corrections Pyodide (P38 boot, P41a remontée de
fichiers) vivaient dans le worker — l'iframe ne chargeait que `micropip` au
boot et ne comptait que sur la détection regex littérale d'imports. Mes tests
chromium validaient le worker — la bonne voie — mais l'appareil ne la prenait
pas. Fix : `ENABLE_PYODIDE_FILE_PERSISTENCE=true` dans android_main
(_prepare_env) → le worker sert désormais, avec boot numpy/pandas/sympy,
persistance IDBFS de /mnt/uploads et remontée des fichiers (P41).
P44b (filet) : le boot de l'iframe embarque aussi numpy/pandas/sympy.

Anomalie N°2 (rrule) — P45 : la cause est la docstring d'OUTIL elle-même, qui
montre « DTSTART:...\nRRULE:... » avec \n littéral ; les LLM la copient telle
quelle et le parseur RRULE refuse (« Unknown string format »). Normalisation
inconditionnelle dans create_automation/update_automation (un \n littéral n'a
aucun sens en RRULE). Testé : « DTSTART:20250101T090000\nRRULE:FREQ=DAILY »
littéral → vraie ligne ✓.

Justification de l'évolution de scripts/check_patches.py (règle diagnostic) :
contrôle ÉTENDU (P44 activation de la voie worker, P44b boot iframe, P45 rrule)
— aucun affaiblissement. Leçon méthodologique : une preuve sur banc doit
reproduire le SÉLECTEUR de chemin de l'appareil (flag/feature), pas seulement
le composant cible.

## 2026-11-08 — v0.0.27 : paquets Pyodide à la demande, insensibles au style d'import (P46)

Rapport utilisateur : numpy/pandas/sympy OK (le boot P38 tourne enfin — la
voie worker est bien active), mais matplotlib/scipy/sklearn/PIL/bs4/requests/
lxml/docx/pptx/openpyxl/seaborn absents. Cause : l'installation à la demande
reposait sur la détection regex d'IMPORTS LITTÉRAUX côté frontend ; un code
qui teste par boucle ou importlib ne déclenche rien — et l'audit testait
précisément ainsi (matrice « disponibles = exactement le boot »).

- P46a : `_pyodide_packages(code)` côté SERVEUR — détection par simple
  PRÉSENCE du nom de module dans le code (import littéral, boucle, importlib,
  chaîne). Testé : littéral → [matplotlib, scipy] ; boucle/importlib →
  [beautifulsoup4, matplotlib, pillow, scikit-learn] ; rien → [].
- P46b–e : la liste est transmise dans le message et fusionnée avec la détection
  regex frontend (filet de sécurité double).
- P46f : le prompt système du bac à sable documente la liste RÉELLE des
  bibliothèques embarquées (et signale l'absence volontaire de pymupdf,
  statsmodels, plotly — pas de wheels dans l'APK).

Justification de l'évolution de scripts/check_patches.py : contrôle ÉTENDU
(P46a backend, P46c transit frontend) — aucun affaiblissement.

## 2026-11-08 — v0.0.28 : statsmodels et pymupdf embarqués (P47)

Question utilisateur : « pourquoi les wheels ne sont pas embarqués ? » → la
sélection des 53 wheels est celle de l'amont (APK léger) ; le lock Pyodide en
connaît 364, le reste suppose un CDN à l'exécution (impossible hors ligne).
MAIS statsmodels et pymupdf existent en wasm dans la distribution :

- téléchargés depuis le CDN officiel (pyodide v314.0.3), sha256 CONFORMES au
  pyodide-lock.json de l'APK (vérifié) : pymupdf 17,5 Mo, statsmodels 8,1 Mo ;
- stockés dans vendor/wheels-extra/ (règle D5 : tout dans le projet) puis copiés
  dans pyodide/ à chaque génération (P47) — installables hors ligne via la
  détection P46 (fitz → pymupdf, statsmodels → statsmodels) ;
- prompt du bac à sable mis à jour : pymupdf/statsmodels disponibles ;
  plotly/pypdf/pdfplumber INEXISTANTS pour ce runtime wasm (pas dans le lock).

Justification de l'évolution de scripts/check_apk.py (règle diagnostic) :
contrôle ÉTENDU — les wheels statsmodels/pymupdf doivent figurer dans l'APK
(aucun affaiblissement). Gain : extraction/lecture PDF native (pymupdf) et
régressions/stats (statsmodels) dans execute_code.

## 2026-11-08 — v0.0.28 (suite) : build bloqué par check_apk — wheels non versionnés

Le build CI a échoué à « Vérification de la chaîne APK » (check_apk, contrôle
P47 ajouté) : les wheels statsmodels/pymupdf étaient absents de l'artefact.
Cause : `vendor/wheels-extra/` est couvert par la règle `.gitignore:/vendor/`
— les wheels n'avaient jamais été committés, la CI les cherchait en vain et
P47 sautait silencieusement.

Correctif : wheels déplacés vers `wheels-extra/` (racine, VERSIONNÉS comme les
53 wheels amont de src-assets/frontend/pyodide/) ; patch_extra_wheels lit ce
dossier. Le contrôle check_apk a donc fait son travail : un garde-fou qui
échoue est un garde-fou qui fonctionne.

## 2026-11-08 — v0.0.29 : rapport 22:59 traité en 5 points (P48–P52)

1. Deux magasins de fichiers (P51) : compile_typst écrit dans le dossier
   uploads, le bac à sable vivait dans son IndexedDB — deux espaces disjoints.
   Les uploads (8 Mo/fichier, 24 Mo total) sont injectés dans /mnt/uploads
   avant chaque exécution ; la remontée P41 fait le chemin inverse. Un seul
   espace de fichiers désormais.

2. Réseau incohérent (P52) : socket.create_connection mentait (« ouvert »)
   alors que le HTTP sortant est soumis à CORS. Les sockets wasm échouent
   désormais proprement (OSError explicite) et un flag `network_available`
   (vraie sonde HTTP, mémoire entre exécutions) documente la réalité.

3. search_knowledge_files (P48) : le matching était un ILIKE SQL brut —
   « rapport vulnerabilites » ne trouvait jamais « rapport-vulnerabilites.json ».
   Normalisation espace/tiret/underscore + tous les jetons requis + recherche
   du nom de la base. TESTÉ de bout en bout sur la base de test (5 cas) :
   espace ✓, ordre inversé ✓, underscore ✓, json ✓, hors sujet → [] ✓.

4. Noyau non récupérable (P49) : un OOM/kill condamnait toute la session
   (5 tentatives en échec). Le worker réinitialise son init en cas d'échec
   (L.catch → L=null) et le frontend remplace le worker mort sur erreur fatale
   (onerror OU stderr mémoire/RuntimeError/disconnected) — la conversation
   survit à un dépassement de mémoire.

5. tiktoken (P50) : retiré de la liste (tables BPE non embarquées → tentative
   de téléchargement réseau). Le prompt documente la liste RÉELLE + le
   comportement réseau.

Note sécurité (règle confidentialité) : un fichier contenant une clé a été
trouvé dans /mnt/uploads de l'appareil — suppression faite et clé révoquée
côté Albert/etalab (le seul geste efficace, correctement effectué). Rien de
tout cela n'a touché le dépôt. Rappel : P51 rend les uploads VISIBLES dans le
bac à sable — ne jamais y déposer de secrets.

Justification de l'évolution de scripts/check_patches.py : contrôle ÉTENDU
(P48/P51/P52 backend, P49a worker) — aucun affaiblissement.

## 2026-11-08 — v0.0.30 : rapport outils/execute_code traité (P53–P61)

- P53 : statsmodels « absent » → sa dépendance patsy n'était pas embarquée
  (statsmodels dépend de numpy/scipy/pandas/patsy/packaging ; seule patsy
  manquait). Wheel officielle récupérée (sha256 conforme au lock) dans
  wheels-extra/.

- P54 (sévérité haute) : query/search_knowledge_bases ne cherchaient que le
  nom/description — une KB mal nommée était invisible. Fallback par le
  CONTENU des fichiers (nom + contenu, moteur normalisé P48/P55) quand la
  recherche nominative reste muette. TESTÉ : « securite ia open source » et
  « systemes embarques » trouvent par le contenu ; hors sujet → [].

- P55 : search_knowledge_files cherchait par nom alors que son nom promet le
  plein texte (« test » → 0 malgré 97 occurrences). Le contenu est désormais
  cherché (include_content) avec le moteur normalisé, dans les 3 chemins
  d'appel. TESTÉ (3 cas, base de test).

- P57 : write_note enregistre la lecture de la page créée — le workflow
  « créer puis ajuster » ne subit plus le garde-fou read_required.

- P58/P59 : list_tools (vérifie créations/suppressions de tools) et
  delete_file (efface uploads/fichiers de chat/KB avec purge de l'index).
  Les artefacts de test du rapport deviennent supprimables par l'utilisateur.

- P60 : le prompt du bac à sable documente la réalité réseau (CORS — un
  ConnectionError ne signifie pas qu'un site est mort) et la règle de
  redondance fetch_url ↔ requests (egress différents).

- P61 : fetch_url comprime les lignes vides (pages brutes noyées dans du vide).

Reste ouvert (prochain tour) : A3 seuil de pertinence de query_knowledge_files
(scores permissifs), invocation des tools créés dans la même session.

Justification scripts/check_patches.py et check_apk.py : contrôles ÉTENDUS
(P53–P59) — aucun affaiblissement.

## 2026-11-09 — v0.0.31 : correctif des 3 RÉGRESSIONS de v0.0.30 (bloquant)

Audit 01:04 : execute_code, list_tools et list_knowledge_bases étaient
inutilisables — les trois bugs sont de la v0.0.30. Causes racines :

1. execute_code — `None + liste` : mon P51 additionnait les fichiers du
   message à _uploads_pour_sable() ; quand `__metadata__['files']` existe
   mais vaut None, `.get('files', [])` renvoie None → TypeError avant même le
   bac à sable. Corrigé en `(.get('files') or [])`. TESTÉ avec files=None.

2. list_tools — `Tools.get_tools()` est ASYNC : il manquait un `await`
   (coroutine non itérable). Corrigé. TESTÉ : la liste remonte avec les
   fonctions exposées.

3. list_knowledge_bases — « name 'query' is not defined » : le fallback P54a
   visait search_knowledge_bases, mais la queue de list_knowledge_bases est
   IDENTIQUE et replace_once frappe la PREMIÈRE occurrence → le fallback a été
   injecté dans le mauvais outil (crash) et l'outil cible n'a jamais été corrigé
   (d'où le défaut de découverte « persistant » de l'audit). Corrigé par
   remplacement CIBLÉ dans la fonction (découpe par signatures). TESTÉ
   en appelant réellement search_knowledge_bases : « securite ia open source »
   trouve la KB par son contenu (source: content) ✓ ; list_knowledge_bases
   propre ✓.

LEÇON (consignée) : un replace_once sur un motif dupliqué entre outils frappe
en silence la première occurrence. Règle ajoutée : pour les motifs partagés,
cibler par découpe de fonction, et le gardien check_p54_ciblage() vérifie le
positionnement exact (présent dans la bonne fonction, absent de l'autre).

Note : la recommandation de renommer la KB « Test » avec une description
métier est côté utilisateur (les outils cherchent désormais le contenu, mais
un nom explicite reste le meilleur levier de découverte).

## 2026-11-09 — v0.0.32 : « Génération en cours… » qui ne s'arrête jamais

Rapport utilisateur : pendant un audit multi-outils parallèles, la génération
restait suspendue indéfiniment. Cause : execute_code attend le bac à sable via
un appel d'événement SANS DÉLAI — si le noyau ne répond jamais (session
perdue, événement ignoré, démarrage interminable), l'outil ne rend jamais la
main et toute la conversation reste suspendue.

- P65 : délai garanti côté serveur — `asyncio.wait_for(..., timeout=200)` sur
  l'appel d'événement d'execute_code ; passé ce délai, l'outil REND une erreur
  explicite (« Délai dépassé (200 s)… le noyau se relance ») et la génération
  reprend. Aucun outil ne peut plus suspendre une conversation indéfiniment.
- P66 : le délai frontend d'exécution passait de 60 s à 180 s — le premier
  démarrage charge numpy/pandas/sympy (wasm) et tuait les appels légitimes.

Rappel : ask_user bloque volontairement (borné par timeout_ms) — inchangé.
Justification check_patches : contrôle ÉTENDU (P65) — aucun affaiblissement.

## 2026-11-09 — v0.0.33 : audit de divergence — le drift divisé par 3

Directive utilisateur : rester proche de l'origine Open WebUI, ne modifier que
le nécessaire. Audit mesuré puis RÉDUCTION exécutée (phases 1+2) :

AVANT : 16 fichiers amont modifiés, +1248/-52 lignes (83 % concentrés dans
builtin.py +549 et main.py +491).
APRÈS : 16 fichiers, +427/-52 lignes — main.py retrouve +3 lignes (montage),
builtin.py descend à +215 (uniquement les corrections de COMPORTEMENT).

- Phase 1 : tout le bloc navigateur 📂/maintenance quitte main.py pour le
  module AJOUTÉ android_fm.py (register_fm(app), montage à 2 lignes).
- Phase 2 : tout le code AJOUTÉ quitte tools/builtin.py pour le module AJOUTÉ
  tools/android_tools.py (compile_typst, delete_*/list_tools, _probe_fetch_url,
  _pyodide_packages, _uploads_pour_sable, SANDBOX_NET_BOOTSTRAP) ; builtin.py
  importe ces symboles (ré-export : les enregistrements utils/tools.py sont
  inchangés).

Classification maintenue : portage Android / exigences produit / corrections
de contrats (trace des audits) — rien de superflu détecté ; le problème était
la DISPERSION dans l'amont, désormais corrigée.

VÉRIFIÉ avant livraison : compilation des 4 fichiers ; ré-export 10/10 ;
_pyodide_packages identique ; list_tools ✓ ; découverte KB par contenu ✓ ;
DÉMARRAGE RÉEL du serveur (health 200, /fm montée en 401, 0 traceback).
Incident détecté par ce test : les routes empruntaient Depends/Request/
get_verified_user au namespace de main.py — imports ajoutés au module.

Justification check_patches : marqueurs suivis vers android_fm.py/
android_tools.py + nouveau garde-fou P0 (import de montage dans builtin).

## 2026-11-09 — v0.0.34 : « les outils semblent bloqués » — trois bugs autour des await

Rapport utilisateur (audit systématique) : un lot d'outils reste en « Exécution
de… » sans fin. Indice de l'utilisateur : « peut-être autour d'un await ».
Investigation du diff vs amont — TROIS bugs trouvés :

1. P68 (LE blocage) : `search_searxng` interrogeait l'instance SearXNG
   embarquée via `session.get(...)` SANS TIMEOUT — quand ses moteurs traînent
   (Google/DDG lents ou bloqués), search_web attendait le défaut d'aiohttp
   (5 min) voire indéfiniment. Délai explicite : 30 s.

2. P69 (silencieux depuis P31) : `await Storage.delete_file(...)` sur une
   méthode SYNCHRONE → await None → TypeError AVALÉE par un except → la
   ligne en base était supprimée mais le FICHIER PHYSIQUE RESTAIT. Explique
   les fichiers résiduels signalés par les audits. Corrigé en
   `asyncio.to_thread(Storage.delete_file, ...)` (comme l'amont) dans
   delete_file ET /fm/delete. TESTÉ : suppression physique effective.

3. P69 bis (latent depuis le refactor v0.0.33) : android_tools.py utilisait
   `asyncio.to_thread` sans `import asyncio` — compile_typst aurait levé un
   NameError à l'appel (la compilation ne détecte pas les noms manquant).

Sur la remarque « v0.0.30 ne bloquait pas » : cette version-là crashait
instantanément sur execute_code (None+liste) — la ronde finissait vite, en
échec. Le blocage apparent date de la réparation du crash (le bac à sable
tourne pour de vrai) et du timeout SearXNG absent.

Garde-fous : P68/P69 dans check_patches + NOUVELLE règle générale — tout
module open_webui/ utilisant asyncio doit l'importer (leçon : un NameError
n'apparaît qu'à l'exécution ; il faut donc APPELER les outils, pas seulement
compiler).

## 2026-11-09 — v0.0.35 : execute_code ne « bloque » plus (P70/P71)

Confirmé par l'utilisateur : c'est execute_code qui traînait. Cause : le
PREMIER appel monte le runtime wasm (boot numpy/pandas/sympy) et paie les
transferts de fichiers — chaque appel d'un audit en subissait le prix.

- P70 (préchauffage) : le worker est créé et booté AU CHARGEMENT DE LA PAGE
  (message fs:sync qui déclenche l'init en tâche de fond). Au moment d'un
  execute_code, le bac à sable est déjà chaud.
- P71 (charges utiles) : le worker ne renvoie plus les fichiers d'ENTRÉE
  (déjà côté serveur — ils n'avaient rien à faire dans le message retour) et
  plafonne la remontée (8 Mo/fichier, 16 Mo total) ; l'injection des uploads
  n'envoie plus que les fichiers CITÉS dans le code + les petits (budget 2 Mo).
  TESTÉ : fichier cité ✓, petit non cité ✓, gros non cité exclu ✓.

Incident de méthode : mes éditions successives de check_patches avaient
coupé la liste CHECKS en deux (IndentationError) — réparé, et le garde-fou
valide désormais la syntaxe de son propre script à l'exécution.

## 2026-11-09 — v0.0.36 : hotfix « 500 au lancement » (régression v0.0.35)

La v0.0.35 affichait « 500 : Internal Server Error » au lancement — en fait la
page d'erreur du SPA quand le chunk racine ne se charge pas. Cause : mon
insertion P70 (préchauffage) était une IIFE NUE dans une liste de déclarations
`const` du bundle minifié → erreur de syntaxe JS → toute l'interface morte.

Correctifs :
- l'insertion devient un déclarateur valide (`__prewarm=(()=>{...})()`) ;
- NOUVEAU garde-fou permanent : check_js_syntax() — node --check sur tous les
  fichiers JS patchés (un chunk cassé est invisible à toute la chaîne Python) ;
- vérifié : syntaxe JS ✓✓, DÉMARRAGE RÉEL (health 200, SPA en 200, 0 traceback).

LEÇON MAJEURE (double) : (1) patcher du JS minifié exige une validation de
SYNTAXE JS — la présence du texte ne prouve rien ; (2) « compiler et checker »
ne remplace pas « DÉMARRER » — le smoke boot devient obligatoire avant chaque
livraison, comme les vrais appels d'outils.

## 2026-11-09 — v0.0.37 : audit 49 outils traité MÉTHODIQUEMENT (P73-P76)

Méthode imposée par l'utilisateur : cause prouvée → plan → validation de
chaque étape → intégration. Résultats :

- Toggle exécution/recherche : CONFIRMÉ fonctionnel par l'utilisateur
  (activé → outils visibles). P72 (exposition forcée) RÉVOQUÉE — le mécanisme
  amont est le comportement voulu. Validé dans les deux sens : OFF → absent,
  ON → présent.

- P73 (A2, prouvé par reproductibilité : `securite` → [] vs « sécurité ») :
  repli des diacritiques français (SQL + requête) dans les deux moteurs de
  recherche. Validé : `securite informatique` → trouvé.

- P74 (A3) : fetch_url extrait le CONTENU PRINCIPAL quand la page est balisée
  sémantiquement (<main>/<article>/[role=main]) — la nav n'est plus servie.
  Validé par test de `_document_from_html`. Seuil calibré à 50 car. (200
  rejetait les pages fines — trouvé par la validation, pas par la lecture).

- P75 (recommandation audit) : nouvel outil `list_files` — delete_file est
  enfin exploitable (les fichiers résiduels étaient invisibles sans
  identifiants). Bug trouvé en le testant : FileMeta n'est pas un dict
  (getattr, pas .get).

- P76 (A4) : create_tool documente que l'invocation exige l'ATTACHEMENT à la
  conversation (tool_ids envoyé par le client à chaque complétion) —
  comportement amont assumé, désormais explicite.

- Étape 6 (read_required) : validée — create → edit immédiat passe (P57).

Leçons de banc : (1) les harnais de test doivent créer un VRAI user et un
request avec .app/.state ; (2) un critère de test naïf (« 'read_required' in
réponse ») peut mordre sur un nom de champ — parser le JSON.

## 2026-11-09 — v0.0.38 : execute_code rapide — print('hello') en 10 ms (P77)

Critère utilisateur : « il fonctionnait sur des anciennes versions sans
preload et rapidement — print('hello') doit prendre 1 s max ». Donc un coût
était payé À CHAQUE APPEL. Relue de ma propre chaîne — trois coupables :

- P77a : P51 expédiait TOUS les petits uploads (budget 2 Mo) à chaque appel →
  transferts de mégaoctets. Désormais : seuls les fichiers CITÉS partent
  toujours + les très petits (≤ 64 Ko, budget 256 Ko) pour la découvrabilité.
- P77b : P41 renvoyait tout /mnt/uploads à chaque exécution (les fichiers
  persistés revenaient sans cesse). Désormais : instantané avant exécution,
  seuls les fichiers NOUVEAUX/MODIFIÉS remontent (fichiers d'entrée exclus).
- P77c : micropip ré-installait les paquets déjà chargés → filtre sur
  loadedPackages.

VALIDATION D'ACCEPTATION (chromium, vrai worker, préchauffé comme sur
l'appareil) : `x=2+2; print('hello'); x` →
{"result":4,"stdout":"hello\n","files":[]} en 10 ms. Le critère 1 s est tenu
avec 100× de marge (en host ; téléphone attendu 50-300 ms).

Incident de méthode : une ancre de patch avait été écrite avec la version
DÉJÀ patchée (la régénération ne voit que l'amont) — détecté par l'échec du
générateur, corrigé. Les pgrep/pkill de banc se tuent eux-mêmes si le motif
apparaît dans leur propre commande : les scripts de test sont renommés et
arrêtés par PID.

## 2026-11-09 — v0.0.39 : « execute ne s'arrête jamais » démonté (P82/P83) + /fm responsive et identité Open WebUI (P80/P81)

Le problème persistait sur le téléphone — donc pas un résidu local. Relue de
la chaîne avec cet indice : mon P49c (« récupération du noyau ») tuait le
worker sur TOUT stderr contenant RuntimeError — or les codes de test lèvent
des exceptions courantes → chaque erreur forçait un REDÉMARRAGE COMPLET du
runtime wasm (10-60 s sur téléphone). C'est exactement un « ça ne s'arrête
jamais ». En plus, la sonde réseau (P52) se payait au premier appel.

- P83 : on ne tue le worker que sur un vrai CRASH wasm (memory access/out of
  memory/unreachable…) et tout remplaçant est re-préchauffé. VALIDÉ :
  1er appel 8 ms → RuntimeError (worker vivant) → appel suivant 19 ms.
- P82 : le bootstrap réseau/socket s'exécute AU BOOT (préchauffage) — le
  prepend par appel devient un no-op.
- P80 : /fm responsive — media queries portrait/paysage/mobile/tablette.
  VALIDÉ VISUELLEMENT (captures 390x844, 844x390, 820x1180 lues).
- P81 : identité Open WebUI — boutons noirs/blancs (pas bleus), onglet actif
  gris, liens sombres soulignés au survol, suppression rouge discrète.

Note Typst : la chaîne de persistance est VALIDÉE (écriture disque ✓,
list_files ✓, display_file ✓) — le PDF vit dans files/data/uploads sous
<uuid>_<nom>.pdf, affiché <nom>.pdf dans 📂.

## 2026-11-09 — v0.0.40 : execute_code « Client session disconnected » — le réaper démasqué (P84)

Audit : 40 outils OK, mais execute_code hors service — toute tentative
(la plus triviale comprise) renvoie {"status":"error","stderr":"Client session
disconnected."}, sans traceback. L'audit situait la panne « depuis une session
de sous-agent » et demandait un rechargement de page.

CAUSE RACINE (trouvée dans socket/main.py) : le SESSION_POOL est nettoyé par
un RÉAPER après 120 s sans heartbeat (SESSION_POOL_TIMEOUT). Or les timers du
WebView se FIGENT en arrière-plan — exactement pendant un sous-agent long —
les heartbeat s'arrêtent, la session du navigateur est supprimée, et tout
appel d'événement (execute_code !) échoue avec « Client session disconnected »
jusqu'au rechargement. Le symptôme « un nouveau message ne suffit pas » colle.

- P84 : repli automatique — quand la session demandée est absente/expirée/
  synthétique (subagent:<chat>), on vise la session VIVANTE de l'utilisateur
  (même mécanisme que la reprise) et on réécrit l'identifiant porté par
  l'événement (exigé par le frontend). TESTÉ : session périmée → délivré à la
  session vivante → réponse reçue.

Réerves de l'audit actées : create_tool invocable seulement dans un chat
attaché (documenté en P76) ; timer auto-annulable (mécanisme voulu) ;
ask_user non testé (bloquant par nature).

## 2026-11-09 — v0.0.41 : « Délai dépassé » sur les appels lourds — le vrai trou : un ack manquant (P85/P86)

Test utilisateur : un execute_code lourd (numpy+pandas+matplotlib + graphe)
renvoyait « Délai dépassé (200 s) ». Investigation : le `disconnect` retire
bien les sessions du pool (vérifié) — donc le sid mort n'était pas en cause.
Le vrai trou : quand le frontend NE RÉPOND PAS (échec silencieux de Me —
worker qui refuse de se créer — ou événement écarté car conversation non
active dans l'onglet), `sio.call(..., timeout=None)` attend indéfiniment ;
seul mon plafond backend (200 s) bornait, d'où son message.

- P85 : le frontend acquitte TOUJOURS — succès, ou erreur explicite
  (« execute_code frontend: … » / « event dropped : conversation non active
  dans cet onglet »). Plus jamais d'attente muette.
- P86 : plafonds relevés pour le travail lourd (premier appel matplotlib
  = installation wasm) : frontend 180→300 s, backend 200→320 s. Les appels
  légers restent instantanés (8-19 ms mesurés).

Marqueur check_patches P65 mis à jour (200→320) — justifié ci-dessus.

## 2026-11-09 — v0.0.42 : noyau réparé + Paramètres/services dans /fm + bouton déplaçable (P87-P90)

P88 (« le noyau Python ne démarre pas ») : le bootstrap réseau (P82) exécutait
une sonde `urlopen` AU BOOT — le `timeout=3` d'urllib n'arrête pas un fetch
wasm : le boot RESTAIT SUSPENDU, donc plus jamais de noyau. La sonde passe
désormais en JS avec AbortSignal (borné 3 s) et injecte `network_available` ;
le bootstrap Python ne sonde plus rien. VALIDÉ : boot OK + premier appel 5-10 ms.

P87 (« timeout par défaut 2 min modifiable à l'appel ») : paramètre `timeout`
de execute_code (défaut 120 s, max 600, min 5). Leçon technique : un timer
INTERNÉ au worker ne peut pas se déclencher pendant une boucle Python serrée
(le thread est bloqué) — le chronomètre doit vivre dans le FRONTEND, qui peut
tuer le worker. VALIDÉ : `while True: pass` avec timeout=5 → arrêt à 5 s.

P89 (demande utilisateur) : onglet « ⚙ Paramètres » dans /fm — éditeur de
data/openwebui.env (KEY=VALUE) avec garde-fous (DATA_DIR/HOME interdits),
appliqué à chaque démarrage/redémarrage ; boutons de service ▶/⏸/↻ pour
Open WebUI et SearXNG passant par le PONT JAVA (fonctionnent même serveur
arrêté) ; « Redémarrer l'application » (AlarmManager + kill) qui réapplique
vraiment les variables (processus neuf).

P90 (demande utilisateur) : les boutons flottants (📂 SPA et 💬 /fm) sont
DÉPLAÇABLES au glisser-déposer (pointer events), position mémorisée dans
localStorage ; un clic reste un clic (seuil de 6 px).

Vérifié : gardien vert, compilation 4 modules, syntaxe JS (worker + chunk),
démarrage réel (health 200, /fm?folder=settings et POST /fm/settings en 401 =
routes montées), test noyau chromium (boot + latence + timeout 5 s).

## 2026-11-09 — v0.0.43 : l'onglet Paramètres passe au style Open WebUI (P91)

Demande utilisateur : « quelque chose de plus esthétique ». L'onglet n'était
qu'une textarea brute — il devient une vraie page de réglages :

- cartes arrondies par section (🤖 Modèles LLM, 📚 Recherche & RAG,
  🔒 Sécurité & préférences, 🛠 Variables avancées) ;
- champs étiquetés (micro-capitales grises), inputs arrondis, type password
  pour les clés, aide contextuelle en placeholder ;
- boutons hiérarchisés (primaire noir/blanc, fantôme, danger) ;
- mise en page fluide mobile/desktop (max-width 780 px centré).
- le POST fusionne les champs + la zone avancée (garde-fous DATA_DIR/HOME
  conservés) — la lecture réinjecte les valeurs existantes.

VALIDÉ VISUELLEMENT : captures 900×1000 et 390×844 lues — rendu conforme
aux deux formats. Leçon : un ast.parse du générateur ne valide pas le code
PRODUIT — seul py_compile du module généré tranchait (et il a attrapé deux
syntaxes fautives avant livraison).

## 2026-11-09 — v0.0.44 (en préparation, NON publiée) : execute_code pour de bon (P88 disponible)

Le mystère « le noyau Python ne démarre pas » — ÉTABLI ET CORRIGÉ :
le correctif P88 (sonde réseau bornée en JS) s'était PERDU. Mon script de
cette séance avait planté (erreur de syntaxe dans un heredoc) et NE RIEN
appliquait — P88 n'avait donc jamais quitté la planche à dessin. Le worker
embarquait l'ANCIENNE sonde urlopen au boot : son timeout=3 n'arrête pas un
fetch wasm qui pend — httpbin.org inaccessible/lent → LE BOOT RESTAIT
SUSPENDU indéfiniment. Mon banc passait (réseau rapide) — preuve à tromperie.

- P88 v2 DISPONIBLE : la sonde Python urlopen est SUPPRIMÉE du bootstrap —
  la sonde vit en JS avec AbortSignal.timeout(3000), borné par le navigateur
  lui-même : IMPOSSIBLE à court-circuiter. network_available est injecté au
  boot depuis le résultat JS. VALIDÉ : boot OK, 2+2 en 10 ms, print('hello')
  en 6 ms sur le worker réparé.
- GARDE-FOUS NOUVEAUX : (1) check_patches vérifie l'ABSENCE d'urlopen et la
  présence du marqueur du bootstrap ; (2) node --check + smoke boot déjà en
  place. Une perte de patch ne peut plus passer inaperçue.
- État : sur master, PAS DE TAG — la publication attend le signal de
  l'utilisateur (liste de demandes en cours).

## 2026-11-09 — v0.0.44 (préparation, NON publiée) : 3 demandes de l'utilisateur servies

1. P88 disponible (sonde JS bornée, plus d'urlopen au boot) — le noyau démarre
   (validé chromium : boot OK, 2+2 = 10 ms, print('hello') = 6 ms).
2. Retour au navigateur pour l'onglet Paramètres (demande #1).
3. Statut clair et utilisable des services dans /fm (demande #2) : puces
   ● actif (vert) / ○ arrêté (gris) alimentées par le service_status() réel
   (valide visuellement, mobile).
En attente du signal utilisateur pour taguer et publier.

## 2026-11-09 — v0.0.44 retag : les APK publiés portaient 0.0.43

Incident : la release v0.0.44 embarquait des APK nommés « 0.0.43 » — le bump
versionName (sed) n'avait jamais tourné avant le tag. Mes éditions lambda
chaîonnaient le bump avec d'autres opérations sans VÉRIFICATION fin-de-chaîne ;
la même faute que v0.0.23 (leçon non appliquée — récidive assumée).

Garde-fou double, « une bonne fois pour toute » :
1. scripts/verifier_tag.py — exécuté AVANT chaque tag : versionName == tag
   (sinon échec) ;
2. check_apk (CI, à la construction) : les noms d'APK produits doivent
   contenir la version du TAG — un mismatch BLOQUE la publication.

Replay : versionName → 0.0.44, release erronée supprimée, tag retiré puis
re-pointé sur le commit corrigé, build relancé.

## 2026-11-09 — v0.0.44, run 42702951060 en échec : gardes tout réélevés (P93 réparé, cause prouvée)

Traceback CI : `lire()` (ligne 143) → « Attempt to use ZIP archive that was
already closed ». Trois pannes enchaînées dans ma première mouture du garde :
1. posé hors du bloc `with zipfile` (indentation 4) — les lignes suivantes
   sortaient du contexte, `z` fermé → crash au contrôle des bundles ;
2. il écrasait `noms` (les entrées de l'APK), privant la suite des contrôles
   (.so, bundles) ;
3. Surtout, faux négatif structurel : il filtrait `noms` sur `.endswith('.apk')`
   — or un APK ne contient JAMAIS d'entrée `.apk` ; le contrôle visait la
   mauvaise donnée. La bonne : le NOM DU FICHIER livré.

Correctif (une bonne fois pour toute) :
- contrôle 9 déplacé AVANT l'ouverture du zip — porte sur `apk.name`, zéro
  risque de couper le bloc `with` ;
- tag lu via `GITHUB_REF` (déterministe sous Actions), repli
  `git describe --tags --exact-match` en local ;
- validation locale (APK factices stub identiques) : 0.0.44 → aucune erreur
  P93 ; 0.0.43 → exactement une, voie `env` comme voie `describe` ; les
  erreurs « contenu stub » restent en nombre identique.
Documentation : docs/maintenance.typ (§ CI) mis à jour + PDF recompilés ;
todo.md Phase 5 cochée. verifier_tag.py et check_patches.py restent verts.

## 2026-11-09 — v0.0.44 PUBLIÉE : garde P93 franchi, assets conformes

Run 42705082443 vert (4 min 14) : « Vérification de la chaîne APK » passe
avec le contrôle 9 (le nom des APK contient la version du tag). Release
verrouillée : OpenWebUI_Android-0.0.44-debug.apk (239 Mo) et
OpenWebUI_Android-0.0.44-release.apk (235 Mo) sous le tag v0.0.44.
Le bout de chaîne tag→versionName→noms d'APK→assets est désormais gardé aux
deux extrémités (verifier_tag.py avant, check_apk.py à la construction).
Contenu de la version : noyau fiable (P88 v2, sonde JS bornée), Paramètres
avec retour au navigateur (P91) + puces de statut réelles (P92), boutons
flottants déplaçables (P90), timeout execute_code borné et réglable
(P65/P66/P87), accusé d'exécution (P85).

## 2026-11-09 — P94 : journaux d'activité consultables/téléchargeables dans /fm (demande utilisateur)

Demande : « ajouter dans les paramètres une possibilité de voir les log de ce
qui se passe et de les télécharger pour analyser l'erreur execute_code et autre ».

Implémentation (ajouts hors amont, tout pilote depuis prepare_src.py) :
1. Module dédié android_logs.py : capture le logging Python complet (uvicorn,
   open_webui, android_main — tracebacks compris) dans data/logs/serveur.log
   et les exécutions dans data/logs/exec.log ; rotation par taille (1,2 Mo ×3),
   noms de fichiers en liste blanche (traversal impossible), stdlib seule.
2. Patch amont minimal et justifié (builtin.py, P94) : chaque execute_code
   écrit une ligne exec.log (moteur, statut réel P34, délai, tailles, extrait
   stderr 1500 car. sur échec) ; les exceptions y sont journalisées ; le tout
   enveloppé try/except — l'outil ne peut jamais échouer à cause du journal.
3. UI /fm : entrée « Journaux » dans la barre latérale, carte Journaux dans
   Paramètres (demande « dans les paramètres »), page d'aperçu (dernières
   lignes, erreurs surlignées), téléchargement par fichier ou tout en zip
   (auth requise), bouton Rafraîchir.
4. Garde attitré : 9 marqueurs P94 ajoutés à check_patches.py (module,
   handler, rotation, journal builtin, install, page, téléchargement, bouton).

Validation en réel :
- module : 12/12 (écriture/lecture, traceback capturé, traversal/noms abs
  refusés, rotation, suppression) ;
- routes sur serveur réel (harnais FastAPI + android_fm généré, port 8090,
  jamais 8080) : page journaux ✓, bouton Paramètres ✓, téléchargement
  attachment ✓, traversal 404 ✓, zip complet ✓ ;
- rendu mobile 390×760 capturé et lu : la CSS responsive du navigateur
  masquait la colonne Actions — override .logtable ajouté (bouton
  Télécharger par journal désormais visible sur téléphone).

Pièges du harnais (à rejouer si re-test) : WEBUI_SECRET_KEY, DATA_DIR et
DATABASE_URL doivent être posés (sinon SystemExit d'env.py ou SQLite
introuvable), le stub open_webui.utils doit pointer vers le vrai répertoire
(sinon json_codec « introuvable »), et les tables sont créées par
Base.metadata.create_all (migrations alembic non rejouées).

## 2026-11-09 — v0.0.45 : P94 publiée sur signal utilisateur

versionName → 0.0.45 (vérifié : verifier_tag ✓, pied de page /fm régénéré à
0.0.45, check_patches ✓). Tag v0.0.45 → build CI. Contenu : journaux
d'activité dans /fm (P94) — consultation, aperçu erreurs surlignées,
téléchargement fichier/zip, journal execute_code.

## 2026-11-09 — v0.0.45 PUBLIÉE : journaux /fm (P94) livrés

Run 42711393292 vert (4 min 47) — chaîne complète gardée : verifier_tag ✓
avant le tag, check_apk contrôle 9 ✓ à la construction, assets nommés
0.0.45 (debug 239 Mo / release 235 Mo) sous le tag v0.0.45.

## 2026-11-10 — Audit de divergence + fiabilité execute_code (v0.0.46)

Demande : comprendre les divergences avec l'amont (surtout execute_code), où
est le problème, et minimiser sans rien enlever.

**Cause racine du « Client session disconnected »** (trouvée en relisant les
divergences) : le helper de reprise `appel_avec_reprise` (P95) était GÉNÉRÉ
dans android_tools mais **jamais branché** dans builtin.py — le correctif
existait sans être câblé (exactement la classe « patch perdu silencieux »).
Deux avaries compagnes : le paramètre `timeout` (P87) n'était pas dans la
signature (NameError avalé → toujours 120 s) ; le socket ne ré-essaye pas
pour execute:python quand le réaper purge la session (120 s sans heartbeat,
WebView en arrière-plan).

Corrections (validées) :
- execute_code appelle désormais `_appel_reprise` (ré-essais bornés dans la
  fenêtre 320 s) — test unitaire : 2 échecs disconnected puis succès au 3ᵉ ;
- `timeout: int = None` ajouté à la signature (le réglage annoncé marche) ;
- gardes check_patches P95 désormais verts (ils attrapent justement le
  branchement manquant : ils étaient ROUGES et c'est eux qui ont livré la
  preuve).

**Minimisation de l'amont** (sans enlever de fonctionnalité) : la logique
d'appoint de builtin.py a été externalisée dans android_tools.py —
`remonte_fichiers_sable` (P41) et `journal_exec_appel/exception` (P94).
builtin.py passe de 249 à 223 lignes modifiées (−26) ; total amont
566 → 540 lignes. Audit reproductible : scripts/audit_divergence.py +
docs/audit-divergence.txt.

**Journaux** : désactivables à l'exécution (réglage OWUI_LOGS dans les
Paramètres, défaut on) — menu retiré + routes 404 quand off ; flux EN DIRECT
/fm/logs/live (limité à 127.0.0.1) pour lire les logs applicatifs en
continu (validé : lignes streamées en temps réel). Le \n littéral du gabarit
(PIÈGE P42) a été remplacé par chr(10) pour ne pas casser le littéral.

## 2026-11-10 — v0.0.46 PUBLIÉE : execute_code fiable + amont minimisé

Run 42719776998 vert (4 min 7) — chaîne gardée : verifier_tag ✓ + check_apk
contrôle 9 ✓ (assets nommés 0.0.46 sous le tag v0.0.46). Contenu : reprise
« Client session disconnected » branchée (P95), timeout fonctionnel (P87),
P41/P94 externalisés dans android_tools (builtin 249→223 lignes), journaux
avec flux live + désactivation OWUI_LOGS.

## 2026-11-10 — v0.0.47 : anomalies outils corrigées + traçabilité execute_code

Rapport d'anomalies utilisateur traité :
1. create_tool : la contrainte d'id (alphanumérique + underscores, pas de
   tiret) est maintenant annoncée dans la description — « diag-test-tool »
   était rejeté sans explication (source d'échec silencieux).
2. list_tools : __init__ et les fonctions _privées ne sont plus exposées
   comme « fonctions appelables » (inventaire trompeur).
3. update_calendar_event : documenté « passer start ET end ensemble » (le
   comportement « champs partiels appliqués tels quels » est confirmé, pas un
   bug — réserve levée).

Traçabilité execute_code (diagnostic du « curseur sans fin ») : trace
d'ENTRÉE (DEBUT execute_code delai=…) + trace TIMEOUT 320s. Auparavant le
journal n'était écrit qu'à la SORTIE : un blocage laissait un log vide.
Désormais, au prochain test : « DEBUT » sans sortie = blocage dans l'outil ;
rien = l'outil n'est pas invoqué (le blocage est en amont).

## 2026-11-10 — v0.0.47 PUBLIÉE

Run 42723187571 vert (5 min 54) — assets 0.0.47 conformes sous le tag
v0.0.47 (verifier_tag ✓, check_apk ✓, gardes P96 ✓).

## 2026-11-10 — v0.0.48 : diagnostic fin du blocage execute_code

Le « curseur sans fin » est tracé par logs : execute_code EST appelé (trace
DEBUT) mais ne sort jamais, sans TIMEOUT 320 s — donc il se bloque APRÈS
l'entrée et AVANT le wait_for. Le seul await entre les deux est
`Config.get('code_interpreter.engine')`. Pour trancher définitivement entre
Config.get et le premier event_call, ajouts P97 :
- `P97 engine=…` juste après Config.get ;
- `P97 event_call essai k/N` avant + `P97 essai k -> …` après chaque tentative.
Au prochain test, le journal dira exactement : « engine= » absent → Config.get
bloque ; « essai 1/16 » sans « -> » → event_call bloque ; « -> » répétés → la
reprise tourne. Aucun avertissement socket dans serveur.log → __event_call__
non atteint jusqu'ici.

## 2026-11-10 — v0.0.49 : CAUSE RACINE du blocage execute_code trouvée et corrigée

Diagnostic P97 (log réel) : `engine=pyodide` instantané (Config.get innocent),
puis `event_call essai 1 -> Client session disconnected.` après 30 s. Donc une
session EST trouvée, sio.call est lancé, mais le frontend NE RÉPOND JAMAIS.

Cause racine (frontend, bundle minifié) : le gestionnaire « events »
n'exécutait execute:python que si `u.session_id === n().id`. Or après
reconnexion, `n().id` change (nouvelle session socket) mais
`metadata['session_id']` (porté par l'appel outil) reste l'ancien → mismatch
→ le frontend IGNORAIT l'appel sans répondre → sio.call attendait 30 s →
« Client session disconnected ». C'est pour ça que la reprise (P95) ne
servait à rien : la session était bonne mais le filtre frontend rejetait.

Correctif P98 : accepter execute:python même si l'id porté est périmé (la
livraison sio.call(to=session_id) est déjà ciblée sur le bon client). Le
gestionnaire répond via l'ack `i(...)` → sio.call se résout.

## 2026-11-10 — v0.0.49 PUBLIÉE : cause racine execute_code corrigée

Assets 0.0.49 conformes. Correctif P98 (filtre session_id frontend).

## 2026-11-10 — v0.0.50 : diagnostic de session (P99) + logging élargi

0.0.49 n'a pas suffi : la trace montre DEUX modes d'échec — parfois la session
n'est pas trouvée (disconnect rapide ~2 s), parfois trouvée mais le worker ne
répond pas (~28 s). Or serveur.log était VIDE d'avertissement socket : la
capture de logging ne capte pas les loggeurs open_webui.* (les traces P97
apparaissent car elles écrivent directement dans le fichier).

Ajouts pour trancher définitivement :
- P99 : dans __event_caller__, journalise dans exec.log l'état réel du
  SESSION_POOL (sid, uid, clés) à chaque appel — on verra si la session y est ;
- capture de logging élargie (open_webui, socketio, engineio) → serveur.log
  recevra enfin les avertissements socket.

## 2026-11-10 — v0.0.51 : le worker répond enfin TOUJOURS (P99b)

Trace P99 (définitive) : session présente et correspondante (sid=QmLx_z-8Wr,
pool=['QmLx_z-8Wr']) → le serveur livre bien l'appel. Mais le frontend ne
répond jamais, puis la session tombe (pool=[]). DONC la gestion de session est
saine ; le bug est dans le WORKER Pyodide.

Cause : le onmessage du worker fait `await j(self.packages), await He(r,n,o)`
SANS try/catch. Si le chargement Pyodide (j) échoue ou rame, He n'est jamais
atteint → AUCUN postMessage de résultat → le frontend attend indéfiniment →
« Client session disconnected ». Le seul postMessage de résultat est en fin
de He, jamais atteint en cas d'échec amont.

Correctif P99b : le worker répond TOUJOURS — try/catch + bornage du chargement
Pyodide (90 s). Une erreur devient une réponse visible (stderr « ERREUR
WORKER: … ») au lieu d'un blocage silencieux.

## 2026-11-10 — v0.0.52 : ping_timeout — la session survit au chargement Pyodide

Trace P99 (v0.0.51) : la session est présente, l'appel livré, mais la session
TOMBE à ~42 s (« disconnected ») avant que le worker ne réponde. 42 s ≈
ping_interval(25) + ping_timeout(20) : le client, occupé à charger Pyodide,
ne répond plus aux pings socket.io → le serveur déconnecte → session
supprimée → « Client session disconnected ».

C'EST LA CAUSE des décrochages répétés : le keepalive socket.io (20 s) tue la
session pendant que le bac à sable démarre. Les correctifs précédents
(reprise, filtre session_id, worker-respond) étaient justes mais insuffisants
car la session était coupée avant.

Correctif P100 : WEBSOCKET_SERVER_PING_TIMEOUT 20 → 300 s. Le client occupé
a le temps de charger Pyodide sans être déconnecté ; le worker (P99b) répond
dans la foulée.

## 2026-11-10 — v0.0.53 : boot allégé (mémoire) + vidage des journaux

Hypothèse utilisateur (la bonne) : le worker est TUÉ pour mémoire. P44b forçait
['micropip','numpy','pandas','sympy'] au boot = ~115 Mo de wasm d'un coup → le
lowmemorykiller Android (ou la limite du worker) tuait le bac à sable → plus
jamais de réponse → « disconnected before answering ». C'est pourquoi TOUS les
correctifs socket tombaient : on réparait la communication pendant que le
correspondant était mort.

Correctifs :
- P102 : boot allégé ['micropip','numpy'] — pandas/sympy en chargement à la
  demande (le lazy j(self.packages) les charge si le code les importe).
- P101 : vidage des journaux (bouton 🗑 Vider dans /fm → Journaux, route
  /fm/logs/clear) — demande utilisateur.
- P101 : indicateur de démarrage (version + ping_timeout) pour vérifier le
  déploiement.

## 2026-11-10 — revue d'état : v0.0.53 publiée, chaîne verte

Revue de session (lecture seule, aucune modification de code) :
- run CI 42880590199 **vert** (4 min 48 s) sur le tag `v0.0.53` ;
- release GitHub `v0.0.53` créée avec assets nommés `OpenWebUI_Android-0.0.53-{debug,release}.apk` ;
- arbre git propre, `version_code` = 16.
Reste à faire inchangé : Phase 4 (test appareil réel — l'élément clé pour
valider les correctifs mémoire P102 / ping_timeout P100 sur `execute_code`),
Phase 5 (APK release signé, notice BSD-3), et les idées en attente
(connect-to-server, mise à jour in-app, widget).

## 2026-11-10 — v0.0.54 : P103 — boot allégé du VRAI worker (cause racine des décrochages)

Test utilisateur du 0.0.53 : « même problème » (curseur sans fin sur
execute_code). Diagnostic en deux temps.

**1. Traces temps réel** (récupérées via `/fm/logs/live` — accessible en
boucle locale sans auth — puis `/fm/logs/download` avec compte admin) :
- 20:35:23 `DEBUT execute_code delai=120s` → `engine=pyodide` → `essai 1/16`
  → `P99 pool=['HOwlfP4ERv']` : l'appel EST livré à la session ;
- AUCUNE réponse du worker — ni résultat, ni l'erreur « ERREUR WORKER » du
  bornage P99b (90 s) ;
- 20:37:49 (+146 s) : `essai 1 -> Client session disconnected` +
  « disconnected before answering » — la session socket meurt ;
- ensuite `pool=[]` DÉFINITIF (essais 2→12 « not owned … or disconnected ») :
  le frontend ne se **reconnecte jamais**. Or MainActivity ne gère pas
  `onRenderProcessGone` → un tuage du processus rendu ferait crasher l'appli
  entière (serveur compris). Le serveur répondait toujours : la WebView est
  **gelée**, pas morte. Timing cohérent avec un client silencieux dès ~+120 s
  (ping 25 + timeout 20 ≈ 145 s).

**2. Forensique de l'APK réellement installé**
(`Download/OpenWebUI_Android-0.0.53-release.apk` — version confirmée par la
page /fm : `_FM_VERSION=0.0.53`). LE PIÈGE DES DEUX COPIES : le bundle
embarque la logique du bac à sable Pyodide en deux exemplaires —
- `workers/pyodide.worker-*.js` : worker persistant, instancié par
  `new Worker(new URL(…))` — **c'est lui qui s'exécute**
  (`ENABLE_PYODIDE_FILE_PERSISTENCE` forcé à true) ;
- `chunks/wN8N8j40.js` : copie de repli « universel » (iframe/blob), jamais
  atteinte dans notre configuration.
Constat : le worker embarqué chargeait ENCORE
`packages:["micropip","numpy","pandas","sympy"]` (~115 Mo de wasm) —
**P102 (v0.0.53) n'avait allégé que la copie de repli** (le patch ciblait
`patch_pyodide_universel` = les chunks). Le worker s'étouffait au boot
(OOM/thrashing), son thread bloqué ne pouvait même pas exécuter le timer de
secours P99b (setTimeout inatteignable) → silence total → gel UI → session
tuée. Tous les correctifs socket des versions précédentes réparaient la
communication pendant que le correspondant était asphyxié.

Cause racine UNIQUE de tous les « disconnected before answering » : boot
lourd du worker.

Correctifs :
- **P103** : boot allégé du worker `packages:["micropip","numpy"]`
  (pandas/sympy en chargement à la demande via `j(self.packages)` — la
  détection de paquets P46 côté frontend les installe si le code les importe).
  Appliqué dans `src-assets/` (asset embarqué) ET dans `scripts/prepare_src.py`
  (`patch_pyodide_worker_boot`, juste après P38 qui rejoue le boot lourd).
- **Contrôle `check_patches.py`** (évolution justifiée — règle du 2026-11-08) :
  l'ancien contrôle P38 EXIGEAIT le boot lourd dans le worker — il validait
  l'état défectueux et aurait bloqué P103 (faux négatif avéré). Désormais :
  boot allégé exigé dans les DEUX copies (worker + chunks), boot lourd rejeté
  partout.
- `versionName` 0.0.53 → 0.0.54.
- Docs : `PATCHES.md` (section « le piège des deux copies » + tableau
  P38/P44b/P102/P103), `docs/maintenance.typ` (dépannage + table des patchs,
  PDF recompilé).
