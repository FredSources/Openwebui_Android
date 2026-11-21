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

## 2026-11-10 — v0.0.54 PUBLIÉE : boot allégé du worker confirmé dans l'APK livré

Run 42891888099 **vert** (conclusion success) sur le tag `v0.0.54` — chaîne
gardée : verifier_tag ✓ + check_apk (contrôle 9) ✓. Release `v0.0.54` avec
assets nommés `OpenWebUI_Android-0.0.54-{debug,release}.apk`.

Contrôle de contenu de l'asset release téléchargé (au-delà des noms) :
`packages:["micropip","numpy"]` dans le worker **et** dans la copie de repli —
le boot lourd a disparu de l'artefact livré. Attendu au prochain test
appareil : `execute_code` répond (numpy disponible, pandas/sympy chargés à la
demande), session socket stable, plus de « disconnected before answering ».

## 2026-11-10 — v0.0.55 : P104 — la livraison ciblée par sid ne livre JAMAIS (diagnostic)

Suite du test « même problème » (v0.0.54) : le bac à sable répond parfaitement
quand on le pilote directement (sonde navigateur : `print(2+3)` → `stdout:"5\n"`
en 3,5 s — worker ET iframe testés), la chaîne frontend complète aussi
(injection d'une trame `execute:python` dans le client socket.io réel : handler
→ `Me()` → sable → réponse), mais **la trame envoyée par le serveur n'arrive
jamais au client**.

Faits établis (sondes Playwright + client python-socketio, trames WebSocket
capturées) :
1. `execute_code` EST appelé (trace DEBUT), la session est dans le pool, et
   `sio.call('events', …, to=sid)` est lancé vers le bon sid ;
2. le client ne reçoit **jamais** la trame `execute:python` — même un client
   python-socketio pur, connecté, en heartbeats, pendant 4 minutes ;
3. les émissions de *room* (streaming des chats, acks `43x`) arrivent
   normalement — seules les émissions **ciblées par sid** sont perdues ;
4. la même chaîne (module `socket.main` réel de l'app, même `JSONOnlyPacket`,
   même codec orjson, mêmes options, mêmes versions libs) **fonctionne hors
   Android** — livraison et ack en moins d'une seconde ;
5. aucun « Cannot send to sid » (engineio) dans les journaux : le paquet est
   remis à `socket.send()` sans erreur signalée ;
6. les sessions meurent ensuite (disconnect) ou passent au timeout 320 s —
   d'où les « Client session disconnected » et le « bac à sable muet ».

Le piège des deux copies (P102/P103) était réel mais n'était donc pas la seule
cause : malgré le boot allégé, la commande n'est jamais délivrée.

**P104 — instrumentation de la livraison** (ce commit) :
- `sio._send_packet` est enveloppé : tout paquet EVENT avec id d'ack remis au
  transport est journalisé (`P104 SEND eio=… id=…`) avec ses erreurs ;
- `P104 ETAT` : les participants RÉELS du manager au moment de l'appel ;
- `P104 disconnect` : la raison de chaque déconnexion socket ;
- `P104 auth socket` : les échecs d'authentification qui déconnectent la session ;
- route d'auto-test **`/fm/diag/eventcall`** (admin, boucle locale) : l'app
  s'envoie `execute:python` à elle-même et renvoie la réponse + l'état interne —
  test de la chaîne complète à la demande, sans intervention sur l'écran.

`versionName` 0.0.55 ; `check_patches.py` contrôle les 4 marqueurs P104
(évolution justifiée : sans ces traces, tout test appareil reste muet).

## 2026-11-10 — v0.0.55 PUBLIÉE : instrumentation P104 disponible

Run 42918112871 **vert** (conclusion success) sur le tag `v0.0.55` — chaîne
gardée : verifier_tag ✓ + check_apk ✓. Assets `OpenWebUI_Android-0.0.55-{debug,release}.apk`.
Attendu au prochain test : `/fm/diag/eventcall` répond (auto-test) et les
traces `P104 SEND/ETAT/disconnect` localisent la perte du paquet ciblé.

## 2026-11-11 — v0.0.56 : P105 — CAUSE RACINE DÉFINITIVE des « bac à sable muet »

Les traces P104 (v0.0.55) ont tranché immédiatement : à l'appel réel,
`P104 SEND` suivi de **`P104 SEND-ERREUR : Object of type bytes is not JSON
serializable`**. Le paquet d'appel outil contient des **octets bruts** —
`_uploads_pour_sable` (P51/P77) joint les petits fichiers du dossier uploads
(≤ 64 Ko) en `{'name': …, 'data': ent.read_bytes()}` — et `Packet.encode()` ne
sait pas sérialiser les octets : `json.dumps` lève une exception, la tâche
d'envoi meurt dans `asyncio.wait(tasks)` qui avale l'erreur, et **le paquet ne
part jamais** → l'appel pend jusqu'au timeout 320 s (« bac à sable muet ») ou
à la mort de la session.

