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
- [x] Toggles des outils web/code respectés (P126) : P18 révoqué (gate amont
      restauré, icône du composeur respectée) + P28 amendé (compile_typst conditionné
      par le toggle « Outils ») — testé (sonde p126_gate_test sur
      get_builtin_tools réel : 6 scénarios conformes, non-régression /fm
      P124+P125 verte)
- [~] Audio local complet (P127-P130) : messages clairs transcription (P127),
      TTS natif Android via shim speechSynthesis (P128), fin de pydub avec
      découpage wave/mp3 pur Python (P129), découpage MediaExtractor/MediaMuxer
      par pont Java (P130) — sondes hôtes P127/P129 et Playwright P128 vertes ;
      EN ATTENTE : test appareil de l'APK 0.0.78 avant commit/push
- [x] P131 : options « Transformers (Local) » et « Whisper (Local) » masquées
      dans Réglages → Audio (disabled + hidden) — validé (chunk régénéré +
      test Playwright du masquage <option>) ; en attente du build final
- [x] P132 : options RAG mortes masquées (embedding/rerank « SentenceTransformers »,
      découpage « Transformers ») — validé (marqueurs + check_patches + tests)
- [x] Release v0.0.78 (tag → CI GitHub) : publiée (run 44186005320),
      release effacée puis RÉGÉNÉRÉE après P133/P134 (tag repris sur 76f9e1d,
      run 44196145477 success, 2 APK)
- [x] P133 : dictée — plus d'erreur « client » (relance ERROR_CLIENT, codes
      explicites, message lisible, langue non forcée) + diagnostic TTS — validé
      (p133_speech_test)
- [x] P134 : mode d'interaction vocale utilisable en STT local (3 refus
      neutralisés, transcription locale, vrai micro) — validé (p134_call_test)
- [x] P135/P136 : lecture à voix haute et réponses d'appel JAMAIS lues — verrou
      d'initialisation du synthétiseur levé (`voicesJson()` initialise +
      file `initDone`, champs `volatile`, voix par défaut) et boucle d'attente
      des voix bornée (lecture forcée > 5 s, garde-fous 15 s) — validé
      (p136_tts_wait_test + non-régression p128/p133/p134/p127_p129) ;
      EN ATTENTE : test appareil de l'APK (Java non compilable localement)
- [x] Régénération v0.0.78 (release effacée, tag repris → CI) : run
      44196145477 success — 2 APK régénérés depuis 76f9e1d (P133/P134)
- [x] Régénération v0.0.78 (2ᵉ cycle, sur demande « crée une version 0.0.78 ») :
      tag repris sur `eb20a20` (P135/P136), run 44257851519 success —
      release publiée avec les 2 APK régénérés
- [x] P137 : mode vocal — la 2ᵉ réponse d'un chat (et tout message après
      interruption) n'était jamais lue : boucle `nt` terminée et non
      relancée par `ct` — marqueur `ntSig` + drapeau `bt` effacé + relance
      à chaque génération — validé (sonde p137 sur le code livré : 4
      scénarios) ; EN ATTENTE : test appareil
- [x] P138 : messages d'erreur distincts — micro refusé (libellé amont
      conservé + `return`) vs init Kokoro en échec (`Kokoro TTS: …` toast +
      console, appel ouvert quand même) ; init de la file de lecture TTS
      interceptée (fin du rejet silencieux) — validé (sonde p138_p139 :
      15 contrôles) ; EN ATTENTE : test appareil
- [x] P139 : « Default » inutilisable → le default devient Kokoro (sonde de
      voix 2 s, forçage `browser-kokoro` + q8 + af_heart, `defaultVoice`
      aligné sur `config.voice`, normalisation synchrone si kokoro déjà
      choisi) dans les deux chargeurs de `$settings` — validé (sonde
      p138_p139 : 14 contrôles × 2 fichiers) ; EN ATTENTE : test appareil
- [x] Régénération v0.0.78 (3ᵉ cycle, validation « regenere 0.0.78 ») :
      tag repris sur `527529d` (P138/P139), run 44410135285 success —
      release publiée avec les 2 APK régénérés (22:21:52Z)
- [ ] Test appareil v0.0.78 (APK du 2026-11-18, avec P135/P136/P137) : dictée
      (plus d'erreur « client »), mode vocal (bouton « Voice mode » visible,
      énoncé transcrit localement → message dans le chat *derrière* l'overlay ;
      l'overlay n'affiche que statuts et avatar), **génération audio** à
      voix haute à chaque réponse (P135/P136/P137) + toast si aucun moteur TTS
- [ ] Test appareil P138/P139 (après régénération validée) : en échec Kokoro
      le toast doit dire `Kokoro TTS: …` (plus jamais « Accès aux appareils
      multimédias refusé »), micro refusé = message amont exact ; sans voix
      système, « Default » doit parler en Kokoro (af_heart, q8) ; journaux
      activés par l'utilisateur = preuve de la bonne traçabilité
