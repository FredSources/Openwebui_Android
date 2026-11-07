# AGENTS.md — Projet OpenWebUI Android (APK autonome)

## Objectif

Produire un **APK Android installable** (téléphone / tablette) qui embarque le serveur
**Open WebUI complet, RAG sans embeddings locaux**, tournant localement sur l'appareil :

- le backend **FastAPI + uvicorn + SQLite** d'Open WebUI s'exécute **dans l'APK**
  (interpréteur Python embarqué via **Chaquopy**) ;
- le frontend SvelteKit compilé est servi par ce backend et affiché dans une **WebView**
  pointant sur `http://127.0.0.1:8080` ;
- le **LLM reste distant** : Ollama ou API OpenAI-compatible sur un PC / serveur
  (joignable via Tailscale ou Cloudflare Tunnel).

## Périmètre

| Inclus | Exclu (volontaire) |
|--------|--------------------|
| Backend Open WebUI (auth, chats, outils, historique SQLite) | **Embeddings locaux** : chromadb, sentence-transformers, torch |
| Frontend compilé (`static/`) | Inférence locale sur le téléphone |
| Appels LLM distants (Ollama / OpenAI-compatible) | Publication Play Store / iOS |
| **RAG** : embeddings **distants** (API openai/ollama/azure) + **base vectorielle LOCALE** (`LocalVectorDB` : SQLite + numpy) | **Calcul d'embedding local** : chromadb, sentence-transformers, torch |
| Upload de documents, micro/caméra via WebView | |
| STT/TTS via API distante si configurée | |

« Enlever juste le RAG » = supprimer les dépendances lourdes (chromadb, torch,
sentence-transformers, onnxruntime…) **et tout calcul d'embedding local**, tout en
gardant le pipeline RAG complet : le découpage/retrieval reste embarqué, les
embeddings vont par **API distante** (Admin → Documents) et les vecteurs vivent
dans la **base vectorielle locale** `LocalVectorDB` (SQLite + numpy) — seule la
puissance de calcul non disponible sur téléphone est déportée.

## Architecture

```
┌─ APK (appareil Android) ────────────────┐      ┌─ PC / serveur ──────────────┐
│  App Kotlin (MainActivity)              │      │  Ollama ou API OpenAI-compat │
│   ├─ Chaquopy : CPython 3.13 embarqué   │ HTTPS│  (le LLM)                    │
│   │    └─ thread → uvicorn :8080        │ ───► │  OLLAMA_BASE_URL /           │
│   │        └─ open_webui (RAG local)    │      │  OPENAI_API_BASE_URL         │
│   └─ WebView → http://127.0.0.1:8080    │      └──────────────────────────────┘
└─────────────────────────────────────────┘
```

## Décisions techniques (à ne pas re-négocier sans note au journal)

1. **Chaquopy 17.x** comme runtime Python Android (plugin Gradle `com.chaquo.python`).
2. **Python cible 3.13** (décision D7 au journal) : Chaquopy 17.2 + wheels cp313 du
   dépôt Android ; `pydantic-core`/`jiter` sont **cross-buildés localement**
   (`scripts/build-wheels.sh`). La contrainte `Requires-Python <3.13` d'Open WebUI
   vient de `pydub`/`audioop` et est neutralisée par le patch P5. `buildPython`
   = `.venv313/bin/python3` (3.13.5, dans le projet — isolation D5).
3. **ABI `arm64-v8a` uniquement** (APK plus léger, couvre tous les téléphones récents).
4. Serveur lancé en **thread daemon** dans `android_main.py`, écoute **127.0.0.1:8080**
   uniquement (jamais 0.0.0.0).
5. **Foreground service** Android pour que le serveur survive au passage en arrière-plan.
6. Configuration serveur LLM exclusivement par **variables d'environnement**
   (`OLLAMA_BASE_URL`, `OPENAI_API_BASE_URL`, `DATA_DIR`…) — pas de secret dans le code.
7. Sources Open WebUI dans `vendor/` ; le projet Android dans `app/` ;
   tout patch est documenté dans `journal.md` et automatisé dans `scripts/`.

## Règle d'isolation — NE PAS POLLUER L'ENVIRONNEMENT

**Tout ce dont le projet a besoin reste dans `/root/openwebui-android/`.**
Aucune installation globale, aucun fichier écrit en dehors de ce répertoire.

| Élément | Emplacement imposé (sous le projet) | Variable / levier |
|---------|--------------------------------------|-------------------|
| Android SDK (cmdline-tools, platform, build-tools) | `android-sdk/` | `ANDROID_HOME=$PROJ/android-sdk` |
| Gradle (+ son cache) | `tools/gradle/` et `.gradle-cache/` | `GRADLE_USER_HOME=$PROJ/.gradle-cache` |
| Python 3.12 (buildPython Chaquopy) | `tools/python312/` (portable, ex. `uv python install`) | `UV_PYTHON_INSTALL_DIR=$PROJ/tools/python312` |
| venv Python outils du projet | `.venv/` | `source .venv/bin/activate` |
| Sources Open WebUI | `vendor/open-webui/` | `git clone` dans `vendor/` |
| node_modules / cache npm | `vendor/frontend/node_modules/`, `.npm-cache/` | `npm_config_cache=$PROJ/.npm-cache` |
| Sorties de build (APK, rapports) | `dist/` puis `app/build/` | — |

Interdits : `apt install`, `pip install` hors venv du projet, écriture dans `~`,
`/usr`, `/opt`, `/tmp` (hors `/tmp/opencode` transitoire outil), modification de
`~/.config/opencode`. Les scripts `scripts/*.sh` doivent `export` toutes les
variables ci-dessus et refuser de tourner si `$PWD` n'est pas la racine du projet.

## Règles de travail (en plus des règles globales)

- **Français** pour toute la documentation et les échanges.
- **Documentation Typst TOUJOURS maintenue** : toute modification du projet
  (patch amont, version, script, composant, procédure) doit être répercutée dans
  la documentation Typst (`docs/maintenance.typ`, `docs/environnement.typ`),
  suivie d'une **recompilation des PDF**. La documentation est un livrable au
  même titre que l'APK : un changement non documenté est une tâche incomplète.
- À chaque session : lire `todo.md` (état) et `journal.md` (historique + décisions),
  puis **journaliser toute action** dans `journal.md` (horodatage UTC).
- Cocher les tâches dans `todo.md` au fur et à mesure ; ne jamais cocher sans test.
- Python : `/opt/opencode-venv/bin/python3` pour les scripts outils ; le `buildPython`
  de Chaquopy est un **python3.12** distinct (voir décision 2).
- Ne jamais inventer d'URL ; vérifier avec `curl -sIL` avant de référencer.

## Licence

Open WebUI est sous **BSD-3-Clause** : l'embarquage dans un APK et la redistribution
sont autorisés **avec attribution** (conserver la notice de licence dans l'app).

## Livrable final

`app/build/outputs/apk/release/app-release.apk` signé (ou `debug` pour le test),
installable par `adb install` ou téléchargement direct, avec `README.md` de build.
