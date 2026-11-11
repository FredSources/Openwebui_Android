# PATCHES.md — Modifications appliquées au code Open WebUI 0.13.0

Tous les patchs sont générés par `scripts/prepare_src.py` (idempotent, rejouable)
à partir de `vendor/unpacked/open_webui` (wheel PyPI pristine). Objectif unique :
**retirer le RAG** et rendre le reste exécutable sur Android/Python 3.13.

| # | Fichier | Modification | Motif |
|---|---------|-------------|-------|
| P1 | `config.py` | `VECTOR_DB` défaut → `'local'` | Base vectorielle **LOCALE** par défaut (les embeddings restent distants) |
| P2 | `retrieval/vector/type.py` | Ajout `VectorType.NONE` et `VectorType.LOCAL` | Nouveaux backends embarqués |
| P3 | `retrieval/vector/factory.py` | Cas `LOCAL` → `LocalVectorDB`, cas `NONE` → `NullVectorDB` | Aucune dépendance locale d'embedding ; base locale maison |
| P4 | `tools/knowledge_fs.py` | `import re2` → repli `re` | google-re2 (natif) absent du dépôt Android |
| P5 | `routers/audio/__init__.py` | `pydub` importé en try/except | `pydub` exige `audioop`, retiré de la stdlib en Python 3.13 |
| P6 | `storage/provider.py` | Imports Azure/GCS en try/except | `google-cloud-storage` tire protobuf/grpcio (natifs absents d'Android) |
| P7a-c | `routers/audio/__init__.py` | `faster-whisper` / `transformers` / `soundfile+torch` en try/except → HTTP 503 explicite | STT/TTS locaux inembarquables (ctranslate2, torch) : erreur claire au lieu de `ModuleNotFoundError` |
| P8 | `config.py` | `AUDIO_STT_ENGINE` défaut → `'web'` | la dictée utilise le **moteur vocal natif Android** via le shim `SpeechRecognition` (Java `AndroidSpeech.java` + polyfill JS) |
| P9 | `routers/retrieval.py` | Nouveau provider **`embedded-searxng`** dans `search_web()` → `http://127.0.0.1:8888` | SearXNG embarqué : recherche web locale, aucun réglage requis |
| P10 | `frontend/_app/immutable/nodes/*.js` | `embedded-searxng` ajouté à la liste des providers (dropdown) | libellé = valeur brute, affiché tel quel dans l'UI |
| P9b | `routers/retrieval.py` | Message d'erreur de `search_web()` qui porte le moteur lu | diagnostic des mauvaises configurations |
| P11 | `tools/builtin.py` + `utils/tools.py` | Outil **`compile_typst`** (.typ → PDF) et son enregistrement | compilateur Typst embarqué (wheel `typst`) |
| P12 | `utils/tools.py` | `features.get('web_search', True)` | les outils internet (`search_web` = `embedded-searxng`, `fetch_url`) sont exposés même quand le modèle ne déclare pas la capacité dans ses métadonnées — *supersédé par P18* |
| P18 | `utils/tools.py` | gate des outils web réduit à `web.search.enable` + permission utilisateur | `search_web`/`fetch_url` exposés quelles que soient les capacités modèle (`capabilities.web_search`, `builtinTools.web_search`) et le toggle `features` de la requête — les API tierces écrivent souvent `false` explicite dans la fiche modèle et le frontend envoie `features.web_search=false` quand le globe n'est pas actionné |
| P13 | `frontend/` (données) | allègement : source maps, `pyodide/`, `wasm/` supprimés (169 Mo) | ML navigateur et Python-navigateur retirés (règle « pas de calcul local ») |
| P14 | `routers/auths.py`, `routers/utils.py`, `routers/configs.py` | imports différés : `ldap3`, `black`, `MCPClient` | −3,4 s au démarrage |
| P15 | `src/` → `src-assets/` | frontend sorti des assets Python → assets Android extraits une fois par `MainActivity` (progression affichée) | import serveur 35,5 s → 11 s ; APK allégé |
| P16 | `open_webui/migrations/` (+ `build.gradle`) | `migrations/` et `versions/` marqués paquets + `extractPackages` : les `.py` restent sur disque | Alembic lit `env.py`/`versions/*.py` en fichiers — Chaquopy les retirait après compilation bytecode (blocage « … migrations/env.py ») |
| — | `src/searx/` | **SearXNG embarqué** (vendor figé sur `a30b2d4749`, 2026-08-28 — avant la migration `curl_cffi`) | serveur local `127.0.0.1:8888`, réglages générés par `android_main.py` (clé secrète propre à l'appareil, `search.formats: [html, json]`) |
| — | `retrieval/vector/dbs/none.py` | **Nouveau** : `NullVectorDB` | RAG éteint (`VECTOR_DB=none`) : insertions ignorées, recherches vides |
| — | `retrieval/vector/dbs/local.py` | **Nouveau** : `LocalVectorDB` | Base vectorielle **locale** SQLite + numpy (force brute vectorisée, score cosinus dans [0,1]) — `VECTOR_DB=local` |
| — | `src/tiktoken.py` | **Nouveau** : shim | tiktoken (Rust) non fourni ; comptage approximatif (suffisant pour le chunking RAG local) |
| — | `src/pycrdt.py` | **Nouveau** : stub | pycrdt (Rust) non fourni ; collab dégradée (accumulateur d'updates) |

## Dépendances retirées (voir `requirements-min.txt`)

- **RAG** : chromadb, sentence-transformers, torch, transformers, accelerate,
  onnxruntime, colbert-ai, einops, sentencepiece, pgvector, rank-bm25 conservé (léger).
- **Indisponibles sur Android** : google-re2, pycrdt, tiktoken, orjson (repli json
  natif du code), hiredis, uvloop/httptools/watchfiles (via `uvicorn` sans `[standard]`),
  soundfile, pycares/aiodns, opentelemetry-* (+ googleapis-common-protos/protobuf),
  psycopg/psycopg2 (SQLite uniquement).
- **Pins adaptés au dépôt de wheels Android** (plafonds plus anciens que PyPI) :
  cryptography 42.0.8, bcrypt 3.2.2, numpy 1.26.2, aiohttp 3.10.10, lxml 5.3.0,
  Pillow 11.0.0, regex 2024.9.11, psutil 7.1.3, authlib 1.6.4 (1.7+ exige
  joserfc≥1.6 → cryptography≥45), joserfc 1.5.0.

## Comportement après patch

- Chat, auth, outils, fichiers, API distantes (Ollama / OpenAI-compatible) : **intacts**.
- **RAG par services distants** : pipeline complet (découpage, retrieval, rerank)
  dès que les embeddings passent par une API (`RAG_EMBEDDING_ENGINE=openai|ollama|azure_openai`)
  et que les vecteurs vont dans une base tierce (`VECTOR_DB=qdrant|elasticsearch|opensearch|weaviate`).
  Configuration sur l'appareil via `data/openwebui.env` (chargé par `android_main.py`).
  Clients embarqués : qdrant-client, elasticsearch, opensearch-py, weaviate-client.
- **Moteurs RAG locaux exclus** (exigence produit) : chromadb, sentence-transformers,
  torch → `VECTOR_DB=none` par défaut (NullVectorDB) ; toute tentative locale
  remonte une erreur claire.
- **Dictée vocale** : fonctionne via le moteur vocal **natif Android**
  (souvent hors-ligne) grâce au mode STT « web » + shim `SpeechRecognition`
  (`app/src/main/java/org/openwebui/android/AndroidSpeech.java`). Basculable
  vers un STT distant dans Réglages → Audio.
- STT/TTS local (faster-whisper/transformers) : **indisponible** (HTTP 503
  explicite) ; utiliser les API distantes ou la dictée native.
- Stockage Azure/GCS : indisponible ; stockage **local** fonctionnel.
- Édition collaborative (pycrdt) : dégradée sur un seul appareil.

## Vérification

`scripts/smoke.sh` (hôte, Python 3.13) : serveur démarré, `/health` → `{"status":true}`,
frontend servi, `POST /api/v1/auths/signin` → 200 + JWT.

## Bac à sable Pyodide — le piège des DEUX copies

Le bundle frontend embarque **deux copies** de la logique du bac à sable :

- `workers/pyodide.worker-*.js` — worker **persistant**, instancié par
  `new Worker(new URL(…))`. C'est **lui qui s'exécute** (`android_main.py` force
  `ENABLE_PYODIDE_FILE_PERSISTENCE=true`, contrôle P44).
- `chunks/*.js` (fonction `patch_pyodide_universel`) — copie de **repli**
  « universel » (iframe / worker recréé depuis un blob), **jamais atteinte**
  dans notre configuration.

| # | Cible | Modification | Motif |
|---|-------|-------------|-------|
| P38 | `workers/pyodide.worker-*.js` | boot `packages:["micropip","numpy","pandas","sympy"]` | les paquets scientifiques étaient indisponibles (`ModuleNotFoundError`) quand la détection regex d'import échouait |
| P44b | `chunks/*.js` | même boot sur la copie de repli | filet de sécurité si le mode persistant est désactivé |
| P102 | `chunks/*.js` | boot réduit à `['micropip','numpy']` | ~115 Mo de wasm au boot → OOM Android. **Erreur de cible** : seul le repli fut allégé, le worker garda le boot lourd (v0.0.53 inopérante) |
| **P103** | `workers/pyodide.worker-*.js` | boot réduit à `packages:["micropip","numpy"]`, pandas/sympy **à la demande** (`j(self.packages)`) | le worker est la copie exécutée : c'est lui qu'il fallait alléger. Contrôle `check_patches.py` aligné (boot allégé exigé partout, boot lourd rejeté partout) — journal v0.0.54 |
| **P104** | `socket/main.py` + `android_fm.py` | diagnostic de livraison des appels outils : traçage des paquets EVENT avec id d'ack remis au transport (+ erreurs), état réel des participants à l'appel, raisons de déconnexion, échecs d'auth socket, route d'auto-test `/fm/diag/eventcall` | `sio.call(to=sid)` ne livre jamais le paquet dans l'app (navigateur et client python testés, 2026-11-10) alors que la même chaîne fonctionne hors Android — les émissions de *room* arrivent, les ciblées par sid non. Sans ces traces, chaque test appareil reste muet — journal v0.0.55 |
| **P105** | `socket/main.py` | sanitisation JSON du payload des appels outils : tout octet brut (fichiers récoltés par P51/P77, `data: bytes`) est converti en liste d'entiers | `json.dumps` levait `Object of type bytes is not JSON serializable` à l'envoi du paquet — l'exception, avalée par `asyncio.wait(tasks)`, laissait l'appel muet (« bac à sable muet »). Tracé par `P104 SEND-ERREUR` — journal v0.0.56 |
| **P106** | `chunks/*.js` (bundle) | la voie **worker** du bac à sable est forcée (`const cp=()=>new hp`) | le bundle créait le bac à sable au chargement du module, *avant* l'arrivée de la config : `features.enable_pyodide_file_persistence` (pourtant `true` dans l'API) était `undefined` → la copie **iframe** (sans ramassage P41, sans persistance IDBFS, sans P99b) était choisie et mise en cache à vie. 3ᵉ occurrence du piège des deux copies : `files: []`, écritures non persistées, `display_file` « introuvable » — journal v0.0.57 |
| **P70** — *révoqué* | `nodes/0.*.js` | ~~préchauffage du bac à sable au chargement de la page~~ — **retiré (v0.0.58)** | créer le bac à sable avant la config faisait choisir la copie de repli (piège des deux copies, 3ᵉ occurrence). Le bac à sable est créé *à la demande*, comme en amont — le gain (~3 s sur le premier appel) ne valait pas l'écart |
| **P107** | `nodes/0.*.js` | le paramètre `TO=120` (délai d'exécution) est restauré dans la signature de `Me()` | il était introduit dans le même remacement que le préchauffage P70 — la révocation de P70 (v0.0.58) l'a emporté alors que le corps en dépend (`exec_timeout: TO`, minuteur) : « TO is not defined » — journal v0.0.59 |
