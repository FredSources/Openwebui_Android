# OpenWebUI Android — APK autonome sans calcul de l'embedding local

[![Build APK](https://github.com/FredSources/Openwebui_Android/actions/workflows/build-apk.yml/badge.svg)](https://github.com/FredSources/Openwebui_Android/actions/workflows/build-apk.yml)

APK Android qui embarque le serveur **Open WebUI 0.13.0** (FastAPI + SQLite +
frontend SvelteKit compilé) dans un interpréteur **Python 3.13** (Chaquopy),
avec l'interface affichée dans une WebView locale (`http://127.0.0.1:8080`).
Le **LLM reste distant** : Ollama ou API OpenAI-compatible sur ton PC/serveur.

> Le **RAG est actif** : base vectorielle **locale** (`LocalVectorDB`, SQLite +
> numpy, force brute) pour le stockage des vecteurs ; les **embeddings sont
> calculés à distance par API** — la plateforme Android ne permet pas le calcul
> d'embedding local (pas de torch/sentence-transformers). La dictée utilise le
> moteur vocal natif Android. Voir `PATCHES.md` pour le détail exact.

## Contenu du dépôt

| Dossier / fichier | Rôle |
|-------------------|------|
| `AGENTS.md` | Objectif, périmètre, décisions, règle d'isolation |
| `todo.md` / `journal.md` | Suivi des tâches / historique horodaté |
| `PATCHES.md` | Toutes les modifications du code Open WebUI |
| `requirements-min.txt` | Dépendances Python embarquées (slim, RAG léger `LocalVectorDB`) |
| `vendor/unpacked/` | Wheel Open WebUI pristine (source des patchs) |
| `vendor/searxng/` | SearXNG figé (commit `a30b2d4749`) — copié dans `src/searx/` |
| `src/` | Code Python embarqué (Open WebUI patché + SearXNG + shims) |
| `app/` | Projet Android (Java + Chaquopy) |
| `wheels/` | Wheels Rust cross-buildés (pydantic-core, jiter) |
| `scripts/` | `env.sh`, `fetch_src.sh`, `prepare_src.py`, `setup-sdk.sh`, `build-wheels.sh`, `build.sh`, `smoke.sh` |
| `dist/` | APK produits |

**Isolation** : tout vit dans ce dossier (SDK, Gradle, Rust, NDK, venv).
Aucune installation globale. `scripts/env.sh` ancre les variables.

## Reconstruction de l'environnement (machine neuve)

Le dépôt git est auto-portant : ce qui est téléchargeable n'est pas versionné,
il se reconstruit avec un script unique —

```bash
git clone <dépôt> openwebui-android && cd openwebui-android
bash scripts/setup-env.sh --build      # environnement complet + APK
bash scripts/setup-env.sh --check      # audit de l'existant
```

Détail de la procédure, prérequis et dépannage : `docs/environnement.pdf`.
Environnement terminé ≈ 13 Go (SDK/NDK compris), ≈ 3 Go de téléchargements.

## Build de l'APK

Prérequis : Linux aarch64/x86_64, JDK 17+, réseau, ~8 Go libres.

```bash
# 1. venv Python 3.13 (buildPython Chaquopy) + dépendances
/opt/opencode-venv/bin/python3 -m venv .venv313
.venv313/bin/pip install -r requirements-min.txt

# 2. sources patchées (idempotent)
.venv313/bin/python scripts/prepare_src.py

# 3. tout le reste : SDK Android, Gradle, wheels Rust, APK
bash scripts/build.sh            # → dist/app-debug.apk
```

Pour un APK signé « release » : `bash scripts/build.sh assembleRelease`
(générer d'abord un keystore et le référencer dans `app/build.gradle`).

## CI/CD (GitHub Actions)

`.github/workflows/build-apk.yml` build les APK **debug et release** uniquement
lors du push d'un tag `v*`, et publie la **Release GitHub** avec les APK attachés :

```bash
git tag v0.3.0 && git push origin v0.3.0   # → build CI + release + APK attachés
```

Les APK sont nommés `OpenWebUI_Android-<version>-<variante>.apk`
(ex. `OpenWebUI_Android-1.0.0-release.apk`) — même nom en build local (`dist/`).

Signature release : ajouter les secrets `KEYSTORE_BASE64`, `KEYSTORE_PASSWORD`,
`KEY_ALIAS`, `KEY_PASSWORD` au dépôt — sinon l'APK release est signé avec la clé
debug (installable, pour tests).

## Installation et usage

1. Copier `dist/app-debug.apk` sur le téléphone (`adb install` ou téléchargement),
   autoriser « sources inconnues ».
2. Premier lancement : le serveur démarre (~10-30 s la première fois : extraction
   des assets Python + migrations SQLite).
3. Créer le compte admin, puis pointer vers ton LLM :
   - **Ollama** : Réglages → Connexions → URL de ton PC
     (ex. `https://pc-maison.tailnet:11434` via **Tailscale** — recommandé),
   - ou **API OpenAI-compatible** : Réglages → API.
4. Astuce : la notification « Open WebUI est en cours d'exécution » maintient
   le serveur vivant en arrière-plan (foreground service).

## RAG — embeddings distants, base vectorielle locale

Architecture retenue (contrainte plateforme) : **le téléphone ne calcule pas
d'embeddings**, tout passe par une API ; en revanche le **stockage des vecteurs
est local**, dans un backend embarqué maison (SQLite + numpy, aucun module natif).

| Rôle | Solution embarquée | Configuration |
|------|--------------------|---------------|
| **Embeddings** (obligatoirement distant) | API OpenAI-compatible / Ollama / Azure | **Admin → Documents** : moteur d'embedding, modèle, URL, clé |
| **Stockage vectoriel** (local) | `LocalVectorDB` (SQLite + numpy) | `VECTOR_DB=local` (**défaut**) → `data/vector_db/local_vectors.sqlite3` |
| Rerank | API externe (optionnel) | Admin → Documents → moteur de rerank |
| RAG totalement éteint | `NullVectorDB` | `VECTOR_DB=none` |

La recherche est une force brute vectorisée (exacte) : confortable jusqu'à
~100 000 fragments sur téléphone. La configuration avancée passe par
`data/openwebui.env` (chargé au démarrage, `KEY=VALUE`) si besoin.

> Les bases vectorielles **distantes** (Qdrant, Elasticsearch…) restent
> théoriquement supportées par le code Open WebUI mais demandent des clients
> supplémentaires problématiques sous Android (grpcio-tools, protobuf) — non
> fournies. Exigence produit : le moteur d'embedding est distant, pas la base.

## Recherche web — SearXNG embarqué

L'app embarque une **instance SearXNG locale** (`127.0.0.1:8888`), exposée comme
provider **`embedded-searxng`** dans *Réglages → Admin → Recherche web* (moteur
par défaut). Aucun réglage requis : les résultats web alimentent la recherche
des conversations et l'outil de recherche intégré.

- SearXNG figé sur le commit `a30b2d4749` (2026-08-28, avant la dépendance
  native `curl_cffi`) ; `msgspec` (C) cross-buildé dans `wheels/`.
- Réglages générés au premier lancement dans `data/searxng-settings.yml`
  (clé secrète propre à l'appareil, API JSON activée) — modifiable.
- Un SearXNG distant reste possible : choisir le provider `searxng` et renseigner
  son URL (`Réglages → Recherche web → SearXNG URL`).

## Notes de portage (Android)

- **Python 3.13** alors qu'Open WebUI annonce `<3.13` : le cap vient de
  `pydub`/`audioop` (supprimé de la stdlib en 3.13) ; ce chemin est neutralisé
  (patch P5) — test de fumée hôte vert sur 3.13.5.
- `pydantic-core`, `jiter`, `uuid_utils`, `orjson`, `rpds_py` (natifs Rust
  absents du dépôt Chaquopy) sont cross-buildés par `scripts/build-wheels.sh`
  (rustup + NDK + Python Android via l'artefact Maven `com.chaquo.python:python`,
  clang hôte + sysroot du NDK — le NDK officiel est x86_64).
- Les outils Android x86_64 (`aapt2`, `zipalign`) tournent via **qemu-user-static**
  (`tools/qemu/`, wrappers branchés par `android.aapt2FromMavenOverride`) —
  indispensable sur machine aarch64.
- Le premier démarrage extrait le frontend (≈250 Mo) dans le stockage privé ;
  les suivants sont rapides.
- Connexion au LLM distant : privilégier HTTPS (Tailscale / Cloudflare Tunnel).

## Licence

Open WebUI : BSD-3-Clause — attribution requise (notice conservée dans l'app).
