#import "@preview/ilm:2.1.0": *
#import "helpers.typ": *
#import "@preview/merman:0.3.0": show-mermaid-blocks

#set text(lang: "fr")
#set heading(numbering: "1.1")
#set par(justify: true)
#show figure.where(kind: table): set block(breakable: true)
#show raw.where(lang: "mermaid"): show-mermaid-blocks(
  width: 100%,
  document-context: true,
)

#show: ilm.with(
  title: [Chaîne audio d'Open WebUI Android],
  authors: "Équipe projet openwebui-android",
  date: datetime.today(),
  date-format: "[day padding:none]/[month padding:none]/[year]",
  abstract: [Compte rendu de la chaîne audio de l'application *Open WebUI Android* : dictée vocale, transcription de fichiers audio, génération de parole (TTS) et appels vocaux — comportement *avec les patchs du projet* et *sans patch* (code amont Open WebUI). L'inférence audio n'est jamais locale : elle est soit *native* (moteur vocal d'Android pour la dictée), soit *distante* (API STT/TTS), le portage Android excluant les chaînes lourdes (torch, ctranslate2). État au 18 novembre 2026, version 0.0.78.],
  table-of-contents: outline(title: "Sommaire"),
)

= Objet du document

Ce compte rendu décrit *tout ce qui concerne l'audio* dans l'application :
dictée (micro), transcription de fichiers audio joints, génération de son
(synthèse vocale) et appels vocaux. Pour chaque fonction, deux états sont
décrits : le comportement *sans patch* (Open WebUI amont, tel quel) et le
comportement *avec les patchs du projet* (l'APK livré). Les faits cités
viennent du code généré (`src/open_webui/`), des patchs
(`scripts/prepare_src.py`, `PATCHES.md`) et des tests consignés au
`journal.md`.

= Vue d'ensemble du pipeline

```mermaid
flowchart LR
  subgraph entrees [Entrées audio]
    A[Micro - dictée]
    F[Fichier audio joint]
    C[Appel vocal]
  end
  subgraph traitements [Traitement]
    A --> S[SpeechRecognizer Android natif via shim]
    F --> T[POST /api/v1/audio/transcriptions]
    T --> D{Moteur STT}
    D -->|openai / azure / deepgram / mistral| R[API distante]
    D -->|web| W[Dictée client uniquement]
  end
  subgraph sorties [Sorties audio]
    G[POST /api/v1/audio/speech]
    G --> E{Moteur TTS}
    E -->|openai / elevenlabs / azure / mistral| R2[API distante]
    E -->|transformers| X[HTTP 503 - local indisponible]
  end
  S --> Z[Texte dans la zone de saisie]
  R --> Z
  R2 --> L[Lecture - réponse vocale]
```

Principe directeur du portage : *aucune inférence audio lourde locale* — les
moteurs d'Open WebUI amont (`faster-whisper`, `transformers` + `torch` +
`soundfile`) supposent des bibliothèques C++/Rust inembarquables et sont
retirés des exigences (`requirements-min.txt`). En revanche, les *services
audio du système Android* sont mis à profit (P128, P130) : `SpeechRecognizer`
pour la dictée, `TextToSpeech` pour la voix de synthèse,
`MediaExtractor`/`MediaMuxer` pour le traitement de fichiers. Le résultat est
une chaîne *locale* pour la dictée, la parole et le découpage, et *distante*
uniquement pour la transcription de fichiers (API STT configurée dans
*Réglages → Audio*) — l'inférence du modèle de langage restant elle-même
distante par conception.

= Dictée vocale (micro → texte)

== Avec patch — fonctionnel (dictée native)

La dictée est la fonction audio la plus aboutie de l'APK. Chaîne réelle :

+ l'utilisateur actionne le micro de la zone de saisie ; le frontend appelle
  l'API `SpeechRecognition` du navigateur (mode STT « web » d'Open WebUI) ;
+ un *shim JavaScript* (`SPEECH_POLYFILL`, injecté par `MainActivity.java`)
  remplace `SpeechRecognition` par une passerelle `addJavascriptInterface`
  vers `AndroidSpeech.java`, qui pilote le `SpeechRecognizer` *natif
  d'Android* (reconnaissance vocale du système, souvent utilisable
  hors-ligne) ;
