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
- [x] P140 : Kokoro « no available backend » — P13 supprimait `wasm/`
      (ONNX Runtime Web, 21 Mo) alors que le worker Kokoro force
      `wasmPaths="/wasm/"` → `slim_frontend` ne supprime plus que les source
      maps, garde-fou `check_wasm_ort` — validé (check_patches + sonde
      p138_p139) ; EN ATTENTE : test appareil
- [x] P141 : mode vocal — aucun énoncé dans le chat : le MediaRecorder du
      mode vocal monopolisait le micro (conflit documenté par le shim de
      dictée) pendant la reconnaissance → MediaRecorder déporté sur un flux
      silencieux en STT local (VAD + SpeechRecognizer gardent le micro),
      garde « blob < 100 o » réservée au serveur, repli sur résultats
      partiels, traces `Call STT:` — validé (sonde p141 : 20 contrôles) ;
      test appareil : toast `Call STT: transcription vide` = la chaîne est
      atteinte mais le recognizer reste sourd
- [x] P142 : suite P141 — l'analyseur WebAudio du VAD tient aussi le micro
      (capture concurrente) → micro libéré à l'ouverture de l'énoncé (pistes
      stoppées, `z` réinitialisé), « parole continue » pilotée par l'activité
      du recognizer (`__callVadHit`, < 800 ms), toast avec la dernière erreur
      moteur (`moteur : no-speech`) — validé (sonde p142 : 11 contrôles) ;
      test appareil : `moteur : no-speech` = démarrage froid du recognizer
- [x] P143 : démarrage froid — préchauffage `warm()` à l'ouverture de l'appel,
      grâce d'activité 2,5 s + prêt du moteur, télémétrie du toast (code
      erreur + latence), console JS captée dans `data/logs/exec.log`
      (lisible à distance via `/fm/logs/tail`) — validé (sonde p143 :
      10 contrôles) ; EN ATTENTE : test appareil
