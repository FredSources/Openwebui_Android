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