+ le shim respecte le contrat frontend : `onresult` (résultats avec
  `isFinal` et `[0].transcript`), `onend`, `onerror` (codes standard) ;
+ en cas de `NO_MATCH`/`SPEECH_TIMEOUT`, `AndroidSpeech` *relance
  silencieusement l'écoute* (3 essais maximum) avant de conclure ;
+ en cas d'`ERROR_CLIENT` (service de reconnaissance qui redémarre — fréquent
  au tout premier appel ou à une relance trop rapide), l'écoute est *relancée
  après 400 ms* (2 tentatives) au lieu d'afficher l'erreur ; les codes restants
  sont mappés explicitement (trop de demandes, service coupé, langue non
  prise en charge) et renvoyés avec le code Android brut (`{error, code}`) —
  le shim les traduit en libellé lisible (« service de reconnaissance
  indisponible (réessayez) (code 5) ») ; quand le réglage de langue de la
  dictée est vide, *aucune langue n'est forcée* (imposer `Locale.toString()`
  → « fr_FR » faisait échouer les moteurs qui attendent un tag BCP-47) —
  *P133* ;
+ en mode « web », le shim remplace le flux `getUserMedia` audio par un
  *flux silencieux* : le `MediaRecorder` de l'UI monopolisait le micro au
  détriment du `SpeechRecognizer` natif (symptôme « no speech ») — le blob
  enregistré est de toute façon ignoré dans ce mode ; en mode STT distant,
  le flux réel est conservé ;
+ le moteur STT par défaut est fixé à `web` (patch P8 sur `config.py`, plus
  `_force_web_stt`/`AUDIO_STT_ENGINE=web` dans `android_main.py` pour les
  bases déjà semées) ;
+ les permissions Android `RECORD_AUDIO`, `CAMERA` et
  `MODIFY_AUDIO_SETTINGS` sont demandées au lancement (la chaîne audio de
  Chromium échoue sans `MODIFY_AUDIO_SETTINGS`), et `onPermissionRequest`
  n'accorde la capture audio/vidéo que si la permission système est détenue.

*Confidentialité* : la voix dictée est traitée par le moteur vocal du
système Android (constructeur) et ne transite pas par le serveur de
l'application.

== Sans patch — non fonctionnel

Deux blocages indépendants, cumulatifs :

+ *le module audio ne s'importe pas* : `routers/audio/__init__.py` importe
  `pydub` en tête de module, or `pydub` dépend d'`audioop`, retiré de la
  bibliothèque standard en Python 3.13 (la cible du projet) — c'est
  d'ailleurs la raison du cap `Requires-Python < 3.13` d'Open WebUI amont ;
+ *le STT local par défaut est absent* : le moteur `''` appelle
  `faster-whisper` (chaîne C++ `ctranslate2`), non embarquée — symptôme
  réel observé sur appareil (« No module named 'faster_whisper' »).

= Transcription de fichiers audio joints (STT)

== Chaîne de traitement

Un fichier audio joint à une conversation suit le chemin
`routers/files.py` → `transcribe()` → `transcription_handler()` :

+ *prétraitement* (en dehors du mode « bypass ») : vérification du format
  (`mediainfo`), conversion mp3 si besoin, compression, puis découpage en
  morceaux de 20 Mo maximum (`MAX_FILE_SIZE_MB = 20`) ;
+ *transcription* par le moteur configuré (`audio.stt.engine`) : `openai`
  (API compatible Whisper), `deepgram`, `azure`, `mistral` — les morceaux
  sont transcrits en parallèle puis concaténés ;
+ le texte obtenu est indexé (RAG) et transmis au modèle.

== Avec patch — fonctionnel avec un moteur distant

+ `pydub` n'est plus utilisé dans la chaîne (P129) : le fichier est transmis
  tel quel aux API (wav, mp3, m4a, mp4, flac, webm, ogg… acceptés) ;
+ les fichiers de plus de 20 Mo sont *découpés localement* (P129/P130) :
  WAV et MP3 en pur Python (module `wave`, parseur de trames), les autres
  formats via les API Android (`MediaExtractor`/`MediaMuxer`) ;
+ `faster-whisper` / `transformers` / `soundfile+torch` sont mis en
  try/except (patches P7a-c) : un appel à un moteur local renvoie un
  HTTP 503 explicite invitant à configurer un moteur distant — plus de
  `ModuleNotFoundError` brutal ;