C'EST la cause unique de TOUS les échecs depuis le début : tant que le dossier
uploads est vide, execute_code marche (d'où les tests « simples » qui
passaient parfois et l'auto-test v0.0.55, `files: []`, en 0,0 s) ; dès qu'un
petit fichier s'y trouve (CSV, image…), TOUS les appels meurent silencieusement.
Les correctifs socket/mémoire précédents (P95-P103) traitaient des conséquences.

**P105** : dans `__event_caller__`, tout octet du payload est converti en
liste d'entiers (`_p105_json_sur`, récursif) — forme JSON, acceptée telle
quelle par le frontend (`new Uint8Array(r.data)` dans le worker). Le
diagnostic reste actif : `P104 SEND-ERREUR` signalerait toute récidive.
`check_patches.py` vérifie le marqueur `_p105_json_sur`. `versionName` 0.0.56.

## 2026-11-11 — v0.0.56 PUBLIÉE : le payload des appels outils est JSON-sûr

Run 42921767989 **vert** (conclusion success) sur le tag `v0.0.56` — chaîne
gardée : verifier_tag ✓ + check_apk ✓. Assets `OpenWebUI_Android-0.0.56-{debug,release}.apk`.
Attendu au test appareil : `execute_code` répond même avec des fichiers dans le
dossier uploads et du code pandas/matplotlib ; `P104 SEND` sans `SEND-ERREUR`.

## 2026-11-11 — v0.0.56 VALIDÉE sur appareil + cause racine expliquée

**Validation utilisateur** (transcription de session conservée par l'utilisateur) :
execute_code répond systématiquement — `status: success` sur tous les tests :
- contrôles numpy/pandas/matplotlib (Python 3.14.2, Emscripten-5.0.3-wasm32) ✓ ;
- pandas DataFrame + calculs (somme des carrés = 285) ✓ ;
- matplotlib : PNG écrit (43,7 Ko) + CSV relu ✓ ;
- liste de /mnt/uploads, réseau bloqué (OSError attendu) ✓ ;
- écriture fichier persist_test.txt ✓.
Aucun « bac à sable muet », aucun timeout 320 s. **Le bug historique est clos.**

### Le bug corrigé (P105) — explication de référence

Le serveur envoyait au bac à sable une commande d'exécution qui embarquait les
petits fichiers du dossier uploads (P51/P77 : « découvrabilité », ≤ 64 Ko)
sous forme d'**octets bruts** (`data: ent.read_bytes()`). Cette commande doit
être encodée en JSON pour partir sur le WebSocket ; or `json.dumps` refuse les
octets (`Object of type bytes is not JSON serializable`). L'exception tuait la
tâche d'envoi, **avalée par `asyncio.wait(tasks)`** (aucune trace, aucun
journal) : le paquet ne partait jamais, l'appel restait suspendu jusqu'au
timeout 320 s (« bac à sable muet ») ou à la mort de la session.

Effet « parfois ça marche » : dossier uploads vide → aucun octet → succès ;
un seul petit fichier présent → échec systématique. Tous les correctifs
précédents (P95-P103 : reprise, sessions, mémoire, ping) traitaient des
**conséquences** de paquets jamais envoyés — d'où leur inefficacité.

Correctif : `_p105_json_sur` (dans `__event_caller__`) convertit récursivement
tout octet du payload en liste d'entiers — forme JSON reconstruite côté client
par `new Uint8Array(r.data)`. Le traçage `P104 SEND-ERREUR` (v0.0.55) arme la
détection de toute récidive.

### Suite ouverte — remontée des fichiers (P41) : à traiter

La transcription de test montre que les fichiers écrits dans `/mnt/uploads` par
le code Python **ne sont pas remontés** : `files: []` dans toutes les réponses,
`display_file` répond « Fichier introuvable », et les écritures ne semblent pas
persistées entre deux exécutions (le PNG du run n'apparaît plus au run suivant ;
seuls les fichiers d'entrée injectés y figurent). Pistes : le ramassage du
worker (`__inNames`/`__snap` qui sautent les fichiers d'entrée ou inchangés),
la persistance IDBFS (`A()`/syncfs), et le format des données (base64 côté
worker vs listes depuis P105). À investiguer au prochain tour — le périmètre
reste le bac à sable, l'outil répondant désormais correctement.

## 2026-11-11 — v0.0.57 : P106 — la voie worker du bac à sable n'avait JAMAIS tourné

Suite de la validation v0.0.56 (execute_code répond ✓) : les fichiers écrits
dans `/mnt/uploads` ne remontent pas (`files: []`), `display_file` répond
« Fichier introuvable », et les écritures ne survivent pas à l'exécution
suivante (seuls les fichiers d'entrée sont présents).

**Diagnostic (piège des deux copies — 3ᵉ occurrence)** : l'appli exécute le
bac à sable dans la copie **iframe** (`chunks/*.js`) — qui ne contient NI le
ramassage des fichiers produits (P41), NI la persistance IDBFS (P51), NI le
bornage d'erreur (P99b). Ces patchs vivent uniquement dans le **worker**
(`workers/pyodide.worker-*.js`)… qui n'est JAMAIS instancié. Pourquoi : le
bundle crée le bac à sable au chargement du module (`__prewarm` → `cp()`), or
`cp()` lit `features.enable_pyodide_file_persistence` dans la config — pas
encore chargée à cet instant → `undefined` → la copie iframe est choisie puis
mise en cache pour toute la vie de la page. L'API renvoie pourtant bien
`enable_pyodide_file_persistence: True` (vérifié sur `/api/config`), et
`android_main` force l'environnement (P44) — mais la décision est prise trop
tôt. Constat d'écoute : aucune des traces « ERREUR WORKER » (P99b) n'a jamais
apparu — cohérent : le code P99b n'était pas exécuté.

**P106** : la voie worker est forcée dans le bundle (`const cp=()=>new hp`) —
la seule voie complète (ramassage, persistance, bornage, boot allégé P103).
`check_patches.py` vérifie le forçage et rejette la décision conditionnelle
(évolution justifiée : le contrôle P44 ne vérifiait que la variable
d'environnement, jamais la décision réelle du bundle).

### Leçon d'architecture (question utilisateur, 2026-11-11) — pourquoi deux copies ?

Open WebUI d'origine embarque la logique du bac à sable en DEUX MODES : le
*worker* (persistant, IndexedDB) et le *repli universel* (iframe/blob, éphémère)
pour les navigateurs sans IndexedDB. Le bundleur les empaquette différemment
(entrée worker minifiée vs texte brut dans un chunk), mais ils sortent de la
MÊME source au build : identiques par construction, et le choix se fait « à la
demande » au premier execute_code, quand la config est chargée — donc jamais
faussé en amont.

Le bug du projet n'est pas amont : il est venu de NOS patchs.
(1) P70/P71 (préchauffage) crée le bac à sable AU CHARGEMENT DE LA PAGE, avant
la config → le drapeau enable_pyodide_file_persistence est undefined → la
copie de repli est choisie et cachée à vie. (2) Nos correctifs furent posés par
remplacement de chaînes sur un exemplaire à la fois : les bons patchs (P41
ramassage, P51 persistance, P99b bornage) allèrent dans le worker, jamais
exécuté. (3) Les contrôles validaient le fichier patché, pas la copie exécutée.

Règles qui découlent : ne jamais créer un ressort avant que sa configuration
soit disponible ; tout patch de la logique du bac à sable doit viser la copie
exécutée (worker forcé par P106) et le contrôle doit porter sur la décision
effective du bundle.

## 2026-11-11 — v0.0.58 : P70 révoqué — le préchauffage retiré (décision utilisateur)

Demande utilisateur : « on peut enlever le préchauffage ». Oui — et c'est
mieux : avec P106 (voie worker forcée) le préchauffage n'apportait plus qu'environ
3 s sur le premier appel, au prix d'un écart avec l'amont et de mémoire wasm
résidente en continu. Surtout, il était l'AMORCE du bug des deux copies (créer
le bac à sable avant la config). Retiré : le bac à sable est créé à la demande,
au premier execute_code, comme en amont — la config est chargée à ce moment-là,
toute la classe de bugs « décision avant config » disparaît. P71a (instantané
des fichiers d'entrée, plafonds de remontée) est conservé. `versionName` 0.0.58.

## 2026-11-11 — v0.0.58 PUBLIÉE : préchauffage retiré, voie worker forcée

Run 42927630348 **vert** (conclusion success) sur le tag `v0.0.58` — chaîne
gardée : verifier_tag ✓ + check_apk ✓. Assets `OpenWebUI_Android-0.0.58-{debug,release}.apk`.
Contenu : P106 (voie worker forcée — ramassage P41 + persistance IDBFS enfin
exécutés) + P70 révoqué (bac à sable créé à la demande, comme en amont).
Attendu au test appareil : fichiers écrits dans /mnt/uploads visibles dans le
gestionnaire et retrouvés par display_file, écritures persistantes entre
exécutions ; premier appel plus lent de 3-5 s (montage wasm à la demande).

## 2026-11-11 — v0.0.59 : P107 — le paramètre TO restauré (régression de la v0.0.58)

Test appareil v0.0.58 : « execute_code frontend: TO is not defined » —
régression de MA révocation de P70 : le paramètre `TO=120` (délai
d'exécution) était introduit par le MÊME remplacement que le préchauffage ;
retirer le bloc en entier a laissé un corps de fonction qui référence TO sans
le déclarer (transmission `exec_timeout: TO` + minuteur « Execution timeout
apres … »). Correctif P107 : le paramètre est restauré, le préchauffage reste
révoqué. `check_patches.py` vérifie désormais la signature complète de `Me()`
(évolution justifiée : un contrôle par marqueur ne voyait pas qu'une révocation
emportait un fragment utile). `versionName` 0.0.59.

Note positive : l'erreur est remontée IMMÉDIATEMENT à l'écran et dans les
traces — la chaîne de diagnostic (P104/P105) fonctionne comme prévu.

## 2026-11-11 — v0.0.59 PUBLIÉe : signature Me() complète, test fichiers attendu

Run 42929234033 **vert** (conclusion success) sur le tag `v0.0.59` — chaîne
gardée : verifier_tag ✓ + check_apk ✓. Assets `OpenWebUI_Android-0.0.59-{debug,release}.apk`.
Contenu cumulé depuis la v0.0.56 validée : P106 (voie worker forcée), P70
révoqué (création à la demande), P107 (paramètre TO restauré). Attendu au
test appareil : exécutions OK + fichiers écrits dans /mnt/uploads visibles au
gestionnaire, retrouvés par display_file, persistants entre exécutions.

## 2026-11-11 — v0.0.60 : P108 — fichiers produits enregistrés + statut juste

Tests v0.0.59 (transcription utilisateur) : execute_code fonctionne, et le
ramassage marche (`files: ["test_plot.png"]`, PNG 29 124 octets) — P106 validé.
Deux défauts restants, corrigés ici :

1. **Le fichier produit reste invisible** : `remonte_fichiers_sable` écrivait
   le fichier sur disque (UPLOAD_DIR) mais ne créait AUCUNE fiche dans la base —
   or le gestionnaire /fm, display_file et l'API fichiers listent la base.
   D'où le « pas visible et accessible » d'origine. Correctif : chaque fichier
   produit est stocké via `Storage.upload_file` et enregistré par
   `Files.insert_new_file` (même patron que compile_typst), avec nom affichable,
   type MIME et taille — et l'appel devient `await remonte_fichiers_sable(...,
   user_id)`.
2. **`status: error` sur les réussites** : `echec = bool(stderr)` — le warning
   bénin Emscripten « FS.syncfs operations in flight at once » (deux écritures
   de persistance lancées en même temps — la voie worker, nouvellement
   exercée, est la première à faire tourner la persistance) atterrissait dans
   stderr et faussait le verdict. Correctif : ces avertissements sont filtrés
   avant le calcul du statut.

`check_patches.py` vérifie les trois marqueurs (enregistrement, filtre, appel
async). `versionName` 0.0.60.

## 2026-11-11 — v0.0.60 PUBLIÉE : fichiers enregistrés, statut juste

Run 42932395264 **vert** (conclusion success) sur le tag `v0.0.60` — chaîne
gardée : verifier_tag ✓ + check_apk ✓. Assets `OpenWebUI_Android-0.0.60-{debug,release}.apk`.
Attendu au test appareil : `status: success` sur les réussites (plus de warning
FS.syncfs filtré), fichiers produits visibles au gestionnaire /fm, retrouvés par
display_file, persistants entre exécutions.

## 2026-11-11 — v0.0.60 VALIDÉE — objectifs de la session atteints

Validation utilisateur : « c'est bon » — execute_code fonctionne, les fichiers
sont visibles, le statut est juste. Le seul message restant
(« The inference service is overloaded ») vient du SERVICE D'INFÉRENCE DISTANT
(HTTP 429 rate_limited sur opencode.ai/DeepSeek — vu aussi dans serveur.log) :
hors périmètre de l'appli, correctif = réessayer plus tard ou changer de
modèle. L'appli remonte l'erreur proprement.

Bilan de la session du 2026-11-10/11 — six correctifs, tous validés :
- P103 (v0.0.54) : boot allégé du worker (mémoire) ;
- P104 (v0.0.55) : instrumentation de la livraison (SEND/ETAT/disconnect,
  route /fm/diag/eventcall) — c'est elle qui a fait sortir l'erreur cachée ;
- P105 (v0.0.56) : CAUSE RACINE des « bac à sable muet » — octets bruts non
  JSON-sérialisables dans le payload → l'envoi mourait silencieusement ;
- P106 (v0.0.57) : voie worker forcée — 3ᵉ occurrence du piège des deux copies
  (ramassage P41 + persistance IDBFS enfin exécutés) ;
- P70 révoqué (v0.0.58) : préchauffage retiré (il amorçait le bug des copies) ;
- P107 (v0.0.59) : paramètre TO restauré (régression de la révocation) ;
- P108 (v0.0.60) : fichiers produits ENREGISTRÉS (base + stockage) et statut
  débarrassé des avertissements FS bénins.

Prochaine étape naturelle : Phase 4 du plan initial — campagne de tests
appareil complets (chat, dictée, recherche, upload+RAG, Typst, tenue en
arrière-plan), puis Phase 5 (APK release signé, notice BSD-3, tag de livraison).

## 2026-11-11 — Phase 4 : campagne de tests appareil (partie automatisée)

Batterie exécutée depuis Termux contre l'appareil réel (appli v0.0.60 installée) :

| Test | Résultat |
|---|---|
| Installation / version servie | ✅ v0.0.60 (marqueur P101 au démarrage) |
| Santé serveur (`/health`) | ✅ `{"status":true}` |
| Taille APK release | ✅ 235,7 Mo |
| Démarrage (import → scheduler) | ✅ ~1 s (P101 01:40:14 → scheduler 01:40:15) |
| Chat en streaming (modèle distant OpenAI-compatible) | ✅ validé ×10 (sondes de session) |
| `execute_code` (21 réussites cumulées) + persistance fichiers | ✅ |
| Fichiers produits → gestionnaire (`test_matplotlib.png`, `diagnostic_typst_test.pdf`) | ✅ enregistrés, listés, téléchargeables |
| Upload de fichier (API + visibilité `/fm`) | ✅ `p4-test.txt` listé |
| Recherche web SearXNG embarquée (`/search?q=test&format=json`) | ✅ résultats réels |

Reste au MANUEL (l'utilisateur) : dictée (micro + permissions), coupure réseau
(mode avion), tenue en arrière-plan (foreground service), relance après reboot,
ressenti de fluidité/RAM. Consignés dans todo.md (Phase 4 en cours).

## 2026-11-11 — Verdict utilisateur Phase 4 : « pas exactement le résultat attendu mais me convient »

Réserve utilisateur notée sans objection — analyse de l'écart principal,
la TAILLE DE L'APK : l'objectif documenté (« ≈ 150 Mo ») date de l'époque P13
où le runtime Pyodide avait été RETIRÉ du frontend ; P23 l'a restauré
(61 Mo annoncés, 84,4 Mo réels aujourd'hui dans `assets/frontend/pyodide/`
avec les paquets scientifiques) pour rendre `execute_code` possible — d'où un
APK à 235,7 Mo. L'écart est donc le COÛT DU BAC À SABLE fonctionnel, non une
régression. Ajustement de la documentation : la table des performances devra
mentionner cette composante. Leviers futurs si la taille devient un sujet :
alléger le dépôt de paquets Pyodide embarqués (scipy/sklearn/statsmodels non
utilisés par l'utilisateur), ou proposer un APK « léger » sans bac à sable.

Décision : la taille actuelle est acceptée (« elle me convient ») ; on avance.

## 2026-11-11 — v0.0.61 : P109 — refonte du gestionnaire /fm et de l'écran Paramètres

Demande utilisateur — le gestionnaire de fichiers est refondu :

1. **Sidebar PERMANENTE** (toutes les pages, aperçu compris) avec arbre
   « Fichiers » au même niveau que Paramètres, s'ouvrant sur : Tous, PDF,
   Images, **Typst**, **Markdown**, Autres (catégories `_fm_kind` élargies,
   Typst et Markdown sortis de « documents »).
2. **Filtre d'origine** des fichiers : *Les deux* / *En base* (fiches) /
   *Sur disque* (orphelins) — paramètre `src=`, conservé par la recherche et
   la pagination.
3. **Bouton de retour fixe en HAUT à droite** (toujours présent, déplaçable),
   et suppression des liens « ← retour/navigateur/paramètres/maintenance »
   redondants (la sidebar suffit) — seuls restent la pagination et « réessayer ».
4. **Écran Paramètres en 2 onglets** : `Open WebUI` et `SearXNG`, chacun avec un
   **point vert/rouge d'état** à côté du nom, puis un **champ service**
   (démarrer / arrêter / redémarrer) et plus bas les **réglages utiles** —
   SearXNG : formats (html/json), limiter, clé secrète (empreinte +
   régénération) ; Open WebUI : modèles, RAG, sécurité, variables avancées,
   journaux. Le POST `/fm/settings` gère les deux onglets
   (`searxng_settings_load/save` ajoutés dans `android_main.py`).
   `versionName` 0.0.61.

## 2026-11-11 — v0.0.61 PUBLIÉE : refonte /fm + Paramètres à 2 onglets

Run 43011249950 **vert** (conclusion success) sur le tag `v0.0.61` — chaîne
gardée : verifier_tag ✓ + check_apk ✓. Assets `OpenWebUI_Android-0.0.61-{debug,release}.apk`.
À valider à l'écran : arbre Fichiers (PDF/Images/Typst/Markdown/Autres), filtre
base/disque/les deux, sidebar permanente, retour en haut à droite, onglets
Paramètres Open WebUI/SearXNG avec points d'état et champ service.

## 2026-11-11 — v0.0.62 : P110 — cohérence des écrans /fm, onglets étendus, FAB synchronisé

Retours utilisateur sur la refonte v0.0.61, tous traités :

1. **Cohérence Open WebUI / SearXNG** : même conteneur `.settings` (largeur
   identique), mêmes classes de boutons par rôle, cases à cocher alignées
   (classe `.chk`, une par ligne).
2. **Plus de clé secrète** pour l'instance SearXNG locale : la section (affichage
   + génération) est retirée de l'écran, et le POST ne peut plus régénérer la
   clé — elle reste interne au fichier de réglages, jamais exposée.
3. **Maintenance et Journaux en onglets sous Paramètres** : barre commune
   `Open WebUI | SearXNG | Maintenance | Journaux` sur les quatre écrans,
   avec points vert/rouge d'état sur les deux services ; la sidebar porte les
   deux arbres (Fichiers + Paramètres).
4. **Bouton bleu de bascule /fm ↔ Open WebUI** : même position par défaut
   (haut à droite) sur les deux écrans, déplaçable, et **synchronisé** — les
   deux lisent/écrivent la même clé `fabPos` (fini `fabPosFm`/`fabPosSpa`).
   `versionName` 0.0.62.

## 2026-11-11 — v0.0.62 PUBLIÉE : écrans cohérents, onglets étendus, FAB synchronisé

Run 43015709291 **vert** (conclusion success) sur le tag `v0.0.62` — chaîne
gardée : verifier_tag ✓ + check_apk ✓. Assets `OpenWebUI_Android-0.0.62-{debug,release}.apk`.
À valider à l'écran : largeurs/boutons/cases cohérents entre Open WebUI et
SearXNG, absence de clé secrète, onglets Maintenance/Journaux sous Paramètres,
bouton bleu au même endroit et synchronisé entre /fm et Open WebUI.

## 2026-11-11 — v0.0.63 : P111 — journaux unifiés, suivi automatique, journalisation off par défaut

Retours utilisateur, tous traités :

1. **Mêmes logs partout** : l'écran Journaux ne montrait qu'un fichier (300
   lignes) quand le flux live montrait tous les journaux fusionnés —
   l'écran affiche désormais la **fusion** (notation « fichier | ligne », limite
   la plus généreuse : 300 lignes par fichier), le bouton **Live** est retiré de
   l'interface (la route reste pour les diagnostics).
2. **Suivi automatique** : la vue se rafraîchit toutes les 3 s et se cale sur
   les **dernières lignes** (barre de défilement en bas) — endpoint
   `/fm/logs/tail` (texte brut).
3. **Journalisation DÉSACTIVÉE par défaut** (accord utilisateur) : la case
   « désactiver la journalisation » est pré-cochée au premier affichage ; les
   écritures sont réellement coupées (garde dans `_ecrire`), effet immédiat +
   mémorisé (`OWUI_LOGS=on/off` dans `data/openwebui.env`).
4. **Évacuation réseau des journaux désactivable** : case dédiée
   (`OWUI_LOGS_NET`, active par défaut) — quand elle est cochée, les routes de
   téléchargement/zip/flux live répondent 404. `versionName` 0.0.63.

## 2026-11-11 — v0.0.63 PUBLIÉE : journaux unifiés, suivi automatique, journalisation off par défaut

Run 43020910431 **success** (4 min 36 s) sur le tag `v0.0.63` — chaîne gardée :
verifier_tag ✓ + check_apk ✓. Assets `OpenWebUI_Android-0.0.63-{debug,release}.apk`
(publiés ; incident mineur de suivi CI — EOF réseau — sans effet sur le build).
À valider à l'écran : fusion des journaux, suivi automatique calé en bas,
journalisation désactivée par défaut (case pré-cochée), évacuation réseau
désactivable.

## 2026-11-11 — v0.0.64 : P112 — l'onglet Journaux est l'unique entrée

Demande utilisateur : « il faut la tab log pour pouvoir les activer et les
visualiser ; dans le tab openwebui enlève le lien vers les journaux ».
L'onglet **Journaux** centralise donc : la bascule d'activation (et
l'évacuation réseau) et la visualisation ; la carte « Journaux » de l'onglet
Open WebUI est retirée (redondante). Le contrôle P94 est recentré sur
l'onglet (`folder=logs`) au lieu de l'ancien bouton — évolution justifiée :
le point d'entrée s'est déplacé, pas disparu. `versionName` 0.0.64.

## 2026-11-11 — v0.0.64 PUBLIÉE : l'onglet Journaux est l'unique entrée

Run 43024354592 **success** sur le tag `v0.0.64` — chaîne gardée : verifier_tag ✓
+ check_apk ✓. Assets `OpenWebUI_Android-0.0.64-{debug,release}.apk`.
À valider : l'onglet Journaux active + affiche les journaux ; l'onglet Open
WebUI ne contient plus de lien vers les journaux.

## 2026-11-11 — v0.0.65 : P113 — l'onglet Journaux n'était pas visible (œuf et poule)

Bug vu à l'écran (sonde Playwright sur l'appareil) : la barre d'onglets
n'en montrait que trois (Open WebUI, SearXNG, Maintenance) — l'onglet
**Journaux avait disparu**. Cause : P111 rend la journalisation
DÉSACTIVÉE par défaut, or le code masquait l'onglet Journaux quand
`_journaux_actifs()` est faux → la réactivation depuis l'UI était
impossible (cul-de-sac : l'écran « Journaux désactivés » n'offrait aucune
bascule). Correctif : l'onglet (sidebar + barre) est désormais TOUJOURS
présent, et l'écran Journaux s'affiche même sans journalisation — les
bascules d'activation y sont, c'est leur place. `versionName` 0.0.65.

Note de méthode : la capture d'écran de la version installée a permis de
VOIR le bug que la lecture de code n'avait pas vu — à refaire après chaque
refonte d'UI.

## 2026-11-11 — v0.0.65 PUBLIÉE : onglet Journaux permanent

Run 43027272430 **success** sur le tag `v0.0.65` — chaîne gardée : verifier_tag ✓
+ check_apk ✓. Assets `OpenWebUI_Android-0.0.65-{debug,release}.apk`.
Attendu : 4 onglets visibles (Open WebUI, SearXNG, Maintenance, Journaux) même
sans journalisation ; bascules d'activation présentes sur l'écran Journaux.
Vérification par capture d'écran après installation de l'utilisateur.

## 2026-11-11 — v0.0.66 : P114 — « Internal Error » à l'activation des journaux

Retour utilisateur : activer la journalisation provoque une erreur interne.
Cause : la route `/fm/logs/toggle` (P111) utilisait `os.environ` alors que
`android_fm.py` n'importe `os` que sous l'alias `_osj` → `NameError` → 500.
Corrigé (`_osj.environ`), vérifié dans le module généré (plus aucune
référence à `os.`), contrôles verts. `versionName` 0.0.66.

## 2026-11-11 — v0.0.66 PUBLIÉE : bascule de journalisation fonctionnelle

Run 43029835799 **success** sur le tag `v0.0.66` — chaîne gardée : verifier_tag ✓
+ check_apk ✓. Assets `OpenWebUI_Android-0.0.66-{debug,release}.apk`.
Attendu : activation/désactivation des journaux sans erreur interne, effet
immédiat, vue fusionnée qui se remplit. Vérification par capture après
installation.

## 2026-11-11 — v0.0.67 : P115 — 2ᵉ cause du « Internal Error » de la bascule

Toujours en erreur après la v0.0.66 (vérifié par appel direct : POST
`/fm/logs/toggle` → 500, version 0.0.66 servie). Analyse du module généré :
la route appelait `_Red(...)`, alias LOCAL de la route « Vider » — le module
importe `RedirectResponse as _Redirect` : `NameError` → 500. Corrigé et
vérifié dans le module généré (0 occurrence de `_Red(` dans la route,
`_Redirect` présent). Le journal serveur n'était pas consultable pendant le
défaut (journalisation off par défaut — paradoxe de diagnostic) ; les
prochains défauts de route devraient être habillés d'une trace visible.
`versionName` 0.0.67.

## 2026-11-11 — v0.0.68 : P116 — boutons Activer/Désactiver pour les journaux

Préférence utilisateur : « je préfère des boutons activer les logs que
désactiver les logs ». Les cases à cocher de l'écran Journaux sont remplacées
par quatre boutons (▶ Activer les logs / ⏹ Désactiver les logs / ▶ Activer
l'évacuation réseau / ⏹ Désactiver l'évacuation réseau), même style que le
champ Service, avec l'état visible (points vert/rouge : Logs actifs /
désactivés, Évacuation réseau active / désactivée). La route
`/fm/logs/toggle` reçoit désormais `action=logs_on|logs_off|net_on|net_off`.
`versionName` 0.0.68.

## 2026-11-11 — v0.0.68 PUBLIÉE : boutons Activer/Désactiver pour les journaux

Run 43033249652 terminé (exit 0) sur le tag `v0.0.68` — assets
`OpenWebUI_Android-0.0.68-{debug,release}.apk` publiés. Attendu à l'écran :
état vert/rouge visible + quatre boutons ▶/⏹ (logs, évacuation réseau),
aucune case à cocher, effet immédiat.

## 2026-11-11 — v0.0.69 : P117 — Journalisation en deux colonnes, erreurs en modale

Demandes utilisateur, toutes traitées :

1. **Séparation verticale** dans la carte Journalisation : colonne « Logs
   fichier » (activer/désactiver l'écriture) | colonne « Logs réseau »
   (activer/désactiver l'évacuation), filet vertical entre les deux.
2. **« Vider » toujours possible** : la route `/fm/logs/clear` ne dépend plus
   de la journalisation — on nettoie les journaux même quand l'écriture est
   désactivée (bouton dédié sur l'écran Journaux).
3. **Erreurs en MODALE** : les actions (basculer, vider) passent par `fmPost`
   (fetch) et toute erreur s'affiche dans une popup `fmErr` **sans changement
   de page** — succès = rechargement de la page en place.
4. **Transparence de la config** : `OWUI_LOGS` et `OWUI_LOGS_NET` disparaissent
   des réglages Open WebUI (champs et « Variables avancées ») — ils sont gérés
   uniquement par l'onglet Journaux, cohérents avec l'activation des logs.

Note de fabrication : plusieurs régressions d'échappement de guillemets dans
le gabarit généré (« Perhaps you forgot a comma ») — la chaîne FM_CODE exige
des doubles antislashs ; consolidé et vérifié par compilation du module
généré. `versionName` 0.0.69.

## 2026-11-11 — v0.0.69 PUBLIÉE : Journalisation en deux colonnes, erreurs en modale

Run 43038776353 **success** sur le tag `v0.0.69` — chaîne gardée : verifier_tag ✓
+ check_apk ✓. Assets `OpenWebUI_Android-0.0.69-{debug,release}.apk`.
Attendu : carte Journalisation en deux colonnes (fichier | réseau) séparées
verticalement, « Vider » actif même sans journalisation, erreurs en modale
sans changement de page, OWUI_LOGS/OWUI_LOGS_NET invisibles dans les réglages
Open WebUI. Contrôle visuel des écrans après installation.

## 2026-11-11 — v0.0.70 : P118 — colonnes égales et espacement des cartes

Retours de mise en page : les deux colonnes de la carte Journalisation
(« Logs fichier » / « Logs réseau ») doivent être de la même taille — la
grille CSS (`1fr | filet | 1fr`) garantit l'égalité stricte (le flex laissait
les contenus déformer les largeurs). Un espace plus marqué sépare chaque
carte de ce qui la suit (marge basse 28 px). `versionName` 0.0.70.

## 2026-11-11 — v0.0.70 PUBLIÉE : colonnes égales, espacement des cartes

Run 43040424158 **success** sur le tag `v0.0.70` — chaîne gardée : verifier_tag ✓
+ check_apk ✓. Assets `OpenWebUI_Android-0.0.70-{debug,release}.apk`.
Attendu : deux colonnes de même largeur dans la carte Journalisation, espace
marqué sous chaque carte. Contrôle visuel des écrans après installation.

## 2026-11-11 — v0.0.71 : P119 — tiroir ☰ mobile, onglets, corrections de rendu

Contrôle visuel complet des 5 écrans /fm (sonde Playwright, viewport 412×915,
harnais 8090) — retours utilisateur : « le rendu n'est pas top sur un tel,
il faudrait comme Open WebUI pouvoir collapse le sidebar plutôt que de le
remonter au dessus ».

Corrections appliquées :

1. **Sidebar en tiroir mobile (P119)** : sous 820 px, la barre latérale n'est
   plus empilée au-dessus du contenu — elle devient un panneau hors-canvas
   (250 px, glissement 0,22 s) piloté par un bouton ☰ fixe en haut à gauche,
   avec voile d'assombrissement (rgba(0,0,0,.45)) et fermeture au clic.
   Vérifié par sonde : tiroir fermé x=-255 → ouvert x=0 → fermé au voile.
2. **Onglets sur une ligne** : la règle mobile `.tabs` était écrasée par la
   règle de base placée plus tard dans `_FM_STYLE` (cascade) — déplacée après ;
   auto-centrage de l'onglet ACTIF au chargement (sinon « Journaux » restait
   hors écran quand on était justement sur cette page).
3. **Marqueur orphelin `@@OWUI_LOGS@@`** : P117 avait retiré la clé du
   dictionnaire des champs mais pas le placeholder du template → le texte
   `@@OWUI_LOGS@@` s'affichait dans « Sécurité & préférences ». Supprimé
   (audit : seul placeholder orphelin du template).
4. **Cases à cocher réalignées** : `.card label` (text-transform, display
   block) et `.card input` (width 100 %) écrasaient `.chk` → case sur sa
   propre ligne, décalée du libellé sur l'écran SearXNG. Exclues via
   `.card label.chk` / `.card .chk input`.

Bugs de fabrication de la passe (corrigés dans la foulée) : variable `o`
locale à `fmSide` puis `ov` toujours hors portée → l'écouteur du voile n'était
jamais attaché (« ov is not defined ») ; variable top-level `sv` dédiée.
Vérifications : 4 pages /fm en 200, tiroir/onglets/marqueur validés par
sonde, `check_patches.py` vert, `py_compile` OK. Harnais 8090 complété
(stubs `searxng_settings_load/save` — le 500 observé venait du harnais, pas
de l'appli). `versionName` 0.0.71.

## 2026-11-11 — v0.0.71 PUBLIÉE : tiroir ☰ mobile, onglets, corrections de rendu

Run 43086150047 **success** sur le tag `v0.0.71` — chaîne gardée : verifier_tag ✓
+ check_apk ✓. Assets `OpenWebUI_Android-0.0.71-{debug,release}.apk`.
Attendu sur l'appareil : ☰ qui ouvre/ferme la sidebar en tiroir (voile,
fermeture au clic), onglets sur une ligne avec onglet actif centré, plus de
`@@OWUI_LOGS@@` dans les réglages Open WebUI, cases à cocher SearXNG
alignées. Contrôle visuel hôte fait (5 écrans, harnais 8090, arrêté après
test — conforme à la règle AGENTS.md).

## 2026-11-11 — v0.0.72 : P120 — sidebar et pages /fm alignées sur Open WebUI

Demande : « je voudrais le même visuel et la même façon de se replier ou de
se déplier, la même façon pour l'interaction, seul le contenu change » +
« profite en pour avoir un rendu cohérent avec Open WebUI sur le reste des
pages /fm ».

Relevé dans le frontend compilé (`src-assets/frontend/_app/immutable/`) :

1. **Mécanique sidebar** : largeur `--sidebar-width` défaut **245 px**,
   bornes **220/480** (`ee`/`at`), poignée `#sidebar-resizer`
   (`cursor-col-resize`, `touch-action:none`, pointer capture, flèches
   ←/→ ±10 px), persistance `localStorage.sidebarWidth` posée sur
   `document.documentElement` ; état visible persisté `localStorage.sidebar`
   (mobile fermé par défaut) ; bouton `#sidebar-toggle-button`
   (`rounded-lg`, `hover:bg-gray-100 dark:hover:bg-gray-850`, icône `size-4`,
   aria-label « Open/Close Sidebar ») ; items `rounded-xl px-2 py-1.5` avec
   sélection `bg-black/[0.035] dark:bg-white/[0.045]` ; bordure
   `border-e gray-50 / gray-850/30`.
2. **Thème** : corps light `#000/#fff`, dark `#eee/#171717` (le nôtre était
   déjà aligné) ; palette gray oklch neutre convertie en hexa
   (50 `#fafafa` … 900 `#171717`) ; rayons `lg .5rem · xl .75rem · 2xl 1rem` ;
   placeholder `#b4b4b4`.

Implémentation (P120) :

- sidebar : `width: var(--sidebar-width)` (220–480), head avec bouton de repli
  (SVG panneau), poignée `#sidebar-resizer` (`role="separator"`, `tabindex=0`),
  items en flex `rounded-xl` ;
- état unifié `body.sidehide` : desktop ouvert par défaut, mobile **fermé**,
  mémorisé (`localStorage.sidebar`) ; le ☰ s'affiche sur mobile **et** en
  desktop replié ; le voile ne sert qu'au tiroir mobile ;
- persistance : `localStorage.sidebarWidth` à chaque fin de drag et au clavier,
  relue au chargement ;
- harmonisation des pages : rayons OWUI sur boutons, cartes, champs de saisie
  et recherche, placeholder `#b4b4b4`, palette gray (fond sidebar `#fafafa`,
  bordures `#e7e7e7`).

Contrôle (sonde Playwright, harnais 8090) — tout est vert :

| Test | Résultat |
|---|---|
| Desktop défaut | visible, 245 px, ☰ masqué |
| Repli / réouverture | `sidehide` posé/enlevé, ☰ visible au repli |
| Persistance repli | conservé après rechargement |
| Drag poignée | 245 → 345 px, `sidebarWidth=345` persisté |
| Flèche → | 345 → 355 px |
| Mobile défaut | caché, ☰ visible ; ouverture tiroir + voile ; fermeture au voile |
| Mesures pixels | sidebar `#fafafa` sur 245 px, bordure `#e7e7e7` (gray-200) |

`versionName` 0.0.72.

## 2026-11-11 — v0.0.72 PUBLIÉE : sidebar et pages /fm alignées sur Open WebUI

Run 43116659902 **success** sur le tag `v0.0.72` — chaîne gardée : verifier_tag ✓
+ check_apk ✓. Assets `OpenWebUI_Android-0.0.72-{debug,release}.apk`.

Vérification mobile demandée (sonde 412×915, 5 écrans) : **0 px de
débordement horizontal** partout, tiroir ☰ fermé par défaut sur chaque écran,
tiroir ouvert conforme (fond `#fafafa`, bordure `#e7e7e7`, voile assombrissant),
onglets sur une ligne avec actif auto-centré, thème sombre `#171717` mesuré.
Contrôle desktop (1280×900) : sidebar inline 245 px, ☰ masqué, toggle en tête,
mesures pixels conformes. Fonctionnel : repli/réouverture, persistance de
l'état et de la largeur (drag 245→345 persisté, flèche → ±10 px).

## 2026-11-11 — v0.0.73 : P121 — rétraction en icônes seules + icônes Open WebUI

Demandes : « il manque la rétraction avec juste les icônes, le gros bouton est
moche et inutile si il y a la rétraction avec juste les icônes » +
« reprend la façon de faire les icônes ou reprends même ceux de OpenWebUI ».

Relevé dans le sprite du frontend Open WebUI
(`src-assets/frontend/_app/immutable/chunks/wN8N8j40.js`, 127 icônes) :

1. **Icônes** : extraction programmatique des 13 SVG utilisés par la sidebar
   (`folder, list, pdf-logo, image, code, markdown-logo, package, settings,
   brain, search, tools, page-text, sidebar-expand`) — même `viewBox 0 0 24 24`,
   `stroke="currentColor"` `stroke-width 1.5`, `stroke-linecap/linejoin round`
   que le composant `Icon` d'Open WebUI ; les émojis des entrées sont retirés.
2. **Structure** : chaque lien/groupe devient
   `<span class="si">icône</span><span class="sl">libellé</span>` avec
   `title="<libellé>"` (infobulle native en mode icônes).

Implémentation (P121) :

- **Suppression du ☰** : règles CSS `.sidebtn`, bouton HTML `#sidebtn` et
  écouteur JS supprimés ; `body.sidehide` disparaît au profit de
  `body.sideicons` ;
- **Mode icônes seules** (`body.sideicons`) : `width/min-width/max-width`
  56 px, `.sl` masqué, liens et titres centrés, `#sidebar-resizer` masqué,
  groupes `details` forcés ouverts (clic sur `<summary>` neutralisé pour ne
  pas replier l'arbre), bouton de repli qui met à jour son `title` ;
- **Bouton de repli** : icône `sidebar-expand` d'Open WebUI (l'ancien SVG
  maison rect+barre est remplacé) ; il bascule `icons ↔ full` et persiste
  `localStorage.sidebar` ;
- **Mobile** : la sidebar n'est plus un tiroir caché — c'est une **colonne
  d'icônes permanente de 56 px** (contenu décalé `padding-left: 68px`,
  `.ver` décalé à 66 px) ; le mode plein s'ouvre en **overlay avec voile**
  (`body:not(.sideicons) .side` + `.sideov.on`) et un clic sur le voile
  revient aux icônes ; mobile démarre toujours en icônes ;
- **Padding haut mobile** : maintenu à 58 px (le FAB P40 reste fixé en haut
  à droite — un passage à 14 px a fait chevaucher le FAB, corrigé après
  mesure `tab_y=62 > fab_bottom=52`) ;
- **Transition** : `width/min/max .18s ease` (desktop) et `.2s ease` (mobile)
  pour un repli progressif.

Contrôle (sonde Playwright `ui_probe6.py`, harnais 8090) — tout est vert :

| Test | Résultat |
|---|---|
| Desktop défaut | déployé 245 px, titre « Réduire en icônes », 12 icônes |
| Clic repli | 56 px, `.sl` masqué, resizer masqué, groupes ouverts, titre basculé |
| Infobulle | `title="Journaux"` présente |
| Persistance | icônes conservé après rechargement ; retour plein 245 px conservé |
| ☰ | `#sidebtn` absent (0 occurrence) |
| Mobile défaut | colonne 56 px, 0 px de débordement |
| Mobile plein | overlay 245 px + voile `sideov on` |
| Voile | retour aux icônes (56 px) |
| Débordement | 0 px sur les 5 écrans |
| Chevauchement FAB/onglets | False (`tab_y=62`, `fab_bottom=52`) |

`versionName` 0.0.73.

## 2026-11-12 — v0.0.73 PUBLIÉE : rétraction en icônes seules + icônes Open WebUI

Run 43123876070 **success** sur le tag `v0.0.73` — chaîne gardée : verifier_tag ✓
+ check_apk ✓. Assets `OpenWebUI_Android-0.0.73-{debug,release}.apk`.

Revalidations supplémentaires : thème sombre en mode icônes (desktop 56 px +
fond `#171717` mesuré, mobile colonne 56 px sans débordement), chevauchement
FAB/onglets corrigé (`tab_y=62 > fab_bottom=52`), harnais 8090 arrêté après
les tests (0 processus survivant).

## 2026-11-12 — v0.0.74 : P122 — pied de page dégagé de la colonne en mode icônes

Demande : « openwebui android version depasse dans fm quand la side barre est
retracte ».

Diagnostic : le pied de page `.ver` (« OpenWebUI Android 0.0.73 ») est
`position:fixed; left:10px` — en mode icônes la colonne ne fait que 56 px, le
texte (~130 px) débordait donc sur le contenu principal (et chevauchait la
bordure de la colonne).

Correctif (P122) :

- `body.sideicons .ver { left: 66px; }` — le texte démarre à droite de la
  colonne (56 + 10 de marge) ;
- transition `left .18s ease` sur `.ver`, alignée sur celle de la sidebar
  (dépliement sans saut) ;
- mobile : inchangé (règle média déjà à `66px`, affichage masqué ≤480 px).

Contrôle (sonde, harnais 8090) :

| État | `.ver` x | Colonne droite | Conforme |
|---|---|---|---|
| Plein (245 px) | 10 | 245 | ✓ (sur la sidebar, comme depuis P120) |
| Icônes (56 px) | **66** | 56 | ✓ hors colonne |
| Mobile 412 px | masqué (`display:none`) | 56 | ✓ |

`versionName` 0.0.74.

## 2026-11-12 — v0.0.74 PUBLIÉE : pied de page dégagé en mode icônes

Run 43140337496 (tag `v0.0.74`) **success** — assets
`OpenWebUI_Android-0.0.74-{debug,release}.apk`, release publiée à
02:21:35Z. Note : deux échecs transitoires de `gh` en cours de surveillance
(EOF sur l'API GitHub) — le build n'a pas été en cause, relancé à l'identique
avec succès.

## 2026-11-12 — v0.0.75 : P123 — icône « fichier + roue crante » du bouton flottant /fm

Demande : remplacer l'icône trombone 📎 du bouton flottant vers `/fm` par
« une icône trombone avec roue crante ou quelque chose de similaire afin de
montrer que c'est fichier et paramètre de l'application ».

Diagnostic :

- cible unique : `&#128206;` (📎) = `#fab-spa`, injecté par
  `patch_files_button()` (`prepare_src.py`), un seul `</body>` et un seul
  `fab-spa` dans `index.html` ;
- le sprite d'Open WebUI (`immutable/chunks/wN8N8j40.js`) ne contient **ni
  `paperclip` ni `gear`** (123 noms relevés) : l'icône est **dessinée**, au
  trait d'Open WebUI (viewBox 24, `stroke-width` 1.5, `currentColor`).

Correctif (P123) :

- constante `_FAB_SVG` dans `prepare_src.py` : document à pli + 3 lignes,
  engrenage **8 dents** en bas à droite (rayons 4.9 / 3.55, trou 1.65),
  disque de fond `#3b82f6` (couleur du FAB) pour détourer la roue du
  document — 22 px dans le disque de 42 px ;
- `title` du bouton : « Fichiers et paramètres de l'application — glisser
  pour déplacer » (l'ancien parlait seulement des PDF/téléversements) ;
- `check_patches.py` (contrôle renforcé, justifié : nouveau patch, un
  retour d'émoji ou un `index.html` régénéré sans patch ne doit plus passer) :
  `#fab-spa` exigé, `&#128206;`/📎 interdit, `<svg stroke-width="1.5">` exigé.

Validation :

- constante Python **identique octet à octet** au SVG de l'prototype validé
  visuellement (comparaison avec `/tmp/opencode/fab_iconB.py`) ;
- `prepare_src.py` régénéré (117 opérations, 2 min 17) — régénération
  déterministe : mêmes 3 fichiers `src-assets` modifiés qu'avant (P106/P70)
  + l'icône ;
- `py_compile` + `check_patches.py` : **OK** ;
- sonde Playwright (serveur statique 8090, arrêté après test, 0 survivant) :
  FAB 42×42, SVG 22×22 **contenu dans le disque**, `title`/`href=/fm`
  conformes, aucun émoji, aucun débordement horizontal — thème clair **et**
  sombre (captures `fab_light.png` / `fab_dark.png`, lisibilité confirmée à
  taille réelle).

`versionName` 0.0.75.

## 2026-11-12 — v0.0.75 PUBLIÉE : icône « fichier + roue crante » du FAB /fm

Run 43187163673 (tag `v0.0.75`) **success** — build 5 min 04 s, assets
`OpenWebUI_Android-0.0.75-{debug,release}.apk`, release publiée à
09:01:38Z.

Note d'incident maîtrisé : le `git push --tags` a aussi publié une ancienne
balise locale `v0.0.50` jamais poussée, ce qui a déclenché une build non
voulue (run 43187165219) — **annulée** (`gh run cancel`) et balise retirée du
remote (`git push --delete refs/tags/v0.0.50`) avant toute release ; la liste
des releases est inchangée (v0.0.50 absente). À l'avenir : pousser le tag
nommé (`git push origin v0.0.75`), pas `--tags`.

## 2026-11-12 — v0.0.76 : sidebar responsive (P124) + icônes/style OWUI des pages /fm (P125)

P124 — responsive de la sidebar /fm (règle utilisateur demandée) :

- téléphone **≤600 px** : plus de colonne permanente — la sidebar devient un
  tiroir hors-canvas (`transform: translateX(-100%)` + `visibility: hidden`),
  ouvert par le nouveau bouton `#side-open` (icône `sidebar-expand` du sprite
  OWUI, haut à gauche, `display:flex` uniquement ≤600 px) ;
- le voile `.sideov.on` pilote l'affichage par le sélecteur
  `.sideov.on ~ .wrap .side` (**`~` et pas `+`** : le bouton `#side-open` est
  inséré entre `.sideov` et `.wrap` dans le gabarit) ; fermeture au clic
  sur le voile (hors tiroir) ;
- toggle de repli et poignée de redimensionnement masqués ≤600 px
  (inutiles dans un tiroir) ; `.main{padding:58px 12px 12px 12px}`,
  `.ver{left:10px}` ;
- tablette **601–820 px** inchangée (colonne d'icônes 56 px, padding 68 px,
  pas de `#side-open`) ; desktop **≥821 px** inchangé (245 px + resizer).

P125 — icônes et style des pages /fm calqués sur Open WebUI (seul le
contenu change) :

- extraction des icônes du sprite OWUI (`wN8N8j40.js` : `e.name==="…"` →
  variable → `FN=k('…')`), **17 icônes** extraites puis validées visuellement
  (planche `/tmp/opencode/icons_preview.png`), 16 ajoutées à `_FM_ICONS`
  (29 en tout, `code` déjà présent) ;
- table `_FM_EMO_ICO` : les **23 entités d'émojis** des pages (`&#9654;` ▶,
  `&#9208;` ⏹, `&#8635;` ↺, `&#9888;` ⚠, `&#9989;` ✅, `&#9881;` ⚙, 🔌 🔍 💾
  🤖 📑 🔒 🔧 📝 📷 📄 🌐 📥 🗅 🛠 📦 💬) → icônes (`play, stop, refresh,
  info, check, settings, plug, search, save, spark, database-script, lock,
  code, page-text, clock, list, globe, download, trash, tools, package,
  chat-bubble`) ; le sélecteur de variation `&#65039;` (toujours accolé à
  🛠/⚠) est **supprimé** ;
- décorateur `_fm_deco()` : appliqué **une fois sur le document complet**
  retourné par `_fm_page` (contrôle préalable : 43 entités, **0 dans un
  attribut**, 0 dans le CSS, 0 dans le JS → le remplacement ne peut pas
  casser le gabarit) ; substitution `@@VAR@@` faite AVANT `_fm_page`, donc
  sans conflit avec les placeholders `@@ICO:` ;
- **3 exceptions** ciblées par placeholder `@@ICO:nom@@` : Fichiers journaux
  → `folder`, Index des documents → `grid`, Nettoyer l'index → `refresh`
  (la table générique donnerait `list`/`trash`/`trash`) ;
- **style OWUI** relevé dans `0.D7xLj0AB.css` et appliqué à `_FM_STYLE` :
  boutons `h-7 px-2.5 text-xs font-normal rounded-lg` → 28 px, padding
  0 10 px, 12 px, graisse 400, radius .5rem, `inline-flex` (icône + libellé
  alignés, `vertical-align: middle` pour les boutons dans le texte) ;
  primaire `bg-gray-900`/dark `gray-100` (déjà en place), secondaire
  **blanc + bordure** (`.ghost`, `.btn2` → `--btn2:#ffffff`/dark `#1f1f1f`
  + `border:1px solid var(--border)`) ; champs `px-2 py-1.5 text-[0.6875rem]`
  → 6×8 px, 11 px, `outline:none`, focus **blue-400** (`#60a5fa`) ;
  `textarea` idem ; cases à cocher = **règle OWUI reprise telle quelle**
  (14 px, `appearance:none`, radius .25rem, bleu 600 cochée, coche SVG
  blanche en `:after`, placée APRÈS `.card input` pour lui primer dessus) ;
  `html{word-break:break-word}` ; palier **≤480 px** : boutons à 34 px
  de haut (cible tactile).

`check_patches.py` (contrôle **ajouté**, aucun contrôle affaibli —
justification : nouveau patch, un module régénéré sans décorateur ou un
CSS écrasé ne doit plus passer) : nouvelle fonction `check_p125_fm()` —
`_fm_deco` défini et appelé dans `_fm_page` (prepare_src ET module généré),
table `_FM_EMO_ICO` complète (23 entrées), **toutes les entités du module
couvertes** par le décorateur, placeholders `@@ICO:folder/grid/refresh`
présents et sans orphelin, motifs de style OWUI exigés (coche checkbox,
word-break, 28 px, 11 px, secondaire bordé). Contrôle **réactif vérifié** :
8 sabotages détectés (décorateur retiré, clé de couverture retirée, entité
neuve non couverte, CSS 28 px cassé, checkbox cassée, word-break disparu,
secondaire débordé, placeholder orphelin) + arbre réel vert.

Validation :

- `py_compile` prepare_src + android_fm : **OK** ; `check_patches.py` : **OK** ;
- sonde `p125_probe.py` (harnais 8090, **arrêté après test, 0 survivant**) :
  4 pages (accueil, réglages, journaux, maintenance) × 2 thèmes — **0 entité
  d'icône dans le DOM**, **0 émoji littéral**, icônes SVG rendues dans les
  titres et boutons, boutons 28 px/8 px radius/12 px/400, champs 11 px sans
  contour + focus blue-400, cases 14 px avec coche, `html word-break:
  break-word`, secondaire blanc bordé, aucun débordement horizontal ;
- sonde `p124_probe.py` rejouée (non-régression) : tél fermé `side_x=-56`
  hidden / `#side-open:flex` / pad 12 px ; tél ouvert `x=0 w=245` visible +
  voile + libellés ; refermé ; tablette colonne 56 px pad 68 px sans
  `#side-open` ; desktop 245 px + resizer pad 20 px — **tous verts** ;
- validation visuelle des captures (`p125_*.png`) : rendu conforme OWUI
  en clair **et** sombre (labels des cartes, boutons, champs, icônes).

`versionName` 0.0.76.

## 2026-11-12 — v0.0.76 PUBLIÉE : sidebar responsive + icônes/style OWUI

Run 43303454033 (tag `v0.0.76`) **success** — release publiée à 20:49:25Z
avec les 2 APK (`OpenWebUI_Android-0.0.76-{debug,release}.apk`). Push du
tag nommé (`git push origin master v0.0.76`), aucun `--tags`.

Captures de validation rangées dans le projet sous `home/tmp/`
(16 fichiers : `p125_*` 4 pages × 2 thèmes + secondaire, `p124_*` responsive
+ planche, `icons_preview` — données de test neutres, aucun secret).

Correction (2026-11-12) : les captures de validation ne sont pas dans le
projet — elles sont rangées sous `~/tmp` (`/data/data/com.termux/files/home/tmp`),
emplacement voulu par l'utilisateur (demande explicite, en dehors de la règle
d'isolation). Le sous-dossier `home/tmp/` provisoirement créé dans le projet
a été retiré.

## 2026-11-15 — v0.0.77 : toggles des outils web/code respectés (P126)

**Signalement utilisateur** : les outils web et code restaient *visibles et
actifs même avec le toggle désactivé* (icônes du composeur). Demande : vérifier
un éventuel effet de bord de nos patchs (« normalement ça fonctionne bien sans
tes patch »).

**Audit (code généré vs sources vierges du wheel amont)** :

- `utils/tools.py` : 2 écarts de gate — **P18** (outils web exposés sans
  condition : `is_builtin_tool_enabled`, `get_model_capability` ET
  `features.get('web_search')` supprimés) et **P28** (`compile_typst` ajouté
  en fin de fonction, hors de tout gate) ;
- `utils/middleware.py` : **0 diff** (gates `execute_code` et DETECT_CODE
  conformes à l'amont) ; `routers/utils.py` : 3 lignes (P14, import black
  lazy — sans rapport) ; `tools/builtin.py` : nos patchs documentés
  (fetch_url, journaux, fichiers) — aucun gate touché ;
- frontend : 5 fichiers modifiés, tous documentés (worker pyodide P38/P103/
  P49a, `nodes/0` P106/P107, `nodes/2` P10, `index.html` P123) — aucun lien
  avec la visibilité des toggles.

**Sonde unitaire `p126_gate_test.py`** (appel réel de `get_builtin_tools`
sur la base SQLite de test, stubs ciblés pour les wheels natifs Android non
chargeables sur l'hôte) : les fuites sont confirmées **avant** correction —
`search_web`/`fetch_url` exposés avec l'icône du composeur désactivée, avec
`builtinTools.web_search` désactivé, avec `capabilities.web_search`
désactivé, et « tout OFF » ; `compile_typst` exposé dans TOUS les cas ;
`execute_code` correctement filtré partout (aucune fuite).

**Décisions utilisateur (2026-11-15)** : le toggle concerné est celui des
**icônes du composeur** ; `compile_typst` doit suivre le toggle **« Outils »**
du modèle.

**Correctif P126** :

- **P18 révoqué** : le patch est retiré (`prepare_src.py`), le gate amont des
  outils web est rétabli tel quel — il respecte donc `features.get('web_search')`
  (icône du composeur), `builtinTools.web_search`, `capabilities.web_search`,
  `web.search.enable` et la permission utilisateur. Pour activer la recherche
  web : actionner l'icône (globe) du composeur ;
- **P28 amendé** : `compile_typst` est conditionné par
  `if ENABLE_TOOLS and is_builtin_tool_enabled('tools'):` (toggle « Outils »
  du modèle) et reste indépendant de la permission de CRÉATION d'outils
  (`workspace.tools`) qui le faisait disparaître à tort (v0.0.11).

**`check_patches.py` (contrôles modifiés, JUSTIFICATION — règle du
2026-11-08)** : le contrôle P28 évolue parce que le patch P28 évolue — il
exige désormais le gate « Outils » (avant : il exigeait l'enregistrement
*inconditionnel*). Le contrôle se **RENFORCE** : (1) `compile_typst` sans gate
= erreur, (2) gate autre que `is_builtin_tool_enabled('tools')` = erreur,
(3) le retour du gate forcé P18 = erreur, (4) l'absence du gate amont
(`is_builtin_tool_enabled('web_search')`, `features.get('web_search')`) =
erreur. L'entrée CHECKS « P18 gate outils web » (motif du gate forcé) est
retirée et couverte par ces contrôles de révocation.

**Validation** :

- sonde `p126_gate_test.py` **verte après correction** : icônes du composeur
  OFF → ni web ni `execute_code` (`compile_typst` reste, gate « Outils » actif
  par défaut — choix utilisateur) ; toggle « Outils » OFF → `compile_typst`
  caché ; toggles modèle web/code OFF (builtinTools et capabilities) → ni web
  ni `execute_code` ; tout OFF → aucun des 4 ; tout ON (référence) → les
  4 outils présents ;
- `py_compile` prepare_src + check_patches + android_fm : OK ;
- `check_patches.py` : OK (116 opérations de préparation, le patch P18 n'est
  plus appliqué) ;
- non-régression `/fm` : sondes P124 + P125 rejouées sur le harnais 8090
  (arrêté après test, 0 survivant).

`versionName` 0.0.77.

## 2026-11-15 — v0.0.77 PUBLIÉE : toggles des outils web/code respectés

Run 43772199254 (tag `v0.0.77`) **success** — release publiée à 23:02:12Z
avec les 2 APK (`OpenWebUI_Android-0.0.77-{debug,release}.apk`). Push du
tag nommé (`git push origin master v0.0.77`), aucun `--tags`.

## 2026-11-17 — Compte rendu audio (`docs/audio.typ` + PDF)

Document demandé : état de la chaîne audio (dictée, transcription de
fichiers, génération de parole TTS, appels vocaux) *avec patch* et
*sans patch*. Faits relevés dans le code généré, `PATCHES.md`, `journal.md`,
et vérifiés par test direct de `transcribe()` (harnais hôte, stubs ciblés).

Nouveau fait vérifié (limite) : avec le moteur STT par défaut `web`, la
transcription d'un fichier audio joint renvoie HTTP 500 (`TypeError`) —
`transcription_handler()` n'a pas de branche `web` (mode dictée client).
Le correctif P127 est proposé au document (message d'erreur clair).
Validé aussi : les petits fichiers (≤ 20 Mo) sont transcrits sans pydub
(la vérification de format échoue silencieusement, `split_audio` rend le
fichier tel quel).

Livrable : `docs/audio.typ` + `docs/audio.pdf` (schéma merman du pipeline,
tableau récapitulatif avec/sans patch, points de vigilance, références
code). Aucun changement de code — aucun bump de version.

## 2026-11-17 — P127-P130 : audio local complet (dictée, voix, fichiers)

Demande : implémenter P127, P128, P129, P130, *valider chaque élément*,
l'audio devant être complètement fonctionnel en local via les API Android et
les méthodes citées. **Aucun commit/push GitHub** — l'utilisateur teste l'APK
avant publication.

**P127 — messages clairs (transcription de fichiers)** : `transcription_handler`
reçoit les branches `web` (« la dictée native ne transcrit pas les fichiers
joints : configurez un moteur STT distant ») et « moteur inconnu » → HTTP 400
au lieu d'une `TypeError` (HTTP 500) quand la fonction retournait `None` ;
garde-fou équivalent dans `_transcribe_whisper` (STT local absent → 503).

**P128 — synthèse vocale locale (API Android)** : pont `AndroidTTS.java`
(`TextToSpeech` natif : `speak`/`stop`/`voicesJson`, événements
`window.__androidTtsEvent`) + shim `app/src/main/assets/tts_polyfill.js`
remplaçant `window.speechSynthesis`/`SpeechSynthesisUtterance`, injecté par
`MainActivity.onPageFinished`. Piège découvert par le test : dans Chromium,
`window.speechSynthesis` est un attribut EN LECTURE SEULE — l'affectation
échoue silencieusement et l'API native (muette dans la WebView) restait en
place ; corrigé par `Object.defineProperty`. Résultat : lecture à voix haute
et voix des appels produites par la voix du téléphone (hors-ligne, sans clé).

**P129 — fin de pydub** (audioop retiré de Python 3.13) : passage en l'état
sans `mediainfo`, compression/conversion locales supprimées, repli octets
d'origine pour le transcodage TTS ; `split_audio` en pur Python : WAV (module
`wave`) et MP3 (frontières de trames MPEG, parseur maison).

**P130 — découpage par les API Android** : `AndroidAudio.java`
(MediaExtractor/MediaMuxer sans transcodage, sorties m4a/webm) pour les
fichiers > 20 Mo hors wav/mp3 ; pont Java→Python `register_audio_split`
(fonction à un argument JSON, `audio_bridge.py`) enregistré par `MainActivity`
au démarrage ; repli : message clair hors appareil.

**Validation (chaque élément)** :

- P127 + P129 + P130-Python : sonde hôte `p127_p129_test.py` **verte** —
  branches `web`/inconnu → 400 avec les bons messages, whisper local → 503 ;
  WAV découpé en morceaux ≤ plafond avec **reconstitution bit-à-bit** du
  contenu d'origine, MP3 découpé sur frontières de trames (entêtes vérifiés),
  petit fichier rendu tel quel, format inconnu sans pont → message clair,
  pont Android simulé → délégation avec les bons arguments ;
- P128 : sonde Playwright `p128_tts_test.py` **verte** (9 scénarios sur le
  JS réellement livré) — délégation speak (id/texte/débit/voix), événements
  start/end/error, file d'attente (ordre strict), cancel → stop + état remis
  à zéro, pause/resume, inertie du shim sans le pont ;
- `check_patches.py` : contrôle `check_audio_locale()` **ajouté** (renforce :
  exige les messages P127, l'absence de pydub dans la chaîne de transcription,
  les splitteurs wave/mp3, le pont P130 Python+Java, le shim P128 et son
  câblage MainActivity) — contrôles verts ;
- Java : compilation validée par le build Gradle (`scripts/build.sh`) ;
  test appareil requis pour le comportement runtime des ponts.

`versionName` 0.0.78 (arbre local). APK de test : `dist/OpenWebUI_Android-0.0.78-debug.apk`.

## 2026-11-17 — Minimalisation de l'empreinte amont + transcode fonctionnel

Demande : « je veux minimiser les modifications du code d'origine ».

**Révision de l'empreinte** (routers/audio/__init__.py) : 4 remplacements
devenus inutiles sont **retirés** — le code amont gère déjà pydub absent par
ses propres try/except (`is_audio_conversion_required` → False, morte
chemin `convert_audio_to_mp3`, `compress_audio` avalée par son try/except).
`transcription_handler` n'est plus réécrit : ses branches `web`/« inconnu »
sont des **ajouts purs** après la chaîne amont intacte. Le découpage ne
remplace plus le corps de `split_audio` : **une ligne d'appel** changée dans
`transcribe()` (`_split_audio_local`) + fonctions ajoutées en fin de module.

**Bilan final de l'empreinte amont** : 19 lignes touchées au total, dont
6 antérieures (P5/P7a-c : try/except d'import) et 13 nouvelles (12 pour
`transcode_audio_to_mp3` + 1 ligne d'appel de découpage) ; le reste du diff
sont des **ajouts** (239 lignes) sans rien modifier. Les volets Java/JS
(P128/P130) : **zéro** modification amont (fichiers neufs + accroches dans
nos fichiers).

**transcode_audio_to_mp3 rendu fonctionnel** (question utilisateur) : le vrai
encodage MP3 est impossible ici (pydub exporte via ffmpeg absent ; MediaCodec
Android ne fournit aucun encodeur MP3 ; encodeur pur Python inutilisable).
Mais inutile : le PCM brut est **enveloppé en WAV** (module `wave`, pur
Python) et les autres formats sont servis tels quels — testé : Chromium joue
un WAV même servi en `audio/mpeg` (`canplay`, durée correcte), et les API STT
acceptent wav/m4a/flac/webm/ogg directement.

**Validations rejouées après révision** : sonde hôte P127/P129/P130 verte
(transcode PCM → WAV vérifié trames/taux/canaux), shim P128 (9 scénarios),
`check_patches.py` avec nouveau contrôle de **minimalité** (les fonctions
amont doivent rester intactes — toute altération future échoue le contrôle).
Build APK relancé.

## 2026-11-17 — P131 : les moteurs locaux morts sortent de l'UI

Demande : « enlever les choix transformers et whisper dans l'UI, est-ce que
c'est simple ? » — oui : l'amont désactive déjà ces options en mode « slim »
quand les moteurs lourds manquent (`features.slim` sur les `<option>`).
P131 transforme cette désactivation en masquage définitif
(`disabled` + `hidden`) par deux micro-remplacements dans le chunk des
réglages audio (`nodes/2.DwSK4ZlF.js`) — structure Svelte amont intacte.

Résultat dans *Réglages → Audio* : les listes ne proposent plus
« Transformers (Local) » (TTS) ni « Whisper (Local) » (STT) ; restent
« Web API » (= voix Android system depuis P128 pour le TTS, dictée native
pour le STT) et les moteurs distants. Une valeur déjà enregistrée reste
affichée (pas de casse de configuration).

Validé : marqueurs présents dans le chunk régénéré, `check_patches` (contrôle
P131), test Playwright du comportement `hidden` sur `<option>` (disparaît de
la liste déroulante, sélection existante conservée).

## 2026-11-17 — P132 : les options RAG mortes sortent de l'UI + release v0.0.78

**P132** (demande « pour le RAG y a-t-il des options non utilisables ? » →
oui, 3 ; puis « oui » pour les masquer) : même technique que P131 (mécanisme
« slim » de l'amont, `disabled`+`hidden` sur les `<option>`) —
« Default (SentenceTransformers) » pour l'embedding et pour le rerank, et
« Token (Transformers) » pour le découpage. Rationale : torch/
sentence-transformers ne sont pas embarqués (embeddings distants par
conception, `RAG_EMBEDDING_ENGINE=openai` forcé par android_main) ; restent
Ollama/OpenAI/Azure, le rerank « External » ou le scoring cosinus, les
découpages Character/Tiktoken (shim embarqué), et les extracteurs embarqués
(pypdf/python-docx/docx2txt/bs4).

Validé : 5 marqueurs P131/P132 présents dans le chunk régénéré,
`check_patches` (contrôles P132), tests P127/P129/P130 et P128 rejoués verts,
doc Typst `maintenance.typ` complétée (P127→P132) et recompilée sans
avertissement.

**Release v0.0.78 lancée sur demande** : vérification complète → commit →
push → tag `v0.0.78` → build CI GitHub (le push de tag déclenche le workflow).

## 2026-11-17 — v0.0.78 PUBLIÉE : audio local + UI assainie (P127-P132)

Run 44186005320 (tag `v0.0.78`) **success** — release publiée à 22:07:22Z
avec les 2 APK (`OpenWebUI_Android-0.0.78-{debug,release}.apk`). Push du
tag nommé (`git push origin master v0.0.78`), aucun `--tags`.

**Purge des releases GitHub** (demande utilisateur) : les 52 releases
antérieures à `0.0.70` (`v0.0.7` → `v0.0.59`) ont été **supprimées avec
leurs APK** ; conservées : `v0.0.70` à `v0.0.78`. Les tags git, eux, sont
conservés (repères d'historique) — suppression possible sur demande.

## 2026-11-17 — P133 (dictée « client ») + P134 (mode vocal local)

**Retour utilisateur** : « Erreur de reconnaissance vocale : client » à l'appui
sur le micro, et « je n'ai pas le mode d'interaction vocale d'actif ».

**Diagnostic dictée (P133)** — la chaîne `AndroidSpeech` retombait sur
`default: "client"` pour tout code non mappé : `ERROR_CLIENT` (5, service qui
redémarre — fréquent au 1er appel ou à une relance immédiate),
`ERROR_TOO_MANY_REQUESTS` (10), `ERROR_SERVER_DISCONNECTED` (11),
`ERROR_LANGUAGE_NOT_SUPPORTED` (12) / `ERROR_LANGUAGE_UNAVAILABLE` (13).
De plus `buildIntent` imposait `Locale.getDefault().toString()` (« fr_FR »)
alors que les moteurs attendent un tag BCP-47 — source d'erreur côté client.
Corrections : relance espacée de 400 ms sur `ERROR_CLIENT` (2 tentatives),
nouveaux cas dans `mapError`, payload `{error, code}` (code Android brut),
libellé français affiché par le shim (le toast amont est
« Speech recognition error: {{error}} »), langue non forcée si le réglage est
vide. Constantes vérifiées dans `android-sdk/platforms/android-34/android.jar`
(parseur de pool de constantes — `javap` absent) : toutes existent en API 34.
Diagnostic TTS associé : `AndroidTTS` affiche un toast explicite quand
`TextToSpeech` échoue à l'init (aucun moteur TTS installé) — cas qui produisait
exactement le symptôme « pas de synthèse vocale » sans la moindre trace.

**Diagnostic mode vocal (P134)** — l'amont n'affiche le bouton « Voice mode »
que si `audio.realtime.enabled` **ou** `audio.stt.engine !== "web"`, puis
refuse l'ouverture de l'overlay avec « Call feature is not supported when using
Web STT engine » (2 autres occurrences) : notre build force `AUDIO_STT_ENGINE=web`
(dictée native) → le mode était inaccessible. La transcription de l'appel passe
par `rb()` → `/api/v1/audio/transcriptions`, qui renvoie 400 en moteur « web ».
Corrections (7 micro-remplacements dans `chunks/BeEbX_lw.js`) : les 3 refus
neutralisés, l'écoute locale ouverte/fermée par la détection de parole amont
(`__callDictation.start/hold`), transcription lue en local
(`__callDictation.text()` remplace `rb()`), et **vrai micro** via
`window.__realMic` → `__origGUM` (le shim de dictée substitue un flux silencieux
au `getUserMedia`, ce qui aurait cloué la détection de parole de l'appel).
Nouveau `app/src/main/assets/call_polyfill.js` (garde-fou 30 s : jamais
d'écoute en boucle qui finirait par transcrire la voix de l'assistant), injecté
par `MainActivity` — le lecteur d'assets est passé en cache générique
(`assetJs(nom)`).

**Validation** : `check_patches` vert (nouveau contrôle `check_mode_vocal` +
`check_js_syntax` étendu au chunk d'appel et aux polyfills d'assets —
justification : un chunk cassé affiche « 500 » au lancement et aucun contrôle
Python ne le voit) ; sondes rejouées vertes : `p127_p129_test`,
`p128_tts_test`, **`p133_speech_test`** (extraction + `node --check` du string
Java, libellés, `__origGUM`), **`p134_call_test`** (micro réel, résultats
finaux, relance, hold, transcription, garde-fou) ; 133 opérations de préparation.

**Publication** : commit → suppression de la release `v0.0.78` → tag `v0.0.78`
repris sur le nouveau commit → CI (régénération des APK) — sur demande.

## 2026-11-17 (suite) — v0.0.78 : reprise du tag et régénération (sur demande)

Demande explicite de l'utilisateur : « corrige, committe, reprends le tag avec
la 0.0.78 et efface la release 0.0.78, puis régénère ».

- **Doc Typst à jour** : `docs/maintenance.typ` (lignes P133 et P134 ajoutées au
  tableau des patchs, après P132) et `docs/audio.typ` (dictée : relance
  `ERROR_CLIENT`, codes mappés, libellés FR, langue non forcée ; nouvelle
  section « Mode d'interaction vocale — fonctionnel en STT local (P134) »
  distinguée des appels *temps réel* `audio.realtime` toujours désactivés ;
  tableau récap et références enrichis ; abstract porté à 0.0.78) — les deux
  PDF recompilés sans warning (0 tableau Markdown, 0 gras Markdown, 0 `*/`).
- **Vérifications** : `check_patches.py` vert, `verifier_tag.py`
  (tag v0.0.78 == versionName 0.0.78), secret-scan (IP/clés) propre.
- **Commit** `76f9e1d` « P133/P134 : dictée sans erreur « client » + mode vocal
  utilisable en STT local » (14 fichiers).
- **Release supprimée** : `gh release delete v0.0.78 --yes` (les 2 APK du run
  44186005320 sont retirés — ils portaient les versions antérieures à P133).
- **Tag repris** : `git tag -d v0.0.78` (était sur `f9afd99`) +
  `git push origin :refs/tags/v0.0.78` + `git tag v0.0.78 76f9e1d` +
  `git push origin master` puis `git push origin master v0.0.78`
  (jamais `git push --tags`) — le tag remote pointe désormais sur `76f9e1d`.
- **CI déclenchée** : run `44196145477` (Build APK, ref v0.0.78) — suivi en
  arrière-plan, verdict à consigner ci-dessous.

## 2026-11-17 (final) — v0.0.78 RÉGÉNÉRÉE

- Run CI `44196145477` (Build APK, ref `v0.0.78` → `76f9e1d`) : **success**
  (2026-11-17T23:05:03Z → 23:08:59Z, ~4 min).
- Release `v0.0.78` republiée avec les 2 APK **regénérés à partir de
  `76f9e1d`** (donc avec P133 et P134) :
  - `OpenWebUI_Android-0.0.78-debug.apk` (251 848 305 o)
  - `OpenWebUI_Android-0.0.78-release.apk` (247 324 000 o)
- Cycle complet conforme à la demande : correction → commit → effacement de
  l'ancienne release → reprise du tag `v0.0.78` (local + remote, jamais
  `git push --tags`) → régénération par la CI.
- Reste : test sur appareil (dictée, mode vocal, lecture à voix haute).

## 2026-11-18 — P135/P136 : verrou d'initialisation du synthétiseur (aucune génération audio)

Symptôme remonté : le mode d'interaction vocale capte et transcrit l'énoncé,
mais **aucun son n'est jamais émis** (ni dans l'appel, ni à la lecture d'un
message), sans erreur ni toast.

**Cause racine (P135, `app/src/main/java/.../AndroidTTS.java`)** : l'initialisation
du `TextToSpeech` n'était déclenchée que par `speak()`, alors que `speak()` n'est
atteint qu'après que `getVoices()` renvoie une liste non vide — or `voicesJson()`
renvoyait `"[]"` tant que le moteur n'avait pas été créé. La boucle d'attente
amont (100 ms) tournait donc *indéfiniment* : verrou silencieux, aucune voix,
aucun son. Correctifs : `voicesJson()` déclenche l'initialisation
(`ensureTts(() -> { })`), les demandes reçues pendant le démarrage sont mises en
file et purgées à la fin de l'init (`initDone`, distinct de `ready` — sinon un
`speak()` prématuré lèverait une erreur), `tts`/`ready`/`initDone` deviennent
`volatile` (lus depuis le thread JavaScript), voix par défaut si la liste reste
vide après `ready`, javadoc mis à jour.

**Garde-fou amont (P136, `scripts/prepare_src.py::patch_tts_lecture()`)** : la
boucle d'attente des voix de l'amont (`Y` dans `chunks/BeEbX_lw.js`) n'avait
aucune borne : sans voix, `nt()` — file de lecture des réponses de l'appel —
restait bloqué sur `await Y(st)`. Trois micro-remplacements (structure amont
intacte) : horodatage de l'attente, lecture forcée au-delà de 5 s sans voix
(voix par défaut du moteur), garde-fous 15 s sur la promesse (`Promise.race` —
un `speak()` sans retour d'événement ne peut plus figer la file). Branché dans
`main()` après `patch_mode_vocal()`.

**Justification du contrôle ajouté à `scripts/check_patches.py`
(`check_tts_lecture()`, branché dans `main()`)** : ces deux patchs sont *silencieux*
— un retour en arrière ne produit aucun symptôme au lancement, seulement un
appareil muet ; aucun contrôle existant ne les couvre. Le contrôle vérifie les
marqueurs Java (`ensureTts(() -> { })`, `initDone`, `ready` volatile) et les trois
motifs JS, plus l'*absence* de l'ancienne boucle non bornée (rétrogradation). Portée
étendue, rien n'est affaibli.

**Deux erreurs de parenthésage corrigées** en cours de route (dumps `})}` mal
décomptés dans le `Promise.race`) — validées par `node --check` sur l'extrait de
`Y` *et* sur le chunk complet avant de relancer `prepare_src.py` (136 opérations,
aucun `ERREUR`/`ÉCHEC`).

**Validation** : `py_compile` + `check_patches.py` vert ; sondes rejouées vertes —
`p128_tts_test` (9 scénarios), `p133_speech_test`, `p134_call_test`,
`p127_p129_test`, et **nouvelle `p136_tts_wait_test`** (4 scénarios sur la fonction
`Y` réellement livrée : voix immédiates → lecture immédiate ; jamais de voix →
lecture forcée ~5 s ; `speak` muet → résolution ~15 s ; voix tardives ~1,2 s ;
piege `speechSynthesis` en lecture seule contourné par `Object.defineProperty`).

**Doc** : `PATCHES.md` (lignes P135/P136), `docs/maintenance.typ` (lignes
P135/P136 au tableau des patchs), `docs/audio.typ` (abstract porté au 18/11/2026,
section « Verrou d'initialisation du synthétiseur — corrigé (P135/P136) »,
tableau récap et références enrichis) — les deux PDF recompilés sans warning
(0 tableau Markdown, 0 gras Markdown, 0 `inline-cite` sans `url`).

**Limite** : `AndroidTTS.java` n'a pas pu être compilé localement (aucun `javac`
sur l'hôte — JDK portable du projet non monté dans cette session, seul le JRE
21 est présent) ; le fichier est validé par relecture et par les contrôles de
marqueurs, la compilation aura lieu au prochain build APK.

**Non committé à ce stade** ; la version reste **v0.0.78** — aucun nouveau tag,
aucune suppression de release, aucune régénération CI sans validation explicite
(règle utilisateur). Piste restée ouverte (non écrite) : **P137**, sérialisation
de la dictée.

## 2026-11-18 — v0.0.78 RÉGÉNÉRÉE (validation utilisateur) : P135/P136 livrés

Demande explicite de l'utilisateur : « crée une version 0.0.78 » — validation
donnée pour le cycle complet de régénération (la version reste v0.0.78, aucun
nouveau numéro).

- **Pré-requis** : `check_patches.py` vert + `TAG=v0.0.78 verifier_tag.py` ✓
  (versionName 0.0.78 == tag) + arbre de travail propre (`eb20a20`).
- **Release précédente déjà absente** : `gh release delete v0.0.78 --yes` a
  répondu « release not found » (et `gh release view` idem) — rien à effacer ;
  à noter que `gh release list` ne montrait que v0.0.77 et antérieures. La
  release créée par la CI porte `created_at` 2026-11-18T00:07:35Z (brouillon
  probable créé entre-temps) et `published_at` 07:23:15Z.
- **Tag repris** : `git tag -d v0.0.78` (était sur `76f9e1d`) →
  `git push origin :refs/tags/v0.0.78` → `git tag v0.0.78 eb20a20` →
  `git push origin master` puis `git push origin master v0.0.78`
  (jamais `git push --tags`) — tag local **et** remote sur `eb20a20`,
  `git describe --tags` = `v0.0.78`.
- **CI** : run `44257851519` (Build APK, ref `v0.0.78`, push sur `eb20a20`) —
  **success** (07:18:30Z → 07:23:20Z, ~4 min 50).
- **Release `v0.0.78` publiée** avec les 2 APK **régénérés depuis `eb20a20`
  (donc avec P135 et P136)** :
  - `OpenWebUI_Android-0.0.78-debug.apk` (251 856 413 o)
  - `OpenWebUI_Android-0.0.78-release.apk` (247 319 128 o)
  (tailles différentes des APK de `76f9e1d` : 251 848 305 / 247 324 000 —
  preuve que les binaires ont bien été reconstruits.)

**Reste** : test appareil — dictée, mode vocal (transcription soumise au chat
*derrière* l'overlay : l'overlay lui-même n'affiche que l'avatar, le micro et
les statuts « Listening… »/« Thinking… », vérifié dans le code amont), et
surtout **génération audio** (P135/P136).

## 2026-11-18 — P137 : en mode vocal, chaque réponse est enfin lue

Retour utilisateur après l'APK régénéré (P135/P136) : « tout semble marcher,
mais en mode vocal je n'ai pas de retour audio, et aucun retour écrit ; les
trois points bougent » — donc la réponse *est générée* (transcription bien
soumise au `submitPrompt` du composeur) mais jamais lue.

**Diagnostic** : le texte n'apparaît nulle part *par conception amont* —
l'overlay n'affiche que l'avatar, le niveau du micro et les statuts
(« Listening… »/« Thinking… ») ; le sous-titre `V` ne porte que l'emoji
(`showEmojiInCall`). La transcription et la réponse vont donc dans le chat
*derrière* l'overlay. Restait l'absence de lecture.

**Cause racine (prouvée par sonde, pas supposée)** : sonde nouvelle
`/tmp/opencode/p137_call_playback_test.py`, qui extrait du chunk la chaîne
RÉELLE (`ct`/`pt`/`wt`/`nt`/`Ue`/`Y`) et la rejoue avec `speechSynthesis`
contrôlé. Résultat *avant* correctif :
- 1ᵉʳ message d'un chat neuf → **lu** ;
- 2ᵉ message du même chat après `chat:finish` → **jamais lu** ;
- changement de chat → lu.

La boucle `nt` se *terminait* (`break`) dès que la réponse était finie et la
file vide, alors que `ct` (`chat:start`, dispatché à **chaque** génération par
la fonction `cl`) ne la relançait que si l'identifiant de chat *changeait*
(`Le!==at`) : les segments suivants s'empilaient dans `rt` sans aucun
lecteur. Comportement amont (nos patchs ne touchaient ni `ct`, ni `pt`,
ni `wt`, ni `nt`).

**Correctif (P137, `scripts/prepare_src.py::patch_appel_lecture()`, 3
micro-remplacements, `break` conservé — aucune boucle orpheline)** :
1. déclaration d'un marqueur de boucle active `ntSig` ;
2. à la fin du tour, `ntSig=null` (elle devra être relancée) ;
3. dans `ct` : `bt[at]=!1` (sinon la boucle relancée se re-arrêtait
   aussitôt — débloqué au 2ᵉ essai de la sonde), relance de `nt` si aucun
   tour n'est associé au signal courant, recréation de l'`AbortController`
   si l'ancien a été annulé (interruption), et `a(q,!0)` remis hors de la
   garde `Le!==at` — sans l'état « parle », la détection de parole resterait
   active pendant la lecture et le micro capterait la voix de l'assistant.

**Justification du contrôle ajouté à `check_patches.py`
(`check_appel_lecture()`, branché dans `main()`)** : ce défaut est
*discret* — l'appel semble fonctionner (micro, transcription, génération) et
seul le 2ᵉ message révèle le silence ; aucun contrôle existant ne couvre la
chaîne de lecture de l'appel. Le contrôle vérifie la présence du marqueur, son
effacement à la fin du tour, la relance + l'effacement du drapeau « réponse
finie », la recréation du signal annulé, l'état « parle » — et deux motifs de
*rétrogradation* (la boucle amont non relançable et le `ct` d'origine).
Portée étendue, rien n'est affaibli.

**Validation** : `prepare_src.py` → 139 opérations, aucun `ERREUR`/`ÉCHEC` ;
`py_compile` + `check_patches.py` verts ; **sonde P137 verte sur les 4
scénarios** (chat neuf, 2ᵉ message du même chat, changement de chat,
reprise après interruption) ; non-régression vertes : `p136_tts_wait_test`,
`p128_tts_test` (9 scénarios), `p133_speech_test`, `p134_call_test`,
`p127_p129_test`.

**Doc** : `PATCHES.md` (ligne P137), `docs/maintenance.typ` (ligne P137 au
tableau des patchs), `docs/audio.typ` (nouvelle section « Réponses de
l'appel : file de lecture — corrigé (P137) » — dont la note que l'overlay
n'affiche aucun texte par conception —, tableau récap et références
enrichis) ; 2 PDF recompilés **sans warning** (0 tableau Markdown, 0 gras
Markdown, 0 `inline-cite` sans `url`).

**Publication** : commit sur `master` puis régénération de **v0.0.78** (tag
repris sur le nouveau commit + CI) — sur demande explicite de l'utilisateur.

## 2026-11-18 — v0.0.78 RÉGÉNÉRÉE (P137 livré)

Demande explicite : « une fois terminé, régénère la version 0.0.78 ».

- **Pré-requis** : `check_patches.py` vert (nouveau `check_appel_lecture`),
  `TAG=v0.0.78 verifier_tag.py` ✓, 6 sondes vertes, 2 PDF recompilés sans
  warning, arbre propre (`5f47747`).
- **Release supprimée** : `gh release delete v0.0.78 --yes` (les 2 APK de
  `eb20a20` sont retirés).
- **Tag repris** : `git tag -d v0.0.78` (était sur `eb20a20`) →
  `git push origin :refs/tags/v0.0.78` → `git tag v0.0.78 5f47747` →
  `git push origin master v0.0.78` (jamais `git push --tags`) — tag local et
  remote sur `5f47747`, `git describe --tags` = `v0.0.78`.
- **CI** : run `44264202171` (Build APK, ref `v0.0.78`) — **success**
  (08:06:49Z → 08:11:12Z, ~4 min 23).
- **Release `v0.0.78` publiée** à 08:11:09Z avec les 2 APK régénérés depuis
  `5f47747` (donc avec **P135, P136 et P137**) :
  - `OpenWebUI_Android-0.0.78-debug.apk` (251 849 321 o)
  - `OpenWebUI_Android-0.0.78-release.apk` (247 322 224 o)
- Lien vérifié (HTTP 200) : `https://github.com/FredSources/Openwebui_Android/releases/tag/v0.0.78`
- Commit journal ci-dessous poussé sur `master` **sans toucher au tag**.

## 2026-11-18 — P138/P139 : messages d'erreur distincts + « Default » → Kokoro

Deux demandes utilisateur le jour même :
(1) message exact « Accès aux appareils multimédias refusé » affiché à tort ;
(2) « de plus si default ne fonctionne pas il faudrait que le default soit
Kokoro.js ».

- **P138 — messages distincts** (`chunks/BeEbX_lw.js` + `chunks/DRZDe0Yd.js`) :
  le bouton « Mode vocal » enveloppait `getUserMedia` ET l'init du worker
  Kokoro dans un *même* `try` — toute erreur Kokoro (modèle injoignable,
  `Voice "alloy" not found`…) affichait « Accès aux appareils multimédias
  refusé ». Découpe en deux `try` : le micro garde le message amont exact +
  `return` (pas d'appel sans micro) ; l'init Kokoro logue
  `Kokoro TTS: …` (toast + `console.warn`) et l'appel s'ouvre quand même.
  (b) dans la file de lecture TTS (`Be`), l'init `he()||(…init())` n'était
  dans aucun `try` : échec = rejet silencieux (aucun son, aucune erreur) —
  interceptée : journal `Kokoro TTS: …`, états « ne parle pas » redressés
  (`p(Me,!1),p(Se,!1)`) puis `return`.
- **P139 — « Default » inutilisable → le default devient Kokoro**
  (`nodes/2.DwSK4ZlF.js` + `nodes/55.s0_1KP7y.js`) : même IIFE dans les
  DEUX chargeurs de `$settings` (`ne` du layout après chargement serveur,
  toutes les routes ; `de` de `/s/[id]`, entrées directes). engine du compte
  vide → sonde de voix ≤ 2 s (polling 150 ms, `AndroidTTS.voicesJson()` puis
  `speechSynthesis.getVoices()`, cache `window.__owuiSysTTS`) ; aucune voix
  ET moteur admin vide → `engine:"browser-kokoro"`, `dtype:"q8"` si absent
  (sinon fp32 ≈ 325 Mo), `voice:"af_heart"`, `defaultVoice` aligné sur
  `config.audio.tts.voice` (la chaîne amont `je()`/`Ce()` n'utilise
  `settings.voice` QUE si `defaultVoice === config.voice` — sinon « alloy »
  → `Voice "alloy" not found`, d'où « Erreur après avoir choisi Kokoro »).
  engine déjà kokoro → normalisation synchrone (voix hors af_/am_/bf_/bm_ →
  af_heart, dtype manquant → q8). Aucun forçage si voix système présentes,
  TTS serveur réglé ou config non chargée ; en mémoire seulement.
- **Validation** : sonde `/tmp/opencode/p138_p139_test.py` — **TOUT VERT**
  (10 contrôles P138a / 4 scénarios, 5 P138b, 14 P139 × 2 fichiers /
  S1-S6, 6 non-régressions : p127_p129, p128, p133, p134, p136, p137).
  `prepare_src.py` → 143 opérations ; `check_patches.py` vert
  (`check_erreur_tts`, `check_default_kokoro`, `check_js_syntax` étendu aux
  nodes 2/55) ; `node --check` vert sur les 4 fichiers transformés ; cibles
  `old` uniques dans le pristine.
- **Docs** : `PATCHES.md` (P138/P139), `docs/maintenance.typ` (tableau),
  `docs/audio.typ` (sections P138, P139 + limitation « phonémisation
  toujours anglaise des 28 voix Kokoro ») — 2 PDF recompilés sans warning,
  contrôle grammatical passé.
- **Limitation documentée** : le worker Kokoro embarqué = 28 voix
  (af_/am_/bf_/bm_), phonémisation forcée en anglais
  (`_validate_voice` → en-us/en) — pour du français : « Web API » (voix du
  téléphone) ou moteur distant.
- **EN ATTENTE** : validation utilisateur puis régénération v0.0.78
  (interdit sans validation explicite). Les logs activés côté appareil
  doivent montrer P135/P137 ; P138/P139 exigent une reconstruction de l'APK.

## 2026-11-18 — v0.0.78 RÉGÉNÉRÉE (P138/P139 livrés)

Validation utilisateur : « regenere 0.0.78 ».

- **Pré-requis** : `check_patches.py` vert (`check_erreur_tts`,
  `check_default_kokoro`), `TAG=v0.0.78 verifier_tag.py` ✓, sonde
  `p138_p139_test.py` verte (43 contrôles + 6 non-régressions), 2 PDF
  recompilés sans warning, arbre propre (`527529d`).
- **Release supprimée** : `gh release delete v0.0.78 --yes` (les 2 APK de
  `5f47747` sont retirés).
- **Tag repris** : `git tag -d v0.0.78` (était sur `5f47747`) →
  `git push origin :refs/tags/v0.0.78` → `git tag v0.0.78 527529d` →
  `git push origin master v0.0.78` (jamais `git push --tags`) — tag local et
  remote sur `527529d`, `git describe --tags` = `v0.0.78`.
- **CI** : run `44410135285` (Build APK, ref `v0.0.78`) — **success**
  (22:17:30Z → 22:21:58Z, ~4 min 28).
- **Release `v0.0.78` publiée** à 22:21:52Z avec les 2 APK régénérés depuis
  `527529d` (donc avec **P135 à P139**) :
  - `OpenWebUI_Android-0.0.78-debug.apk` (251 856 313 o)
  - `OpenWebUI_Android-0.0.78-release.apk` (247 335 492 o)
- Lien vérifié (HTTP 200) : `https://github.com/FredSources/Openwebui_Android/releases/tag/v0.0.78`
- Commit journal ci-dessous poussé sur `master` **sans toucher au tag**.

## 2026-11-18 — P140 : Kokoro retrouve son backend (ONNX Runtime Web conservé)

Rétroaction utilisateur sur l'APK régénéré (P138 fonctionne — l'erreur est
enfin visible, non masquée) :
`Kokoro TTS: Error: no available backend found. ERR: [webgpu] TypeError:
Failed to fetch dynamically imported module:
http://127.0.0.1:8080/wasm/ort-wasm-simd-threaded.jsep.mjs`

- **Cause racine** : P13 (`slim_frontend`) supprimait le dossier
  `frontend/wasm/` entier (21 Mo) au titre d'un « ONNX Runtime Web = ML
  navigateur, inutile ici » — mais le worker Kokoro force
  `wasmPaths="/wasm/"` et importe dynamiquement
  `ort-wasm-simd-threaded.jsep.mjs` (44 Ko) + `.jsep.wasm` (21,6 Mo).
  Sans eux, aucun backend (webgpu/wasm) ne peut s'initialiser.
- **Correctif (P140)** : `slim_frontend` ne supprime plus que les source
  maps ; `wasm/` est conservé. MIME vérifiés sur la table embarquée
  Python 3.13 (indépendante de `/etc/mime.types`) : `.mjs → text/javascript`
  (requis pour l'import dynamique), `.wasm → application/wasm`. Le frontend
  extrait est servi à la racine (SPAStaticFiles) : `/wasm/…` résolu.
- **Garde-fou** : `check_wasm_ort` dans `check_patches.py` — présence des 2
  fichiers dans `src-assets/frontend/wasm/` avec tailles minimales (40 Ko /
  20 Mo, anti-troncature) + `wasmPaths="/wasm/"` intact dans
  `kokoro.worker-*.js` (rétrogradation détectée).
- **Validation** : `prepare_src.py` 143 opérations, `check_patches.py` vert,
  sonde `p138_p139_test.py` verte (43 contrôles + 6 non-régressions).
- **Docs** : `PATCHES.md` (ligne P13 annotée + P140), `maintenance.typ`
  (P140), `audio.typ` (prérequis `/wasm/` dans la section P139) — PDF
  recompilés sans warning, contrôle grammatical OK.
- **Régénération v0.0.78** : chaîne ci-dessous (validation utilisateur
  « regenere 0.0.78 » toujours en cours sur cette même release).

## 2026-11-18 — v0.0.78 RÉGÉNÉRÉE (P140 livré)

Suite du « regenere 0.0.78 » utilisateur, après la rétroaction du jour.

- **Pré-requis** : `check_patches.py` vert (avec `check_wasm_ort`),
  `TAG=v0.0.78 verifier_tag.py` ✓, sonde `p138_p139_test.py` verte
  (43 contrôles + 6 non-régressions), 2 PDF recompilés sans warning, arbre
  propre (`e3aceab`).
- **Release supprimée** : `gh release delete v0.0.78 --yes` (les 2 APK de
  `527529d` sont retirés).
- **Tag repris** : `git tag -d v0.0.78` (était sur `527529d`) →
  `git push origin :refs/tags/v0.0.78` → `git tag v0.0.78 e3aceab` →
  `git push origin master v0.0.78` (jamais `git push --tags`) — tag local et
  remote sur `e3aceab`, `git describe --tags` = `v0.0.78`.
- **CI** : run `44413777676` (Build APK, ref `v0.0.78`) — **success**
  (22:40:16Z → 22:45:10Z, ~4 min 54).
- **Release `v0.0.78` publiée** à 22:44:58Z avec les 2 APK régénérés depuis
  `e3aceab` (donc **P135 à P140**, `wasm/` ONNX Runtime inclus) :
  - `OpenWebUI_Android-0.0.78-debug.apk` (258 120 430 o)
  - `OpenWebUI_Android-0.0.78-release.apk` (252 409 897 o)
- Lien vérifié (HTTP 200) : `https://github.com/FredSources/Openwebui_Android/releases/tag/v0.0.78`
- Commit journal ci-dessous poussé sur `master` **sans toucher au tag**.

## 2026-11-18 — P141 : mode vocal, la transcription locale n'arrivait jamais

Résumé utilisateur : « la dictée fonctionne, la lecture automatique de
réponse en audio fonctionne. le mode vocal ne fonctionne pas » — en mode
vocal, « aucun texte n'arrive sur le chat ».

- **Cause racine (conflit matériel)** : le shim de dictée documente déjà le
  conflit : « le MediaRecorder monopolise le micro et le SpeechRecognizer
  natif n'entend rien (no-speech) » — d'où son flux silencieux de
  substitution. Or `Ge` (mode vocal) démarrait le MediaRecorder sur le VRAI
  micro (`__realMic`, P134) exactement quand `__callDictation.start()`
  ouvrait la reconnaissance : le natif était sourd → `text()` vide → aucune
  soumission → rien dans le chat. Étouffement cumulé : la garde amont
  `blob < 100 o` bloquait aussi la transcription locale (le blob est ignoré
  en STT « web »).
- **Correctif (P141)** :
  (a) `Ge` : en STT « web », le MediaRecorder enregistre le flux SILENCIEUX
  (`window.__callSilent()`, polyfill) — il ne sert qu'à déclencher
  `onstop → Qe → De` ; la détection de parole (VAD) et le SpeechRecognizer
  gardent le vrai micro. En STT serveur, le vrai micro reste (blob téléversé).
  (b) `De` : garde `blob < 100 o` réservée au chemin serveur.
  (c) polyfill : repli sur les résultats partiels si le final n'arrive pas,
  fenêtre d'attente `text()` 3 s → 5 s.
  (d) traçabilité device : `console.warn("Call STT: local -> N car.")` +
  toast `Call STT: transcription vide (micro non entendu ?)` si vide.
- **Validation** : sonde `/tmp/opencode/p141_call_stt_test.py` — **TOUT VERT**
  (4 polyfill, 4 Ge, 12 De, 7 non-régressions : p127_p129, p128, p133,
  p134, p136, p137, p138_p139). `prepare_src.py` 145 opérations,
  `check_patches.py` vert (`check_appel_stt_local`).
- **Docs** : `PATCHES.md` (P141), `maintenance.typ` (P141), `audio.typ`
  (section P141) — PDF recompilés sans warning, contrôle grammatical OK.
- **Régénération v0.0.78** : chaîne ci-dessous (itération active sur cette
  release, validation utilisateur « regenere 0.0.78 »).

## 2026-11-18 — v0.0.78 RÉGÉNÉRÉE (P141 livré)

- **CI** : run `44422882568` (Build APK, ref `v0.0.78` → `25a0028`) —
  **success** ; release publiée à 23:45:38Z :
  `OpenWebUI_Android-0.0.78-debug.apk` (258 114 030 o),
  `OpenWebUI_Android-0.0.78-release.apk` (252 409 561 o).
- **Test appareil** : la chaîne P141 est atteinte jusqu'à `De` (toast
  `Call STT: transcription vide (micro non entendu ?)` visible = VAD, fermeture
  d'énoncé, `Qe`, `De` et le toast fonctionnent) MAIS le SpeechRecognizer
  n'a rien entendu : `text()` ressort vide.
- **Cause restante (P142)** : l'analyseur WebAudio (`xt(z)`) tient lui aussi
  le micro réel (client AudioRecord actif) — même effet de silence du
  recognizer natif que le MediaRecorder avant P141.

## 2026-11-19 — P142 : mode vocal, libérer le micro à l'ouverture de l'énoncé

Test appareil P141 : le toast `Call STT: transcription vide (micro non
entendu ?)` s'affiche — la chaîne P141 fonctionne jusqu'à `De` (VAD,
fermeture, `Qe`, `De`, toast) mais le SpeechRecognizer n'a rien entendu.

- **Cause restante** : l'analyseur WebAudio du VAD (`xt(z)`) tient lui aussi
  le micro réel (client AudioRecord actif) — même silence imposé au
  recognizer natif que le MediaRecorder avant P141. Capture concurrente :
  toute capture « MIC » côté web assourdit le SpeechRecognizer (comportement
  documenté par le shim de dictée).
- **Correctif (P142) — démultiplexage temporel du micro** :
  (a) à l'ouverture de l'énoncé, les pistes du micro sont stoppées et
  `z=null` (Ge() en reprendra un frais à la fermeture) ; le recognizer est
  démarré AVANT la libération (ordre garanti) ;
  (b) « la parole continue » = l'activité du recognizer lui-même
  (`window.__callVadHit()` : résultat partiel/final reçu depuis < 800 ms) —
  le VAD muet ne peut plus entretenir `Mt` ; la fermeture survient 2 s après
  le dernier résultat (ou 2,8 s après l'ouverture si le recognizer reste
  muet) ;
  (c) le toast de transcription vide porte la dernière erreur moteur :
  `Call STT: transcription vide (moteur : no-speech)` — diagnostic device
  explicite (« micro tenu » vs « moteur en échec »).
- **Validation** : sonde `/tmp/opencode/p142_call_vad_test.py` — **TOUT VERT**
  (7 polyfill : `__callVadHit` graine/activité/silence/hold + champ `error`
  de `text()` ; 4 ouverture : ordre start→libération, `z` réinitialisé, micro
  conservé en STT serveur ; 8 non-régressions dont p141).
  `prepare_src.py` 148 opérations, `check_patches.py` vert
  (`check_appel_vad`).
- **Docs** : `PATCHES.md` (P142), `maintenance.typ` (P142), `audio.typ`
  (suite P142) — PDF recompilés sans warning.
- **Régénération v0.0.78** : chaîne ci-dessous.

## 2026-11-19 — P143 : préchauffage du recognizer + console JS journalisée

Test appareil P142 : `Call STT: transcription vide (moteur : no-speech)` —
le micro est bien libéré mais le recognizer n'a rien entendu : démarrage
froid (liaison du service, 1-2 s) — l'énoncé est écoulé avant que le moteur
n'écoute, et la fermeture le coupe.

- **(a) Préchauffage** : `__callDictation.warm()` appelé dès l'ouverture de
  l'appel (chunk) — session créée puis annulée (400 ms) : seul le lien de
  service compte ; `start()` annule un préchauffage en cours et le minuteur
  du warm ne cible jamais la session réelle.
- **(b) Grâce d'activité** portée à 2,5 s ; le prêt du moteur (`onstart`)
  entretient l'activité (mesure de la latence de démarrage).
- **(c) Télémétrie device** : le toast de transcription vide embarque code
  d'erreur brut + latence : `Call STT: transcription vide (moteur :
  no-speech #7 (prêt à 812 ms))` — distingue « micro tenu » / « moteur
  froid » / « moteur en échec » ; suffixe `(jamais prêt)` si le moteur n'a
  jamais démarré.
- **(d) Console JS captée dans data/logs/exec.log** (`onConsoleMessage` +
  `journalConsole`, même fichier que les journaux Python) : traces
  `[call-dict]`, `Call STT:`, `Kokoro TTS:` consultables dans `/fm` →
  Journaux **et lisibles à distance** via `/fm/logs/tail` (diagnostic
  direct depuis l'hôte, sans logcat — verrouillé par Android).
- **Validation** : sonde `/tmp/opencode/p143_call_warm_test.py` — TOUT VERT
  (7 polyfill, 3 diagnostic). `prepare_src.py` 149 opérations,
  `check_patches.py` vert (`check_appel_diag`). Java non compilable
  localement : validation par les marqueurs + test appareil.
- **Docs** : `PATCHES.md` (P143), `maintenance.typ` (P143), `audio.typ`
  (suite P143) — PDF recompilés.
- **Accès diagnostic** : serveur de l'appareil sur `localhost:8080`
  (réseau partagé Termux), `/fm/logs/tail` avec le token admin — les
  prochains tests sont lisibles en direct depuis l'hôte.

## 2026-11-19 — v0.0.78 RÉGÉNÉRÉE (P143 livré)

- **CI** : run `44476750726` (Build APK, ref `v0.0.78` → `5daa530`) —
  **success** ; release publiée à 07:09:33Z :
  `OpenWebUI_Android-0.0.78-debug.apk` (258 115 130 o),
  `OpenWebUI_Android-0.0.78-release.apk` (252 414 013 o).
- **Validation** : sonde p143 (10 contrôles) + p142 (11 contrôles + 8 non-
  régressions) vertes avant build ; `check_patches.py` vert.
- **Attendu au test appareil** : mode vocal transcrit les énoncés dans le
  chat ; en cas d'échec, le toast porte code erreur + latence
  (`no-speech #7 (prêt à …)`) et les traces `[call-dict]` / `Call STT:` sont
  lisibles dans `/fm` → Journaux et via `/fm/logs/tail`.
- Commit journal ci-dessous poussé sur `master` **sans toucher au tag**.

## 2026-11-19 — P144 : écoute permanente, fin de la troncature de début

Constat utilisateur : « toute la chaîne est fonctionnelle, mais le début de
ma phrase est tronqué » — et « ce problème n'apparait pas en mode dictée ».
Clé : en dictée, le recognizer démarre AVANT la parole (le tap précède la
phrase) ; en mode vocal, il démarrait AU début de la parole (déclenché par la
détection) : les ~300-500 premiers ms (latence de démarrage) étaient perdus.

- **(a) Écoute permanente** : `warm()` = `start()` — le recognizer écoute
  dès l'ouverture de l'appel ; les énoncés sont découpés par MARQUEURS :
  `mark()` garde l'hypothèse partielle en cours (la phrase dès son premier
  mot — c'était la troncature) et efface l'ambiance (fenêtre de déclenchement
  100 ms) ; relance de session 250 → 150 ms, compteur remis à chaque session
  aboutie ; `stop()` à la fermeture de l'appel (`Ke`).
- **(b) Micro réel réservé au recognizer** : `Ge` branche VAD (analyseur) et
  MediaRecorder sur le flux SILENCIEUX en STT local — plus aucune capture web
  concurrente (conflit documenté par le shim de dictée) ; la libération de
  micro P142b est retirée (arrêter le flux déclencherait l'arrêt anticipé du
  MediaRecorder → `Qe` en plein énoncé).
- **(c) Silenciation TTS** : `__callSpeechGate` vide les tampons à chaque
  image pendant la lecture — la voix de l'assistant n'entre jamais dans la
  transcription, et aucune activité résiduelle ne déclenche un faux énoncé.
- **Validation** : sonde `/tmp/opencode/p144_call_test.py` — **TOUT VERT**
  (5 contrôles : tête de phrase conservée, historique effacé, silenciation
  TTS, segments concaténés + p141/p142/p143 vertes). `prepare_src.py` 153
  opérations, `check_patches.py` vert (`check_appel_permanente`).
- **Docs** : PATCHES.md, maintenance.typ, audio.typ — PDF recompilés.

## 2026-11-19 — v0.0.78 RÉGÉNÉRÉE (P144 livré)

- **CI** : run `44481344297` (Build APK, ref `v0.0.78` → `0b6717b`) —
  conclusion et assets ci-dessous ; tag local/remote sur `0b6717b`.
- **Attendu au test** : le début de phrase n'est plus tronqué (le recognizer
  écoute avant la parole, comme en dictée) ; en cas d'écart, les traces
  `[call-dict]` restent lisibles via `/fm/logs/tail`.

## 2026-11-19 — P145/P146/P147 : tiling, écho IA, faux « aucun son »

Trois retours appareil suite à la validation de P144 (« ok ca fonctionne »),
traités ensemble (2026-11-19T13:17Z).

- **P145 — bip de « tiling » au début/fin de dictée et à chaque réactivation
  du micro** : cause = le canal `STREAM_NOTIFICATION` joué par le service de
  reconnaissance. `AndroidSpeech.java` : mute ciblé (`ADJUST_MUTE`) avant
  `startListening()`, dé-mute différé 800 ms après `stop()`/`cancel()`
  (`scheduleUnmute`, annulé si un nouveau cycle commence), restauration
  `unmuteNotifNow()` (seulement si muet par nous — l'état muet de
  l'utilisateur est respecté). `MainActivity.java` : champ `androidSpeech`,
  dé-mute garde-fou dans `onDestroy()` et avant `Process.killProcess` dans
  `restartApp()` (le mute est un état système persistant qui survivrait à la
  mort du process). Seul le canal notification est touché ;
  `MODIFY_AUDIO_SETTINGS` déjà au manifeste. **Non compilable en local**
  (aucun `javac`) → validation device finale à faire.
- **P146 — « la conversation continue toute seule »** : le recognizer
  (écoute permanente P144) livre des résultats TARDIFS après l'extinction du
  TTS ; l'activité résiduelle entretenait le VAD et rouvrait des énoncés sur
  la voix de l'assistant. `call_polyfill.js` : `__callSpeechGate(muted=true)`
  arme `graceUntil = now + 2500 ms` ; pendant la grâce, `onresult` ignore
  les résultats tardifs (trace `résultat ignoré (grâce post-TTS)`),
  `__callVadHit()` renvoie `false`, `onstart` n'entretient pas l'activité,
  `mark()` refuse l'énoncé (trace `énoncé refusé (grâce post-TTS)`) ;
  `stop()` remet `graceUntil = 0` (réouverture propre).
- **P147 — « aucun son entendu » affiché alors que le silence est normal** :
  `prepare_src.py` : nouvelle fonction `patch_appel_silence()` chaînée sur
  la sortie P142c — `st.error` vide / `no-speech` / `aborted` /
  « aucun résultat » → trace console seulement
  (`Call STT: silence normal, ignoré (…)`, déjà journalisée dans
  `exec.log`) ; vraies erreurs moteur et `st=null` (erreur serveur) gardent
  leur toast. Le contrôle P142c de `check_patches.py` est aligné (motif
  template literal `${ce}`, libellé « moteur : » conservé) — justification :
  P147 reformule le toast, le contrôle enchaîne sans s'affaibrir.
- **Contrôles ajoutés** (`check_patches.py`, `check_appel_silence_grace_tiling`)
  : P145 (canal `STREAM_NOTIFICATION`/`ADJUST_MUTE`, dé-mute différé,
  restauration ≥ 2 endroits, champ `androidSpeech`), P146 (6 motifs du
  polyfill : armement, 4 points de branchement, réinit `stop()`), P147
  (trace « silence normal » présente, toast bloquant amont absent).
- **Sondes** : `p146_call_grace_test.py` (nouveau — 9 scénarios device joués
  dans `node` contre le polyfill réel : VAD hors/grâce, onstart silencieux,
  mark refusé, résultat tardif ignoré, tampons vides, stop réinitialise) ;
  `p141_call_stt_test.py` étendue (4 scénarios P147 : silence normal sans
  toast, `no-speech` sans toast, erreur réseau toastée, `st=null` toastée ;
  extraction du segment `De` réalignée sur la fin reformulée).
- **Chaîne complète : TOUT VERT** — `py_compile` (2 scripts),
  `prepare_src.py` **154 opérations** (+ P147), `check_patches.py` vert,
  `node --check` polyfill, sondes p141 (24 De + non-régressions) / p142 /
  p143 / p144 / p146 (9) toutes vertes.
- **Docs** : PATCHES.md (+P145/P146/P147), todo.md (P144 coché validé
  device ; P145-P147 en attente test appareil), maintenance.typ (+3
  entrées), audio.typ (+section « Retours appareil P145-P147 ») — PDFs
  recompilés (avertissement `**` Markdown corrigé).

## 2026-11-19 — P145 : correctif CI (isStreamMuted → isStreamMute)

- **CI** : run `44532336357` **échec** à l'étape « Build APK » —
  `AndroidSpeech.java:80: error: cannot find symbol / method
  isStreamMuted(int)` : la méthode `AudioManager.isStreamMuted` **n'existe
  pas** dans l'API publique 34 (vérifié : `unzip -p android.jar
  android/media/AudioManager.class | strings` ne montre que `isStreamMute`).
- **Correctif** : orthographe réelle `isStreamMute(int)` (API 23+, minSdk 24
  — conforme) ; aucun autre symbole P145 incriminable (Handler
  `post`/`postDelayed`/`removeCallbacks`, `ADJUST_MUTE`/`ADJUST_UNMUTE`,
  `Context.AUDIO_SERVICE` — tous présents de l'API 1).
- **Contrôle renforcé** (justifié : piège CI avéré) : `check_patches.py`
  P145 exige désormais `isStreamMute(` avec libellé rappelant que
  `isStreamMuted` casse la compilation — une régression d'orthographe ne
  pourra plus passer en local.
- `check_patches.py` vert ; relance de la régénération ci-dessous.

## 2026-11-19 — v0.0.78 RÉGÉNÉRÉE (P145/P146/P147 livrés)

- **CI** : run `44533293871` (Build APK, ref `v0.0.78` → `be206b2`) —
  **success** (4m15s) ; tag local/remote `v0.0.78` forcé sur `be206b2`
  (release supprimée puis recréée, 2 APK : debug + release).
- **Retours attendus au test appareil** : (1) plus de bip de tiling au
  début/fin de dictée (P145 — mute du canal notification) ; (2) la
  conversation ne repart plus toute seule après la réponse (P146 — grâce
  post-TTS 2,5 s) ; (3) plus de message « aucun son entendu » sur un
  silence normal (P147 — trace console à la place).
- **Diagnostic à distance** : traces `[call-dict]`, `Call STT: silence
  normal…`, `résultat ignoré (grâce post-TTS)` dans `/fm/logs/tail`.
- **Audit de minimisation** en cours (demande utilisateur) : 56+ fonctions
  `patch_*` ; la chaîne vocale P134→P147 reste la zone la plus patchée du
  chunk `BeEbX_lw.js`.

## 2026-11-19 — audit de minimisation des patchs (−4 opérations)

Demande utilisateur : « minimiser le nombre de patchs ». Inventaire des
56+ fonctions `patch_*`, focalisation sur la chaîne vocale P134→P147 (zone
la plus patchée : 8 fonctions sur le chunk `BeEbX_lw.js`).

- **P142b + P144c supprimés (−2)** : P142b *insérait* la libération du
  micro à l'ouverture de l'énoncé, P144c la *retirait* — deux opérations
  qui s'annulaient (livré net identique depuis P144). Les deux sont
  supprimées ; un commentaire de fusion documente le retrait. Le contrôle
  `check_patches` « libération rétablie interdite » reste en place (garde
  contre réintroduction future).
- **P134#6 fusionné dans P141b (−1)** : le remplacement « transcription
  locale » était *réécrit* intégralement par P141b (garde blob + trace) ;
  P141b prend désormais le **code amont brut** en entrée et régénère la
  même sortie.
- **P134#7 fusionné dans P144b (−1)** : idem — le remplacement « vrai
  micro » (`__realMic`) est réécrit par P144b (choix du flux silencieux) ;
  P144b prend le motif amont brut en entrée.
- **Résultat** : `prepare_src.py` **154 → 150 opérations** ; P134 passe de
  7 à 5 micro-remplacements (docstrings PATCHES.md/maintenance.typ
  alignées).
- **Preuve d'identité du livré** : après régénération, `git status
  src-assets/` = **0 fichier modifié** (le code produit est strictement
  identique à `be206b2`) — zéro risque fonctionnel, aucune régénération
  d'APK nécessaire au-delà du commit de scripts.
- **Sondes : TOUT VERT** — p134, p138_p139, p141 (24 De + 7 non-rég.),
  p142 (8 non-rég.), p143 (9 non-rég. — 1ᵉʳ passage : 1 échec
  transitoire non reproduit, 2ᵉ passage complet vert), p144, p146 (9) ;
  `check_patches.py` vert.
- **Sonde p134 alignée sur le contrat P144** (mise à jour justifiée, pas
  un affaiblissement) : elle validait l'ancien comportement *remplacé
  délibérément* par P144 et validé device (« ok ca fonctionne ») —
  (1) `hold()` ne stoppe **plus** l'écoute (écoute permanente : la
  fermeture est par `stop()`) ; (2) après `hold()`, `onend` **relance**
  la session (plus de trou d'écoute) ; (3) `mark()` efface l'historique à
  l'ouverture d'un nouvel énoncé (le résultat « après hold » n'est plus
  concaténé à l'ancien contenu). Preuve de préexistence : les 3 échecs
  étaient identiques avec le polyfill d'`a2fd676` (avant P145-P147),
  rejoué explicitement.
- **Reste à faire** : régénération v0.0.78 (commit scripts, livré
  identique) pour garder tag/HEAD alignés.

## 2026-11-19 — v0.0.78 RÉGÉNÉRÉE (audit de minimisation livré)

- **CI** : run `44548137095` (Build APK, ref `v0.0.78` → `d190742`) —
  **success** ; tag local/remote forcé sur `d190742`, release recréée
  (2 APK). Livré identique à `be206b2` (0 diff `src-assets/`) : la
  régénération ne sert qu'à garder tag/HEAD alignés.
- **Bilan de la session** : P145 (bip de tiling), P146 (grâce post-TTS),
  P147 (silence sans toast) livrés + audit −4 opérations ; 7 sondes
  vertes ; `check_patches.py` vert (150 opérations `prepare_src.py`).
- **En attente utilisateur** : validation device P145 (aucun `javac`
  local), P146 et P147 (traces lisibles via `/fm/logs/tail`).

## 2026-11-19 — migration Open WebUI 0.13.0 → 0.13.4 (en cours)

Demande utilisateur : « se maintenir sur la last release » de
github.com/open-webui/open-webui. Dernière release = **v0.13.4** (17 nov
2026) ; projet épinglé sur 0.13.0 (décision D6).

- **Bascule de version** : `scripts/fetch_src.sh` `OPEN_WEBUI_VERSION` →
  0.13.4 ; `vendor/unpacked` réextrait (wheel PyPI 0.13.4 vérifié : 200,
  `py3-none-any`, cap Python `<3.13` identique — neutralisé par P5).
  Le CI lit la version à cet endroit exact → bascule locale+CI ensemble.
- **Relocalisation des 5 fichiers frontend hashés** (minification
  entièrement renommée en 0.13.4) :
  | ancien | nouveau |
  |---|---|
  | `chunks/BeEbX_lw.js` | `chunks/BnHPywC-.js` |
  | `chunks/DRZDe0Yd.js` (TTS) | `chunks/AZSCJQb3.js` |
  | `nodes/2.DwSK4ZlF.js` | `nodes/2.Dki0jDRo.js` |
  | `nodes/55.s0_1KP7y.js` | `nodes/56.DyQrwVL7.js` |
  | `chunks/wN8N8j40.js` (sprite) | `chunks/wCZlPA5v.js` |
- **Audit d'échecs** (`/tmp/opencode/mig_audit.py`, `replace_once`
  tolérant) : **44 patchs appliqués, 28 en échec** — backend Python
  100 % vert (0 échec), tous les échecs sont frontend :
  - `BnHPywC-.js` : 18 (P134 #3/#4/#5, P136 ×3, P137 ×3, P141a/b,
    P142a/c, P143, P144a/b/d, P147, P138a) ;
  - `2.Dki0jDRo.js` : 7 (P131 ×2, P132 ×3, P139a, P10) ;
  - `AZSCJQb3.js` : 1 (P138b) ; `56.DyQrwVL7.js` : 1 (P139b).
- **Correspondances du chunk d'appel** relevées : `De`→`ot` (STT fin
  d'énoncé), `Qe`→`et`, `Ge`→`lt` (stream+MediaRecorder), `Ke`→`Ae`
  (fermeture), boucle VAD `cr`→`Wt`, `V0`→`Zk` (blob), `rb`→`Px` (API
  STT), `jt`→`xr`, `n()`→`i()` (settings), `e(P)`→`e(O)` (énoncé),
  `e(Q)`→`e(N)` (mute), `e(q)`→`e(Z)` (parle), `J`→`X` (MediaRecorder),
  `z`→`W` (stream), `ee`→`de` (chunks), `G`→`ce` (fin d'énoncé),
  `Mt`→`Tt`.

## 2026-11-20 — migration 0.13.0 → 0.13.4 validée + P148 (nouveau besoin)

Suite du 2026-11-19. Chaîne de validation complète, puis livraison
0.0.79_beta.

### P148 — `encode_basic_auth` (repli RFC 7617, aiohttp épinglé)

- **Découverte par le smoke test 8090** (étape jamais sautée, comme
  l'alerte du doc l'impose) : `ImportError: cannot import name
  'encode_basic_auth' from 'aiohttp'` au chargement de `open_webui.main`
  → `routers/auths.py` (introspection OAuth2) et `utils/oauth.py`
  (refresh de token, 2 sites) l'utilisent.
- **Cause** : la fonction n'existe que depuis aiohttp **3.11** ; le
  dépôt épinglle `aiohttp==3.10.10` (`[PIN-REPO] slim: 3.14.5 — « do not
  update to 3.13.3 »`) — **le pin n'est pas bougé**.
- **Repli fidèle** : `BasicAuth(login, password, encoding).encode()`
  (déjà présent en 3.10.10) — équivalence RFC 7617 **vérifiée en
  exécution** : `BasicAuth('id','secret',encoding='latin1').encode()` →
  `'Basic aWQ6c2VjcmV0'`, identique au format attendu.
- **Implémentation** (2 sites, `prepare_src.py` → 153 opérations) :
  (a) `auths.py` : import en `try/except ImportError` + définition de
  repli ; (b) `oauth.py` : garde `if not hasattr(aiohttp,
  "encode_basic_auth")` qui expose la fonction sur le module — les 2
  appels amont `aiohttp.encode_basic_auth(...)` restent **intacts**
  (aucune signature amont modifiée).
- **Contrôle** : `check_p148_aiohttp` dans `check_patches.py` — échec
  si l'import direct est rétabli, si le repli manque, ou si
  l'équivalence `BasicAuth.encode` disparaît.
- **Justification charte** : ajout d'un contrôle dans
  `check_patches.py` → motivé ici (nouveau patch P148, aucun contrôle
  existant affaibli).

### Réalignement des 25 contrôles de `check_patches.py` (motifs 0.13.4)

- **Justification (charte)** : les 25 motifs réalignés (P131/P132,
  P136, P137, P138a/b, P139, P141a/b, P142a, P143, P144b/c, P41b,
  P46c, P106, P107 + marqueurs `node --check`) pointaient sur les
  **noms minifiés de 0.13.0** ; la minification de 0.13.4 renomme les
  identifiants, ce qui produisait de **faux positifs** (« patch mal
  appliqué » alors que le patch est bien présent). Aucun contrôle n'a été
  supprimé ni affaibli : chaque motif a été **relocalisé** sur la
  variable/fonction correspondante de 0.13.4 (cartographie détaillée
  dans l'entrée du 2026-11-19), et la structure logique contrôlée est
  identique.
- **Bug réel trouvé au passage** (P46c/P107) : le 5e paramètre ajouté
  `X=[]` entrait en collision avec le handler `onerror` `X` de `rt()` en
  0.13.4 → `SyntaxError: Identifier 'X' has already been declared` ;
  paramètre renommé **`Pk=[]`** (3 sites : signature, fusion
  `[..._e,...Pk]`, contrôle P46d) — sans ce fix, le bac à sable
  `execute_code` aurait cassé au premier appel.
- **P41b** : seuls les callbacks *message* portent les fichiers
  (`files:W.files||[]`, `W` = données du message, `ge` = worker) ;
  callbacks timeout/erreur sans `files:` (comportement amont préservé).
- **P87** : ancrage court `'6e4);const ce=se=>{'` remplacé par
  `'Math.max(5,TO||120)*1e3);const ce=se=>{'` (le motif à parenthèses
  était trop fragile).

### Validation complète — chaîne VERT

- `prepare_src.py` : **153 opérations, 0 échec** ;
  `check_patches.py` : **0 erreur** (« tous les patchs sont
  correctement appliqués ✓ ») ;
  audit tolérant `mig_audit.py` : **133 appliqués / 0 échec**.
- **`node --check`** : `call_polyfill.js`, `tts_polyfill.js`,
  `pyodide.worker-*.js`, `chunks/BnHPywC-.js` — tous verts.
- **`javac` 25 (OpenJDK 25, classpath `android-sdk/platforms/
  android-34/android.jar`)** : `AndroidSpeech.java`, `AndroidTTS.java`,
  `AndroidAudio.java` compilent **0 erreur** — première validation
  locale du code Java P145/P128/P130 (jusqu'ici « aucun javac local ») ;
  `MainActivity.java` exige Chaquopy + `R` générés (jar Chaquopy 17.2.0
  repéré dans `.gradle-cache`) — non compilable seule, hors périmètre du
  patch.
- **Sonde globale de non-régression** `/tmp/opencode/
  probe_migration_0134.py` (consolide les 7 sondes purgées) :
  **74/74 contrôles verts** — chunks 0.13.4, P131-P147, bac à sable,
  worker, motifs amont interdits (non-régressions), Java, javac.
- **Smoke test 8090** (jamais 8080) après P148 : `/` 200, `/health`
  200, `/api/config` 200, `/api/version` 200, `/favicon.ico` 200,
  SearXNG 8888 → 200 ; erreurs searx bénignes (engines `ahmia`/`torch`
  absents du slim, wikidata 403 externe) ; **aucun traceback
  applicatif** ; processus et ports libérés proprement après test
  (`pgrep` vide, 8080/8090/8888 libres).
- **Version backend `0.0.0`** : non-régression — `env.py` lit
  `package.json` (absent du wheel → repli `{'version': '0.0.0'}`),
  mécanisme identique en 0.13.0.

### Documentation

- `PATCHES.md` : titre → 0.13.4, 5 chunks renommés, **P148** ajouté.
- `docs/maintenance.typ` : version → 0.13.4 (architecture, sources,
  annexe), section « Mise à jour d'Open WebUI » **réécrite en 11
  étapes** avec la leçon de cette migration (bascule via `fetch_src.sh`,
  relocalisation des chunks hashés, réalignement justifié des contrôles,
  scan d'imports contre les pins, smoke test qui a attrapé P148),
  ligne **P148** au tableau des patchs — `maintenance.pdf` recompilé
  (0 warning).
- `docs/audio.typ` : 5 chunks renommés — `audio.pdf` recompilé (0
  warning).

### Livraison 0.0.79_beta

- **Commit** `180d183` (850 fichiers : scripts + doc + `src-assets/` régénéré
  0.13.4) poussé sur `origin master` (`95b2e6e..180d183`) — arbre propre
  (`git status` vide).
- **Garde-fou P93** : `verifier_tag.py` avec `TAG=v0.0.79_beta` →
  `✓ tag v0.0.79_beta == versionName 0.0.79_beta`.
- **Tag** `v0.0.79_beta` créé sur `180d183` et poussé **nommément**
  (`git push -f origin v0.0.79_beta` — jamais `--tags`).
- **CI** : run `44705257612` **success** (5 min 19) — seules annotations :
  dépréciations d'actions GitHub (Node 20, `setup-java@v4`), sans impact.
- **Release** publiée par `github-actions` :
  `https://github.com/FredSources/Openwebui_Android/releases/tag/v0.0.79_beta`
  avec `OpenWebUI_Android-0.0.79_beta-debug.apk` et `-release.apk`.
- **En attente utilisateur** : test appareil de la migration 0.13.4 (login,
  chat, dictée, mode vocal, TTS) + rétroactions ouvertes P145/P146/P147.

## 2026-11-20 17:34 UTC — audit de cohérence P134 (rétroaction device) + évaluation fournisseur realtime « local »

Rétroaction utilisateur sur v0.0.79_beta : « Le mode vocal n'est pas
disponible. La synthèse vocale et le mode dictée sont opérationnels » —
config précisée : **pas de realtime, engine `web`**. Puis : « Ce
comportement me va » (le refus amont en web non-realtime est **voulu**) et
demande d'**évaluer** l'ajout d'un fournisseur realtime « système vocal
local Android » (sans implémenter tout de suite).

### A) Audit de cohérence P134 — 2 patchs MORTS + 3 contrôles morts (faux verts)

Diagnostic factuel (pristine 0.13.4 vs livré, motifs exacts) :

| élément | état | preuve |
|---|---|---|
| P134 #1 (bouton affiché en web) | **MORT** | motif vars 0.13.0 `o()?…engine!=="web"&&(n()?…` → **0 occurrence** dans le pristine 0.13.4 ; « déjà appliqué » est un **faux positif** : son `new` = `"!0"` est présent partout |
| P134 #2 (refus `lo` neutralisé) | **MORT** | motif vars 0.13.0 (`nr`, `o()`, `$t.error`, `f().t`) → **0 occurrence** ; faux « déjà appliqué » car son `new` `"!1){}"` est **partagé avec #3** (`else if(!1){}` le contient) |
| P134 #3 (refus overlay neutralisé) | **VIVANT** | motif vars 0.13.4 `else if(r()?…==="web"){Mt.error(a().t(…))` : 1 dans le pristine → **0 dans le livré** (neutralisé) |
| refus clic (handler `on`) | **actif, voulu** | `engine==="web"){Mt.error(_().t("Call feature…` présent dans le livré — comportement amont conservé (« ce comportement me va ») |
| `check_mode_vocal` : 3 contrôles « refus revenu » | **TOUS MORTS** | motifs vars 0.13.0 (`n()`, `s()`, `$t/f()`) → **0 occurrence** dans le livré : faux verts, ils ne détecteraient aucune régression |

Conséquences fonctionnelles (expliquent la rétroaction) :
- #1 mort → le bouton « Call » du bandeau suit la condition amont
  (`realtime.enabled || engine !== "web"`) → **masqué** en web non-realtime
  = « mode vocal pas disponible » — comportement **confirmé voulu** ;
- #2 mort → le refus clic (`on`) est intact (inatteignable tant que le
  bouton est masqué) ;
- #3 vivant mais **inatteignable en l'état** (branche `current` de `bi`
  jamais prise sans realtime) → devient **essentiel** dès que le mode
  local forcera `current`.

Décisions (au feu vert) :
1. **Retirer P134 #1 et #2** de `prepare_src.py` : patchs morts =
   ajouts inutiles, faux « déjà appliqués » trompeurs (le retrait ne
   change **rien au livré** : leurs motifs sont introuvables).
2. **Garder P134 #3** : nécessaire au mode local (overlay ouvert en
   `current` avec engine `web`).
3. **Réaligner les 3 contrôles « refus revenu »** de `check_mode_vocal`
   sur les motifs 0.13.4 : (a) refus overlay `else if(r()?…` **absent**
   (neutralisé par #3), (b) refus clic `engine==="web"){Mt.error(_().t(…`
   **présent** (comportement amont voulu — contrôle inversé), (c) la
   condition bouton amont reste **présente** (elle doit l'être : le
   bouton est censé être masqué hors realtime). Justification charte :
   les anciens motifs ne compilent plus depuis la minification 0.13.4.

### B) Évaluation — fournisseur realtime « local » (système vocal Android)

Architecture existante cartographiée :
- **serveur** : `realtime.py` = proxy WS `client ↔ bridge ↔ provider`
  (OpenAI/Azure, protocole Realtime PCM 24 k + messages `bridge.*`) ;
  validation `provider not in {'openai','azure'}` (L314) ;
  schéma config `PROVIDER: Literal['openai','azure']`
  (`routers/audio/__init__.py:334`) ;
  handshake exige `model`+`voice`+`transcription_model` (L446).
- **client** (`BnHPywC-.js`) : clic bandeau → si `realtime.enabled` →
  overlay ; **bifurcation unique** dans l'effet d'ouverture `bi` :
  `m(connected||connecting||realtime.enabled ? "bridge" : "current")` ;
  `bridge` → `h().connect()` (WS) ; `current` → boucle existante
  (STT natif `__callDictation` + chat + TTS) — **qui est précisément le
  système vocal Android**.
- **réglages** (`nodes/2.Dki0jDRo.js`) : dropdown provider à **2 options**
  (`openai`, `azure`), champs URL/Key/Model/Voice affichés selon provider.

Modifications nécessaires (évaluation, pas encore appliquées) :

| # | Fichier | Modification | Nature |
|---|---|---|---|
| 1 | `nodes/2.Dki0jDRo.js` | 3ᵉ `<option value="local">` + libellé dans le dropdown Provider | requis |
| 2 | `nodes/2.Dki0jDRo.js` | masquer URL/Key/Model/Voice/Transcription si `PROVIDER==="local"` (aucun `required` ne doit bloquer) | requis |
| 3 | `chunks/BnHPywC-.js` | bifurcation `bi` : `…&&provider!=="local" ? "bridge" : "current"` (le WS n'est **jamais** ouvert en local) | requis — **cœur du patch** |
| 4 | `routers/audio/__init__.py:334` | `Literal['openai','azure']` → + `'local'` (sinon 422 à l'enregistrement) | requis |
| 5 | `routers/audio/realtime.py` | garde propre : si `local`, pas d'exigence model/voice/transcription (L446) + message explicite si un WS arrive quand même (L314) | robustesse |
| 6 | `prepare_src.py` + `check_patches.py` | patchs **P149** (réglages + bifurcation + backend) + contrôles ; nettoyage #1/#2 + réalignement `check_mode_vocal` | process projet |
| 7 | doc | `PATCHES.md`, `maintenance.typ`, `audio.typ` (PDF), `todo.md`, `journal.md` | livrable |

Aucune modification de : refus clic `on` (voulu), boucle `current`
existante (P134/P141-P147), TTS/dictée (confirmés opérationnels).

Points de vigilance à valider **à l'implémentation** :
1. la boucle `current` démarre-t-elle quand l'overlay est ouvert par le
   chemin realtime (`ic.set(!0), Mn.set(!0)`) ? — en 0.0.78 le mode
   `current` était atteint via le test `getUserMedia` du clic ;
2. `required` des champs réglages masqués en local ;
3. libellé i18n de l'option (fallback si clé absente) ;
4. `check_auth`/retry bridge : `m()==="current"` ⇒ jamais de reconnexion
   (vérifié : le `ve(...)` de retry teste `m()==="bridge"`).

## 2026-11-20 22:46 UTC — P149 livré : fournisseur realtime « android » (boucle vocale locale)

Décisions utilisateur de la séance :
- **UI identique au standard** — pas de masquage : « un flag pour désactiver
  l'ensemble », seul le fournisseur reste éditable ;
- **tag `v0.0.79_beta` forcé** (le tag/release existants 0.13.4+P148 sont
  remplacés — choix explicite « recrée 0.0.79_beta »).

### Implémentation — `patch_realtime_android()` (P149, 12 opérations)

1. **template** `nodes/2` : `Co=v("<option> </option> <option> </option>",1)`
   → 3 `<option>` — **piège découvert en Chromium** : le positionneur
   `n(ut,2)` de la 3ᵉ option sortait du template à 2 options →
   `TypeError: Illegal invocation` au montage du select (aucun contrôle
   Python ne le voit : `node --check` passe) ;
2. **dropdown** : 3ᵉ option `android` (idiome exact du TEXT_SPLITTER à
   3 options, variables `xY`/`xZ`/`zB` — `xA`/`xB`/`xT` du plan initial
   **existaient déjà**, collision évitée) ;
3. **bifurcation** `chunks/BnHPywC-.js` : `…realtime.enabled &&
   realtime.provider!=="android" ? "bridge" : "current"` → le WS n'est
   jamais ouvert pour android ;
4. **flag** : 7 champs cloud désactivés quand `PROVIDER==="android"`
   (URL, Voice Model, Voice, Transcription en `X.disabled=(e(u),a(…))`
   dans un `g()` ; API Key en prop `readOnly` — SensitiveInput n'expose
   pas `disabled` ; Input Params et Prompt en prop `disabled` — Textarea
   l'expose) ; Provider jamais touché ;
5. **backend** : `Literal['openai','azure','android']` +
   garde `realtime_call` → `Realtime calls are handled locally on Android`.

### Correctifs de séance (au fil des tests)

- chemins `DST/"open_webui"/routers` → `DST/"routers"` (double `open_webui`)
  — `FileNotFoundError` au 1er lancement ;
- payload `config/update` : `tts`/`stt` ont **tous leurs champs requis** →
  reconstruit depuis le `GET` (sinon 422) ;
- harnais CDP : sélecteur API Key corrigé (`type="text"`, id
  `password-input-*`, placeholder « API Key ») + `Network.setCacheDisabled`
  (nom de fichier immutable = cache navigateur) ;
- bisect pristine/patché : prouve que l'erreur `Illegal invocation` venait
  bien du template à 2 options (0 erreur sur pristine, 1 sur patché).

### Validations (toutes vertes)

| contrôle | résultat |
|---|---|
| `prepare_src.py` | **163 opérations, 0 échec** (151 nets + 12 P149) |
| `check_patches.py` (dont `check_realtime_android`) | OK |
| `probe_migration_0134.py` (javac API 34 inclus) | **74/74** |
| `node --check` (via `check_js_syntax`) | OK |
| smoke 8090 (`/health`, `/`, frontend servi patché) | OK |
| harnais CDP Chromium : dropdown | 3 options `openai/azure/android`, labels OK |
| harnais CDP : avant android | 7 champs **actifs** (baseline) |
| harnais CDP : après android | 7 champs **désactivés**, Provider **actif** |
| harnais CDP : retour openai | tout **réactivé** (flag réactif) |
| persistance API (`POST /config/update` + `GET`) | `PROVIDER=android` enregistré et relu |
| garde WS | `bridge.error: Realtime calls are handled locally on Android` |
| `Literal` (import réel) | openai/azure/android acceptés, autre rejeté (422) |

Nettoyage P134 également en place (non commité précédemment) : retrait des
2 patchs **morts** #1/#2 de `prepare_src.py` (motifs 0.13.0 introuvables),
`check_mode_vocal` réaligné sur 0.13.4 (refus bouton/clic = présence
requise, overlay neutralisé) — livré identique.

### Suite

`PATCHES.md` (P149 + ligne P134 corrigée) ; `maintenance.typ`,
`audio.typ` (+ PDF, grammaire) ; `todo.md` ; commit, push, tag
`v0.0.79_beta` **forcé**, release remplacée, CI.

## 2026-11-20 23:02 UTC — v0.0.79_beta livrée (P149 + nettoyage P134)

- `versionName '0.0.79_beta'` inchangé (déjà en place) ;
- commit `7c200f1` (11 fichiers : patchs + scripts + doc Typst/PDF + journal)
  poussé sur `origin master` ;
- tag `v0.0.79_beta` **forcé** de `75579e4` → `7c200f1` (décision
  utilisateur : remplacer la release 0.13.4+P148) puis poussé **nommément**
  (jamais `--tags`) — `origin master` et le tag sont alignés sur `7c200f1` ;
- CI **run 44832951778 → success** (5 min : build debug+release, APK
  vérifiés, release mise à jour) ;
- release `v0.0.79_beta` : titre « fournisseur realtime Android (P149) +
  nettoyage P134 », note P149 ajoutée, 2 APK (`debug` + `release`)
  remplacés ;
- annotations CI : dépréciations Node.js 20 / setup-java v4 (préexistantes,
  non bloquantes).

Reste ouvert : **test appareil** (choisir « Android » → champs désactivés →
Enregistrer → appel qui doit démarrer la boucle locale sans WS) —
`todo.md`.

## 2026-11-20 23:40 UTC — P149 corrigé au retour appareil (3 points)

Rétroaction utilisateur sur l'APK v0.0.79_beta :
1. « le menu Call mode a un champ vide comme 3ᵉ choix » ;
2. « je préfère que les champs soient invisibles plutôt que désactivés » ;
3. « lors de l'activation du call j'ai *Realtime calls are handled locally on
   Android* » (ma garde backend, donc le WS s'ouvrait quand même).

### Causes et correctifs

| # | Cause | Correctif |
|---|-------|-----------|
| 1 | `Co` (template `<option>` à 2) est **partagé** avec Call mode et Authentication : l'élargir ajoutait une 3ᵉ option vide **partout** | template **dédié `CoA`** à 3 options, déclaré à côté de `Co` (intact) et branché **uniquement** sur le select Provider (`var Oe=CoA()`) |
| 2 | demande : masquer, pas griser | **un seul effet** remplace les 7 désactivations : il remonte au conteneur de chaque `AdminSettingField` (div racine — template `rk=<div><label> <div>input</div> <desc></div>`) et pose `display:none` (label + champ + description d'un coup) ; l'API Key (SensitiveInput, id généré) est le **frère suivant** du champ URL ; réactivation au retour `openai` |
| 3 | `/api/config` n'exposait que `enabled/model/voice` pour realtime → `provider` = `undefined` → `undefined !== "android"` **toujours vrai** → « bridge » → `h().connect()` → garde | deux ajouts dans `main.py` : la clé `audio.realtime.provider` **dans le `get_many`** (sinon `config.get(...)` = `None`) puis `'provider': ...` **dans le dict** |

### Validations (toutes vertes, après correction)

- `prepare_src.py` : **160 opérations, 0 échec** (8 P149) · `check_patches.py`
  : OK (contrôles P149 réécrits : `CoA` présent, `Co` intact, Provider branché,
  masquage, config) ;
- `probe_migration_0134.py` : **74/74** (javac) ;
- harnais CDP Chromium : Call mode à **2 options** (3ᵉ vide disparue),
  dropdown 3 options, 7 champs **visibles → masqués → réaffichés**,
  Provider actif ;
- test d'appel décisif : config `{enabled:true, provider:"android"}` → clic
  **« Voice mode »** → **aucune requête WS/realtime** dans le réseau CDP et
  overlay **« Listening... »** (la boucle locale `current` démarre) ;
- persistance API + garde WS inchangées (message déjà servi si un client
  tente quand même).

### Suite

`PATCHES.md` (ligne P149 réécrite), `maintenance.typ`/`audio.typ` (PDF),
`todo.md`, commit, push, tag `v0.0.79_beta` **re-forcé**, CI.

## 2026-11-21 00:05 UTC — v0.0.79_beta re-livrée (3 corrections appareil)

- commit `faf6f60` (10 fichiers) poussé sur `origin master` ;
- tag `v0.0.79_beta` **re-forcé** `7c200f1` → `faf6f60` (poussé nommément,
  jamais `--tags`) — `origin master` et le tag alignés ;
- CI **run 44840579175 → success** (build debug + release, release mise à
  jour) ;
- release : titre « fournisseur realtime Android (P149) + retours appareil »,
  note P149 réécrite, 2 APK remplacés, `prerelease` remis à `false`
  (l'action l'avait basculé en suivant le tag « _beta »).

Corrections livrées (détail au 23:40) : template dédié `CoA` (plus d'option
vide dans Call mode), masquage des 7 champs (au lieu de la désactivation),
`audio.realtime.provider` exposé par `/api/config` (fin du WebSocket
inopiné). Reste ouvert : test appareil de cette version.

## 2026-11-21 10:20 UTC — P149 v2 : masquage au montage + garde du chargement réglages

Retour appareil (suite) :
1. « à l'ouverture, avec android déjà sélectionné, les champs qui devraient
   être cachés ne le sont pas ; quand on sélectionne android ils disparaissent » ;
2. message de transcription au moment de l'appel (« la dictée native (moteur
   « web ») ne transcrit pas les fichiers joints… ») — l'utilisateur précise :
   le bug avait lieu **car le voice call était activé**, sinon la dictée
   fonctionnait, et « avec ta correction du voice, tout sera peut-être
   fonctionnel » → à confirmer par un test de cette version.

### 1) Bug A — masquage absent au montage (corrigé)

Diagnostic au banc (trace ajoutée dans l'effet) :
`P149 mount droid=true conteneurs=0/6` — au premier passage de l'effet, ni les
`<label>` ni les inputs n'existent encore (les champs sont montés par des
brances `y()` postérieures) → aucun conteneur trouvé ET `reste=false` (les
éléments étaient absents, pas seulement les conteneurs) → **aucun retry**, et
comme `PROVIDER` ne change plus ensuite, l'effet ne se rejouait jamais.
Correctif : la condition de retry est désormais « tant que moins de 6
conteneurs sont traités » (borné à 40 frames), avec trace `P149 mount` au
montage (diagnostic device). Validé au banc : `conteneurs=0/6` puis **7 champs
masqués**, réactivité openai → visible → android → masqué.

### 2) Garde du chargement des réglages (préexistant, bloquant)

Pendant les tests, `/admin/settings` (et `/admin/settings/audio`) renvoyait
vers `/` : le patch **P139** lançait `TypeError: x.subscribe is not a function`
dans son `tick` — exécuté via `setTimeout(+150 ms)`, donc **hors** du `try` de
l'IIFE : l'exception n'était jamais avalée et cassait le chargement de la page.
Le pristine ne la déclenchait pas (0/4 contre 3/4 pour le livré, puis
« base avant P149 » également touchée → bug préexistant, pas de P149).
Correctifs dans `patch_default_kokoro` : `snap()` refuse un store non prêt
(`subscribe` absent → `null`) et le corps de `tick` est enveloppé dans son
propre `try/catch`. Le contrôle P139 de `check_patches.py` est aligné (motif
`fix(!0)}catch(e){}};` + exigences des deux nouvelles gardes).

### 3) Note de banc — routage admin

La bonne URL de test est `/admin/settings/audio` (l'overlay s'ouvre ensuite
sur `/` mais la section Audio — et le select Call mode — est bien affichée) ;
`/admin/settings` nu affiche une autre section (sans Call mode), ce qui a fait
perdre du temps en diagnostics. `__callDictation` n'existe **jamais** sur un
banc hôte (c'est `MainActivity` qui injecte `call_polyfill.js`) : les tests
d'appel doivent injecter le polyfill (`Page.addScriptToEvaluateOnNewDocument`)
pour se rapprocher de l'appareil.

### Validations

`prepare_src` **160 opérations / 0 échec** · `check_patches` OK (contrôles
P149 + P139 réalignés) · smoke 8090 (health/racine/signin 200, frontend servi
avec la trace) · harnais Bug A **VERT** (7 champs masqués au montage,
réactivité).

### Livraison

Régénération de **0.0.79_beta** demandée par l'utilisateur pour confirmer sur
l'appareil si la correction du voice call suffit à faire disparaître le message
de transcription (Bug B non corrigé en attente de ce retour).

## 2026-11-21 10:45 UTC — v0.0.79_beta régénérée (v2, P149 + gardes P139)

- commits `0e4773d` (P149 v2 + P139) et `130a48e` (gardes P139 dans le
  chargeur `/s/[id]`, `nodes/56` — oublié du premier add) poussés sur
  `origin master` ;
- tag `v0.0.79_beta` **re-forcé** `faf6f60` → `130a48e` (poussé nommément) —
  tag et master alignés ;
- CI **run 44912321275 → success** (build debug + release, release mise à
  jour) ;
- release : titre « fournisseur realtime Android (P149) — v2 », note listant
  les deux corrections + la procédure de test appareil, 2 APK remplacés,
  `prerelease=false`.

À vérifier sur appareil : (1) champs masqués à l'ouverture avec Android déjà
sélectionné ; (2) disparition éventuelle du message de transcription à la
dictée quand l'appel est activé (Bug B — non corrigé, hypothèse : il venait
du mode bridge/WS désormais abandonné).
