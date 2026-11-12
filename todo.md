# todo.md — Tâches du projet OpenWebUI Android

Légende : `[ ]` à faire · `[~]` en cours · `[x]` fait (testé) · `[!]` bloqué

## Phase 0 — Cadrage et environnement

- [x] Créer le répertoire projet `/root/openwebui-android` + `git init`
- [x] Reconnaissance environnement (JDK 21, Python 3.13.5, Node 24, 8 cœurs, 110 Go libres)
- [x] Vérifier l'accès réseau (PyPI, GitHub, dl.google.com) — OK
- [x] Rédiger `AGENTS.md` (objectif), `todo.md`, `journal.md`
- [x] Récupérer les sources Open WebUI dans `vendor/` — wheel `open_webui-0.13.0`
      obtenu via le **python3.12 du projet** (le wheel exige `<3.13`, l'hôte 3.13
      ne pouvait pas le télécharger : cf. journal D6)
- [x] **Isolation (D5)** : `scripts/env.sh` ancre tout le projet dans `$PROJ`
- [x] Supprimer le dossier vide `vendor/wheel/` (reste du `pip download` échoué)
- [x] Installer **Python 3.12 portable** dans `tools/python312/` (copie `/opt/uv-python/`)
- [x] Version cible figée : **Open WebUI 0.13.0** (journal D6) — cible Python 3.13 (D7)

## Phase 1 — Backend « sans RAG »

- [x] Récupérer `open_webui/` (wheel 0.13.0 extrait dans `vendor/unpacked/`)
- [x] Frontend **déjà compilé** dans le wheel (`open_webui/frontend/`) — pas de npm
- [x] Produire `requirements-min.txt` = slim − RAG − natifs absents d'Android (pins repo)
- [x] Stub `NullVectorDB` + shims `tiktoken`/`pycrdt` + patchs P1-P6
      (`scripts/prepare_src.py`, documentés dans `PATCHES.md`)
- [x] Test de fumée locale : `uvicorn` démarre, `/health` répond, signin → JWT ✅

## Phase 2 — Projet Android (Chaquopy)

- [x] Squelette Gradle : `settings.gradle` (AGP 8.7.3), `build.gradle`, `app/build.gradle`
- [x] Plugin Chaquopy 17.2, `python { version '3.13' }`, buildPython = `.venv313`,
      `abiFilters arm64-v8a`, pip `--find-links wheels/`
- [x] `AndroidManifest.xml` : PyApplication, permissions, networkSecurityConfig
- [x] `MainActivity.java` : WebView (JS, DOM, upload, micro/caméra), retry /health
- [x] `android_main.py` : env vars, clé secrète persistée, thread uvicorn idempotent
- [x] `ServerService.java` : foreground service + notification
- [x] Ressources : icônes (générées Pillow), thème, chaînes

## Phase 3 — Build

- [x] Android SDK + Gradle dans le projet (`scripts/setup-sdk.sh`) — OK
- [x] Wheels Rust cross-buildés : pydantic-core, jiter, uuid_utils, orjson, rpds_py
      (`scripts/build-wheels.sh`, tags `android_24_arm64_v8a`)
- [x] JDK portable Temurin 21 (`tools/jdk/`) — le JDK système n'a pas `javac` (D10)
- [x] Outils x86_64 (aapt2, zipalign) exécutés via qemu-user-static + wrappers (D9)
- [x] `scripts/build.sh` : build APK debug de bout en bout
- [x] **APK produit : `dist/app-debug.apk`** — contenu vérifié
      (badging, libs natives, archives Python Chaquopy)
- [x] Wheels Rust : pydantic_core, jiter, uuid_utils, orjson, rpds_py,
      msgspec (setuptools), **typst** — 7 wheels `android_24_arm64_v8a`
- [x] Purge cache WebView par versionCode (D13) — `version_code` auto-incrémenté
- [x] Recherche web `embedded-searxng` validée de bout en bout (HTTP → SearXNG)
- [x] Dictée native (shim SpeechRecognition + relances + arbitrage micro)
- [x] Outil `compile_typst` (.typ → PDF) embarqué (D14)

## Phase 4 — Test appareil

- [x] Installation sur téléphone/tablette (`adb install` ou fichier) — v0.0.60 installée et validée
- [x] Premier lancement : compte admin actif, modèle distant (API OpenAI-compatible) connecté
- [~] Vérifier : chat en streaming ✓ (validé ×10), upload de fichier ✓ (API + gestionnaire),
      micro (dictée) ⏳ manuel, coupure réseau ⏳ manuel
- [ ] Tenue en arrière-plan (foreground service), relance après reboot — ⏳ manuel
- [~] Mesurer taille APK (235,7 Mo ✓), RAM ⏳ manuel, temps de démarrage (import serveur ~1 s ;
      1er lancement plus lent : extraction des assets)

## Phase 5 — Finition

- [ ] APK release signé (keystore dédié, consigné au journal)
- [x] `README.md` : prérequis, build, installation, configuration serveur LLM
- [ ] Notice de licence BSD-3 d'Open WebUI incluse dans l'app
- [ ] Nettoyage : `git tag` de la version livrée
- [x] Garde de cohérence version/tag (P93) : `scripts/verifier_tag.py` avant
      chaque tag + contrôle 9 de `scripts/check_apk.py` à la construction
      (testé localement : positif 0.0.44 / négatif 0.0.43 embarrassés au choix
      de la voie `env` ou `git describe`)

## Idées / hors périmètre pour l'instant

- [x] **SearXNG embarqué** — fait : vendor figé `a30b2d4749` (pré-curl_cffi),
      `msgspec` cross-buildé, provider **`embedded-searxng`** (P9/P10), instance
      locale `127.0.0.1:8888`, moteur de recherche web par défaut.
- [ ] SearXNG « voie B » : documenter un SearXNG distant comme alternative
- [ ] Mode « Connecter à un serveur » en plus du mode local (comme SprintGPT)
- [ ] Mise à jour in-app de l'APK via GitHub Releases
- [ ] Widget Android « nouveau chat »
- [x] Journaux d'activité dans /fm (P94) : consultation + téléchargement
      (fichier / zip), journal `execute_code` avec stderr sur échec — testé
      (module 12/12, routes réelles harnais 8090, rendu mobile capturé)
- [x] Audit de divergence amont + minimisation (v0.0.46) : builtin.py 249→223
      lignes (P41/P94 externalisés dans android_tools), script
      `scripts/audit_divergence.py` reproductible — testé (7/7 reprise, 12/12
      journaux, harnais live/désactivation)
- [x] execute_code : reprise « Client session disconnected » branchée (P95) +
      paramètre timeout fonctionnel — testé (3ᵉ essai réussi après 2 déconnexions)
- [x] Sidebar `/fm` responsive (P124) : tiroir hors-canvas ≤600 px + bouton
      `#side-open`, tablette (601-820 px) en colonne d'icônes, desktop inchangé
      — testé (sonde Playwright 3 paliers, ouverture/fermeture au voile,
      aucun débordement)
- [x] Icônes et style des pages `/fm` calqués sur Open WebUI (P125) : 23 entités
      d'émojis → icônes SVG du sprite OWUI (`_fm_deco`), 3 exceptions
      `@@ICO:nom@@`, style boutons/fields/checkbox OWUI, `word-break`, palier
      ≤480 px — testé (sonde 4 pages × 2 thèmes : 0 émoji dans le DOM,
      style conforme, control P125 réactif sur 8 sabotages)