+ les moteurs distants utilisables sont donc `openai`, `deepgram`, `azure`
  et `mistral` (clés et URL dans *Réglages → Audio*).

== Sans patch — non fonctionnel

Même blocage d'import (`pydub`/`audioop`) et même absence de
`faster-whisper` : la transcription de fichier, comme la dictée, échoue.

== Point de vigilance identifié et testé (2026-11-17) — corrigé par P127

Avec le moteur par défaut `web`, la transcription d'un *fichier* audio joint
échouait : `transcription_handler()` ne comportait *aucune branche `web`* (ce
mode est purement client, il ne concerne que la dictée) et la route renvoyait
une `TypeError` (HTTP 500) — vérifié par test direct de `transcribe()`.
*Corrigé (P127, v0.0.78)* : la route renvoie désormais un HTTP 400 explicite
(« la dictée native ne transcrit pas les fichiers joints : configurez un
moteur STT distant dans Réglages → Audio »), avec le même type de message
pour un moteur inconnu et pour le STT local absent (503). Pour transcrire
des fichiers audio, configurer un moteur STT distant.

= Génération de parole (TTS) et lecture à voix haute

== Avec patch — fonctionnel avec un moteur distant, et *en local* (P128)

La synthèse vocale passe par `POST /api/v1/audio/speech` (bouton de
lecture des messages, réponses vocales) ou, désormais, par la voix du
téléphone :

+ *synthèse locale (P128, v0.0.78)* : quand aucun moteur TTS serveur n'est
  configuré, le frontend utilise l'API web `speechSynthesis` — un shim
  (`tts_polyfill.js`, pont `AndroidTTS.java` sur le `TextToSpeech` natif)
  prend la main dans la WebView et produit la parole *sur l'appareil*
  (souvent hors-ligne, aucune clé API). Le shim gère file d'attente,
  débit, voix du système, événements start/end/error ;
+ *moteurs distants disponibles* : `openai` (API compatible, modèle
  `tts-1`, voix `alloy` par défaut), `openai-realtime` (OpenAI Realtime),
  `elevenlabs`, `azure`, `mistral` — les réponses sont mises en cache dans
  `SPEECH_CACHE_DIR` ;
+ *moteurs locaux lourds neutralisés* : `transformers`/`soundfile`+`torch`
  renvoient un HTTP 503 explicite (patches P7b-c) ;
+ *sorties TTS exotiques* (P129) : un moteur distant renvoyant du PCM brut
  (cas Gemini via proxy OpenAI-compatible) est *enveloppé en WAV* localement
  (module `wave`, pur Python) et joué par la WebView ; les sorties ogg/flac/
  webm/m4a sont jouées telles quelles ; le vrai encodage MP3 est impossible
  sur la plateforme (ffmpeg absent, aucun encodeur MP3 dans `MediaCodec`)
  mais jamais nécessaire — testé : un WAV est lu même servi en `audio/mpeg` ;
+ l'accès est soumis à la permission `chat.tts` (les administrateurs
  passent toujours) ;
+ *sans moteur configuré* (`audio.tts.engine` vide) : c'est la voix locale
  (P128) qui parle — le réglage par défaut de l'APK.

== Verrou d'initialisation du synthétiseur — corrigé (P135/P136, v0.0.78)

*Symptôme constaté sur appareil* : le mode d'interaction vocale capte et
transcrit l'énoncé, la réponse s'affiche en texte, mais *aucun son n'est
jamais émis* — ni dans l'appel, ni à la lecture d'un message.

*Cause racine (P135, `AndroidTTS.java`)* : l'initialisation du
`TextToSpeech` n'était déclenchée que par `speak()`, alors que `speak()` n'est
atteint qu'après que `getVoices()` renvoie une liste non vide — et
`voicesJson()` renvoyait `"[]"` tant que le moteur n'avait pas été créé. La
boucle d'attente amont (100 ms) tournait donc *indéfiniment* : verrou
silencieux, aucune voix, aucun son, sans message d'erreur. Correctifs :
`voicesJson()` déclenche l'initialisation, les demandes reçues pendant le
démarrage sont mises en file (`initDone`) au lieu de lever une erreur
prématurée, `tts`/`ready` sont `volatile` (lus depuis le thread JavaScript),
et une voix par défaut est fournie si la liste reste vide.