- [x] P144 : mode vocal — début de phrase tronqué → écoute PERMANENTE du
      recognizer (`warm()` dès l'ouverture), énoncés découpés par marqueurs
      (`mark()` garde l'hypothèse en cours), micro réel réservé au
      recognizer (VAD + MediaRecorder sur flux silencieux), silenciation TTS
      à chaque image, `stop()` à la fermeture — validé (sonde p144 : 5
      contrôles) ; test appareil : « ok ca fonctionne »
- [ ] P145 : bip de « tiling » (canal notification du service de
      reconnaissance) → mute `STREAM_NOTIFICATION` pendant les cycles
      `start()`/`stop()` (pont Java), dé-mute différé 800 ms annulable +
      garde-fous `onDestroy`/`restartApp` — validé (check_patches, Java
      relu) ; EN ATTENTE : test appareil (aucun `javac` local)
- [ ] P146 : « la conversation continue toute seule » (résultats tardifs du
      recognizer après la lecture TTS) → fenêtre de grâce 2,5 s armée par
      `__callSpeechGate` (branchée à `onresult`/`__callVadHit`/`onstart`/
      `mark`), `stop()` la réinitialise — validé (sonde p146 : 9 scénarios
      device) ; EN ATTENTE : test appareil
- [ ] P147 : toast « aucun son entendu » alors que le silence est normal →
      `no-speech`/`aborted`/`aucun résultat` en console seulement, vraies
      erreurs moteur toujours toastées — validé (check_patches + sonde
      p141 : 4 scénarios P147) ; EN ATTENTE : test appareil
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

## Migration Open WebUI 0.13.0 → 0.13.4 (v0.0.79_beta)

- [x] Bascule de version : `scripts/fetch_src.sh` `OPEN_WEBUI_VERSION=0.13.4`
      (le CI lit la version à cet endroit → bascule locale+CI en un fichier)
- [x] Wheel PyPI 0.13.4 vérifié (200, `py3-none-any`, cap `<3.13` identique)
      + `vendor/unpacked/` réextrait
- [x] Relocalisation des 5 chunks hashés (minification renommée) :
      `BeEbX_lw`→`BnHPywC-`, `DRZDe0Yd`→`AZSCJQb3`, `2.DwSK4ZlF`→`2.Dki0jDRo`,
      `55.s0_1KP7y`→`56.DyQrwVL7`, `wN8N8j40`→`wCZlPA5v`
- [x] `prepare_src.py` : **153 opérations, 0 échec** (fix `Pk` P46c/P107 inclus)
- [x] `check_patches.py` : 25 contrôles réalignés sur les motifs 0.13.4
      (faux positifs — justification au journal 2026-11-20) + P148 — **0 erreur**
- [x] Audit tolérant : 133 patchs appliqués / 0 échec
- [x] `node --check` : polyfills + worker + `BnHPywC-.js` verts
- [x] `javac` 25 (android.jar API 34) : `AndroidSpeech`/`AndroidTTS`/
      `AndroidAudio` **0 erreur** (1ʳᵉ validation locale du Java P145)
- [x] Sonde globale `probe_migration_0134.py` : **74/74 verts**
- [x] P148 : `encode_basic_auth` (aiohttp ≥ 3.11 requis, pin 3.10.10
      `[PIN-REPO]` conservé) → repli `BasicAuth.encode()` RFC 7617 vérifié ;
      découvert par le smoke test 8090 (`ImportError` au chargement)
- [x] Smoke test **8090** : `/`, `/health`, `/api/config`, `/api/version`,
      `/favicon.ico`, SearXNG 8888 → 200, aucun traceback, ports/processus
      libérés
- [x] Doc : `PATCHES.md` (+P148, chunks renommés), `maintenance.typ`
      (procédure de mise à jour réécrite en 11 étapes + P148) et `audio.typ`
      (chunks) — PDFs recompilés 0 warning
- [x] Livrer **0.0.79_beta** : `versionName`, commit `180d183`, push `origin master`,
      tag `v0.0.79_beta` poussé nommément (jamais `--tags`), CI run 44705257612 **success** — release + 2 APK publiés
- [x] **P149 — fournisseur realtime « android »** (boucle vocale locale,
      demandé « au plus proche du code initial ») :
      - [x] `prepare_src.py` : `patch_realtime_android()` — **12 opérations**
        (template `Co` à 3 options, 3ᵉ option `android`, bifurcation
        `provider!=="android"`→`current`, 7 champs cloud désactivés par le
        flag, `Literal` + garde `realtime_call`) — **163 opérations, 0 échec**
      - [x] `check_patches.py` : `check_realtime_android()` (template,
        option, libellé, 4+1+2 champs désactivés, bifurcation, Literal,
        garde) — **0 erreur**
      - [x] `probe_migration_0134.py` : **74/74** (javac inclus)
      - [x] smoke **8090** : serveur vert, frontend servi avec les patchs
      - [x] harnais **CDP Chromium** (profil neuf, cache désactivé) :
        dropdown 3 options + libellés, 7 champs actifs (baseline), 7
        désactivés + Provider actif après « Android », **tout réactivé** au
        retour « OpenAI »
      - [x] backend réel : `Literal` accepte android (autre rejeté),
        persistance `config/update` + relecture, **garde WS** avec message
        clair `handled locally on Android`
      - [x] retours appareil corrigés : template **dédié `CoA`** (le `Co`
        partagé ajoutait une 3ᵉ option vide dans Call mode), **masquage**
        des 7 champs (au lieu de la désactivation), **`provider` exposé par
        `/api/config`** (sinon la bifurcation choisissait « bridge » → WS
        ouvert → garde) — revalidé : clic « Voice mode » sans aucune
        requête WS + overlay Listening ;
      - [x] retour appareil 2 : masquage absent **au montage** (ni labels ni
        inputs au 1ᵉʳ passage de l'effet, aucun retry) → retry borné à 40
        frames tant que 6 conteneurs ne sont pas traités — validé : 7 champs
        masqués + réactivité ;
      - [x] **P150** : la dictée pendant l'appel — pause du recognizer de l'appel
        (`pauseForDictation`) à l'ouverture de la dictée, réécoute en fin
        normale/annulation ; contrôle `check_appel_pause_dictation` ;
      - [x] **même bug de store sur le micro** (P141a/P144b) : les conditions de flux
        silencieux lisaient `$settings` seul → vrai micro pris → recognizer sourd →
        transcriptions `local -> vide` → **rien dans le chat** ; les deux stores partout
        (0 occurrence seule restante) ;
      - [x] **audit de fidélité** aux sources v0.13.4 (clonées) :39 insertions sans
        aucune ligne amont modifiée,8 réécritures nécessaires, stores vérifiés —
        `_w` (P141b) corrigé pour lire `$config || $settings` (style VoiceRecording) ;
      - [x] garde P139 (préexistant, bloquait le banc) : `snap()` sur store non
        prêt + `try/catch` du `tick` (setTimeout hors de l'IIFE) — sans elle,
        `/admin/settings` renvoyait vers `/` ;      - [x] message de transcription en mode appel (Bug B) : la fin d'enregistrement
        de l'appel envoyait l'artefact vers l'API quand la dictée locale était
        absente (moteur `web`) → garde `Call STT: énoncé d'appel ignoré` (chemin
        amont intact hors `web`) ; `patch_realtime_android()` déplacé APRÈS les
        patchs d'appel (motif créé par P141b) — *confirmation appareil en attente* ;
      - [x] piège corrigé en route : template à 2 options →
        `Illegal invocation` au montage (détecté uniquement en Chromium)
      - [x] `PATCHES.md` (+P149, ligne P134 corrigée) et `journal.md`
- [x] Livraison **0.0.79_beta remplaçante** (tag forcé, décision utilisateur) :
      `maintenance.typ` + `audio.typ` (+ PDF, grammaire, 0 warning), commit
      `7c200f1`, `push origin master`, tag `v0.0.79_beta` forcé `75579e4`→`7c200f1`
      + poussé nommément, release remplacée (titre + note P149 + 2 APK), CI
      run 44832951778 **success**
- [ ] Test appareil v0.0.79_beta (avec P149) : choisir « Android » dans
      Réglages → Audio → Voice calls (Realtime), vérifier le désactivage des
      champs, enregistrer, puis appuyer sur le bouton d'appel → la boucle
      locale doit démarrer (dictée + réponses lues, **sans** WebSocket)
- [ ] Test appareil v0.0.79_beta : migration 0.13.4 + P148 (login OAuth si
      configuré) + rétroactions ouvertes P145 (bip tiling), P146 (relance
      conversation), P147 (faux « aucun son »)
- [x] Montée amont v0.13.5 (P152) sous le tag *v0.0.81_beta* conservé :
      5 patchs régénérés, `asyncssh==2.23.0`, repli `aiohttp.ClientHandlerType`,
      45 patchs appliqués / 0 échec, imports et P124/P126/P151 verts,
      `check_apk.py` étendu, journal + `maintenance.typ`/PDF mis à jour
- [x] Correction P153 : `PermissionError` sur `/tmp/open-webui-…` au démarrage
      (amont v0.13.5) — `managed.py` suit désormais `TMPDIR`, sonde dédiée,
      `check_apk.py` étendu, 46 patchs / 0 échec
- [x] Correction P154 : « OpenAI: Network Problem » (amont v0.13.5 :
      `middlewares=` incompatible avec aiohttp 3.10 épinglé) — helper
      `client_session_kwargs()`, 47 patchs / 0 échec, test du provider factice
      sur 8090, P124/P126/P151/P153 verts
- [x] P155 : `/fm` → SearXNG en deux sous-onglets (« Service » = page
      actuelle inchangée, « Moteur de recherche » = iframe de
      `http://127.0.0.1:8888/`), paramètre `sub` avec repli sur `service`,
      rappel dans Service du moteur `searxng` et de l'URL de requête à configurer
      dans Open WebUI, 6 cas de `test_p155.py` verts ; `check_apk.py` étendu ;
      livrés ensemble sous `v0.0.81_beta` (CI #45911506476 verte, tag recréé,
      APK vérifiées, `Latest` = `v0.0.80`)
- [x] P156/P157 : lien « Tester la recherche » corrigé vers le service SearXNG
      (`http://127.0.0.1:8888/search?q=test`, l'ancienne route `/search` était
      un 404) ; sous-onglet Moteur réduit à la seule iframe, tout le reste
      regroupé dans Service
- [x] P158 : `embedded-searxng` restauré dans le dropdown « Moteur de recherche
      web » (patch source `09-WebSearch.svelte.patch`, l'ancien P10 ne patchait
      que les chunks précompilés), `test_p158.py` vert, `check_apk.py` étendu
      (faux positif du run 45914805564 corrigé : recherche dans tous les chunks)
- [x] P159/P160 : barre d'onglets de premier niveau supprimée de `/fm`, points
      d'état vert/rouge déplacés dans la liste Paramètres, version `0.0.81`
      mise à jour (`versionName`, pied de page et trace P101), `test_p159.py`
      vert ; livrés en release **stable** `v0.0.81` (CI #45922343958 verte,
      `Latest` = `v0.0.81`, APK vérifiées, signature inchangée)
- [x] R161/R162 : `NameError: onglets` corrigé (placeholder `@@ONGLETS@@`
      retiré du template Open WebUI), bouton « Tester la recherche (SearXNG) »
      supprimé ; huit routes `/fm` rendues sans erreur, garde-fous APK étendus ;
      `v0.0.81` recréé sur `9369888`, CI #45951379812 verte, `Latest` =
      `v0.0.81`, APK vérifiées (`versionCode=26331033`)
- [x] R163 : surlignement Paramètres aligné sur la page rendue (`tab` transmis
      à `_fm_page`), 3 vues vérifiées ; `v0.0.81` recréé sur `d15d3c7`, CI
      #45954723631 verte, `Latest` = `v0.0.81`, APK vérifiées
      (`versionCode=26331035`, marqueur R163 dans le bytecode)
- [x] R164 : alignement amont vérifié (`v0.13.5` = dernier tag et `HEAD`) ; 4
      patchs retirés (changelog copié + 3 changements de mode seuls), 48 → 44
      patchs, reconstruction 44/0/0, 8 tests verts, PDF sans avertissement,
      références `v0.13.4` corrigées ; `v0.0.81` recréé sur `3a80fcc`, CI
      #46071915201 verte, `Latest` = `v0.0.81`, APK vérifiées
      (`versionCode=26331036`, changelog amont embarqué)
- [x] Dette aiohttp soldée en R165 : recompilation croisée réussie (aiohttp
      3.14.5 + 4 dépendances natives), méthode et empreintes dans
      `docs/aiohttp-android.typ`, script `scripts/build-aiohttp-wheels.sh`
- [x] R165 : pins aiohttp remplacés, 4 patchs de compatibilité retirés
      (44 → 41), reconstruction 32/9/0, 9 tests verts, 3 PDF recompilés,
      version relevée en `v0.0.82_beta`
- [x] R165-bis : RECORD des wheels renormalisé (CI #46076329015)
- [x] R165-ter : contrôle dist-info déplacé dans requirements-common.imy
      (CI #46077668862) ; tag recréé, CI #46078600186 verte, APK vérifiées,
      prerelease `v0.0.82_beta` publiée, `v0.0.81` toujours Latest
- [x] P160/P161 : submodules Open Terminal v0.18.8 et proot-distro v5.10.3
      figés, patchs de compatibilité Chaquopy (grp/pwd, watchfiles, version),
      rootfs trixie embarqué, service local 8889 et extraction Java — tests
      locaux en attente de l'artefact rootfs
- [x] P162 : onglets `/fm` Service / Shell root, xterm.js 6.0.0 réel, relais
      HTTP avec clé côté serveur, endpoint resize — test `test_p162.py` vert
- [x] P163 : deux resets distincts (environment conserve work / wipe-work
      supprime work), marqueur consommé au démarrage — test `test_p163.py`
- [ ] Validation matérielle (build release sur appareil) : `proot` depuis les
      assets, `ptrace` autorisé, `pty.openpty()` + `/bin/bash -l` fonctionnels
- [x] Recréer le tag `v0.0.82_ot_beta`, surveiller la CI, vérifier APK et
      prerelease ; CI #46089763471 verte, `v0.0.81` `Latest` et
      `v0.0.82_beta` inchangée
- [x] P164 : relais de reset syntaxiquement valide, addons xterm 6 résolus via
      `ctor()`, pilotage Service seul, Shell root en iframe autonome, restart
      après libération du port — `test_p164.py` et 13 tests verts
- [x] marqueurs P164 exigés dans `android_fm.pyc` par `check_apk.py`
- [x] P165 : entrée Shell root retirée de la sidebar, iframe sans chargement
      différé, démarrage du service à la demande — `test_p165.py` vert
- [x] P166 : une seule session, réutilisation du shell, repli sans PTY sous
      proot, diagnostic journalisé — `test_p166.py` vert, 15 tests verts
- [x] Recréer le tag `v0.0.82_ot_beta` (P166) sur `c8a59cd`, CI #46094209740
      verte, prerelease republiée, APK release et debug vérifiées
- [x] P161 : test dédié aux replis Chaquopy (`grp`/`pwd`, `watchfiles`, version,
      `LD_LIBRARY_PATH`) — vert
- [x] rootfs trixie vérifié (30,9 Mo, SHA-256 au manifest) et xterm.js versionné
- [x] reset `/fm` : appel serveur puis `AndroidSystem.restartApp()`, FitAddon
      relié à `/fm/ot/resize`
- [x] documentation Typst mise à jour et PDF recompilés
- [x] P167 : déplacer `proot`/libs/rootfs dans `getFilesDir()` (volume interne
      exécutable, effacé à la désinstallation), migrer l'ancienne installation,
      supprimer les relances sur `Errno 13` — `test_p167.py` vert
- [x] P167 : tag `v0.0.82_ot_beta` recréé sur `cb7b29c`, CI #46131420884 verte,
      prerelease republiée, APK release et debug vérifiées
- [x] P168 : réappliquer le bit exécutable de `proot` (chemin rapide Java + runner),
      diagnostic honnête errno/mode/racine, retour visuel des boutons de service
      — `test_p168.py` vert, 17 tests verts
- [x] P168 : tag `v0.0.82_ot_beta` recréé sur `2de40d4`, CI #46139047935 verte
      après correction du marqueur P167, prerelease republiée, APK release et
      debug vérifiées