*Garde-fou amont (P136, `BeEbX_lw.js`)* : même avec le moteur correctement
initialisé, la boucle d'attente des voix de l'amont n'avait *aucune borne* :
sans voix, `nt()` — la file de lecture des réponses de l'appel — restait
bloqué sur `await Y(st)` et plus rien n'était lu. Trois micro-remplacements
dans `Y` : horodatage de l'attente, *lecture forcée au-delà de 5 s* (voix par
défaut du moteur), garde-fous 15 s sur la promesse (un `speak()` sans retour
d'événement ne peut plus figer la file).

Le diagnostic P133 (toast « aucun moteur TTS installé sur l'appareil ») n'est
désormais atteint que si le synthétiseur échoue réellement à s'initialiser :
il apparaît au premier usage de la parole, plus jamais masqué par le verrou.

== Sans patch — non fonctionnel

Blocage `pydub`/`audioop` à l'import ; la génération locale suppose
`transformers` + `torch` + `soundfile`, absents de l'APK (et inembarquables
dans le périmètre du projet) : même en débloquant l'import, la synthèse
locale est impossible.

= Appels vocaux (temps réel)

Les appels vocaux *temps réel* (Open WebUI « voice call », fournisseur
`audio.realtime` — OpenAI Realtime API) reposent sur une API distante :
*désactivés par défaut* en amont (`AUDIO_REALTIME_ENABLED = false`), ils ne
sont ni activés ni testés dans l'APK. Ils deviennent envisageables en activant
le réglage et en configurant une API compatible, mais ne font partie d'aucun
scénario validé sur appareil — à traiter comme une piste, pas comme une
fonction livrée.

== Mode d'interaction vocale — fonctionnel en STT local (P134)

À distinguer du temps réel ci-dessus : le *mode d'interaction vocale* du chat
(bouton « Voice mode », overlay avec détection de parole) transcrit chaque
énoncé par l'API serveur `/api/v1/audio/transcriptions`. En amont, ce mode est
*refusé dès que le moteur STT est « web »* (notre défaut, dictée native) :
le bouton n'apparaît pas et l'overlay affiche « Call feature is not supported
when using Web STT engine ». Le build l'apporte ainsi :

+ les *3 refus amont* (affichage du bouton, lancement, ouverture de l'overlay)
  sont neutralisés dans le chunk d'appel (`BeEbX_lw.js`, sept
  micro-remplacements — structure amont intacte) ;
+ la *détection de parole amont* est réutilisée telle quelle : au début de
  l'énoncé, `window.__callDictation.start()` ouvre une écoute
  `SpeechRecognition` *locale* (le même `AndroidSpeech.java` que la dictée) ;
  après 2 s de silence, `hold()` fige l'énoncé et laisse le moteur livrer son
  résultat final ;
+ la *transcription est rendue en local* (`__callDictation.text()` remplace
  l'appel `rb()` → `/api/v1/audio/transcriptions`, qui renverrait 400 en
  moteur « web ») ; les résultats finaux s'accumulent pendant l'énoncé et sont
  relus à la fin ;
+ le mode vocal demande le *vrai micro* (`window.__realMic` → `__origGUM`) :
  le shim de dictée substitue un flux silencieux au `getUserMedia` (pour
  laisser le micro libre au `SpeechRecognizer`), ce qui clouerait la détection
  de parole de l'appel ;
+ un *garde-fou de 30 s* ferme l'écoute : jamais de reconnaissance en boucle
  qui finirait par transcrire la voix de l'assistant.

Le polyfill correspondant (`app/src/main/assets/call_polyfill.js`) est injecté
à chaque page chargée, aux côtés du shim de dictée et du shim TTS.

== Réponses de l'appel : file de lecture — corrigé (P137, v0.0.78)

*Ce que l'overlay affiche* : par conception amont, *aucun texte* — seulement
l'avatar du modèle, le niveau du micro et les statuts (« Listening… »,
« Thinking… », « Tap to interrupt »). La transcription part dans le *vrai
`submitPrompt`* du composeur : elle et la réponse apparaissent dans le chat
*derrière* l'overlay. Le sous-titre central (`V`) ne porte que l'emoji
(`showEmojiInCall`).

*Chaîne de lecture* : `chat:start` / `chat` / `chat:finish` sont dispatchés sur
l'`EventTarget` du layout — le même objet transmis au composant d'appel
(`d7` → `nP` → `H4` → `P4`) — puis `ct` démarre la boucle `nt`, `pt` empile
les segments dans `rt` et `nt` les lit un à un via `Y`
(`speechSynthesis` → shim → `AndroidTTS`).

*Symptôme corrigé* : la réponse était bien générée (les trois points tournent)
mais *rien n'était lu* — ni son, ni sous-titre. Cause : `nt` se *terminait*
(`break`) dès que la réponse était finie et la file vide, alors que `ct`
(`chat:start`, dispatché à chaque génération) ne la relançait que si
l'identifiant de chat *changeait* : le deuxième message d'un même chat — et
tout message après une interruption — s'empilait dans `rt` sans aucun lecteur.

*Correctif (P137, 3 micro-remplacements)* : marqueur de boucle active
(`ntSig`), effacé à la fin du tour ; à chaque génération, `ct` efface le
drapeau « réponse finie » du chat (sinon la boucle relancée se re-arrêtait
aussitôt), relance `nt` si aucun tour n'est associé au signal courant — en
recréant l'`AbortController` si l'ancien a été annulé par une interruption —
et repasse l'état « parle » (`q`) à vrai, sans quoi la détection de parole
resterait active pendant la lecture et le micro capterait la voix de
l'assistant. Le `break` est conservé : aucune boucle orpheline.

*Validation* : sonde `p137_call_playback_test.py` qui rejoue le code
*réellement livré* (`ct`/`pt`/`wt`/`nt`/`Ue`/`Y` extraits du chunk) —
4 scénarios verts : premier message d'un chat neuf, deuxième message du même
chat, changement de chat, reprise après interruption.

= Récapitulatif : avec patch / sans patch

#table(
  columns: (1.1fr, 1.4fr, 1.5fr),
  [*Fonction*], [*Sans patch (amont, Python 3.13)*], [*Avec patch (APK)*],
  [Import du module audio],
  [échec : `pydub` exige `audioop` (retiré de la stdlib en 3.13) —
   blocage d'amorçage],
  [P5 : import optionnel, traitements locaux désactivés avec message clair ;
   l'application démarre],
  [Dictée (micro)],
  [non fonctionnelle : STT local `faster-whisper` absent + blocage d'import],
  [fonctionnelle : `SpeechRecognizer` natif via `AndroidSpeech.java` +
   shim JS (P8, D11), relance silencieuse, arbitrage micro (flux silencieux),
   souvent hors-ligne],
  [Transcription de fichiers joints],
  [non fonctionnelle : même blocages],
  [fonctionnelle avec un STT distant (`openai`, `deepgram`, `azure`,
   `mistral`) ; prétraitement 100 % local sans pydub (P129 : WAV/MP3 découpés
   en pur Python ; P130 : autres formats via MediaExtractor/MediaMuxer) ;
   moteur `web` + fichier → message clair (P127)],
  [Génération de voix (TTS)],
  [non fonctionnelle : `transformers`/`torch`/`soundfile` absents],
  [*locale* par défaut (P128 : `TextToSpeech` natif via le shim
   `speechSynthesis`) ; distante possible (`openai`, `elevenlabs`, `azure`,
   `mistral`) ; local lourd → HTTP 503 explicite (P7b-c) ; permission
   `chat.tts`],
  [Lecture à voix haute],
  [idem TTS],
  [idem TTS — voix du téléphone (P128), hors-ligne ; synthétiseur initialisé
   depuis `getVoices()` et boucle d'attente des voix bornée (P135/P136) :
   la lecture démarre au lieu d'attendre indéfiniment],
  [Appels vocaux],
  [désactivés par défaut],
  [temps réel (`audio.realtime`) : désactivés par défaut ; *mode
   d'interaction vocale* : utilisable en STT local (P134 — 3 refus amont
   neutralisés, transcription locale via `SpeechRecognition`, vrai micro) ;
   chaque réponse lue à voix haute, y compris la deuxième d'un même chat
   (P137) avec la voix locale (P128 + P135/P136) ; dictée sans erreur
   « client » (P133) ; l'overlay n'affiche aucun texte (comportement amont)],
  [Fichiers audio > 20 Mo],
  [découpage par `pydub`],
  [découpage local sans pydub (P129/P130) : WAV/MP3 en pur Python, autres
   formats via les API Android ; hors appareil, message clair],
)

= Points de vigilance et recommandations

+ *Configuration minimale* : la dictée et la voix de synthèse fonctionnent
  *sans aucune configuration* (API Android, P128) ; seule la *transcription
  de fichiers joints* exige un STT distant dans *Réglages → Audio*
  (message clair sinon, P127).
+ *Fichiers > 20 Mo* : découpés localement (P129/P130) — WAV et MP3 en pur
  Python, les autres formats via les API Android ; hors appareil (tests
  hôte), les formats exotiques lèvent un message clair.
+ *Voix du système* : la qualité et la disponibilité hors-ligne dépendent du
  moteur TTS installé sur le téléphone (paramètres Android → Synthèse
  vocale).
+ *Confidentialité* : dictée et synthèse vocale = 100 % local ; la
  transcription de fichiers envoie l'audio à l'API STT choisie.

= Références

#table(
  columns: (1.2fr, 2fr),
  [*Source*], [*Contenu*],
  [`scripts/prepare_src.py`],
  [patchs P5 (`pydub` optionnel), P7a-c (moteurs locaux → 503),
   P8 (`AUDIO_STT_ENGINE=web`), P136 (boucle d'attente des voix bornée dans
   le chunk d'appel), P137 (file de lecture de l'appel relancée à chaque
   réponse)],
  [`app/src/main/java/org/openwebui/android/AndroidSpeech.java`],
  [passerelle `SpeechRecognizer` natif, contrat
   `onresult`/`onend`/`onerror`, relance `NO_MATCH`/`SPEECH_TIMEOUT`, relance
   `ERROR_CLIENT` + codes mappés + payload `{error, code}` (P133)],
  [`app/src/main/java/org/openwebui/android/AndroidTTS.java`],
  [P128 — pont `TextToSpeech` natif (`speak`/`stop`/`voicesJson`,
   événements `__androidTtsEvent`), diagnostic « aucun moteur TTS installé »
   (P133) ; P135 — initialisation paresseuse depuis `voicesJson()` (file
   d'attente `initDone`, champs `volatile`, voix par défaut)],
  [`app/src/main/assets/tts_polyfill.js`],
  [P128 — shim `speechSynthesis`/`SpeechSynthesisUtterance` (file d'attente,
   débit, voix, pause/resume) — `Object.defineProperty` obligatoire
   (attribut en lecture seule dans Chromium)],
  [`app/src/main/assets/call_polyfill.js`],
  [P134 — polyfill du mode d'interaction vocale : `__callDictation`
   (start/hold/text, garde-fou 30 s) et `__realMic` (vrai micro au lieu du
   flux silencieux du shim de dictée)],
  [`app/src/main/java/org/openwebui/android/AndroidAudio.java`],
  [P130 — découpage `MediaExtractor`/`MediaMuxer` sans transcodage
   (sorties m4a/webm)],
  [`app/src/main/python/audio_bridge.py`, `android_main.py`],
  [P130 — pont Java→Python (`register_audio_split`, fonction à un argument
   JSON) enregistré au démarrage du serveur],
  [`app/src/main/java/org/openwebui/android/MainActivity.java`],
  [shim `SPEECH_POLYFILL` (polyfill `SpeechRecognition`, flux silencieux
   `getUserMedia` en mode web, libellés d'erreur lisibles P133,
   `window.__origGUM`), injection des polyfills `tts_polyfill.js` et
   `call_polyfill.js`, permissions micro/caméra],
  [`app/src/main/python/android_main.py`],
  [`AUDIO_STT_ENGINE=web` par défaut (bases déjà semées)],
  [`src/open_webui/routers/audio/__init__.py`],
  [routes `speech`/`transcriptions`, table des moteurs TTS/STT,
   `MAX_FILE_SIZE_MB = 20`],
  [`src/open_webui/config.py`],
  [constantes `AUDIO_STT_*`, `AUDIO_TTS_*`, `AUDIO_REALTIME_*`],
  [`PATCHES.md`, `journal.md`],
  [décision D11 (dictée native), sessions test appareil des 2026-11-06 et
   2026-11-07, tests de transcription du 2026-11-17],
)
