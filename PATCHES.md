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
| **P108** | `tools/android_tools.py` + `tools/builtin.py` | les fichiers produits par le bac à sable sont **enregistrés** (stockage + base : visibles au gestionnaire `/fm`, `display_file`, API fichiers) et les avertissements FS bénins (`FS.syncfs operations in flight`) ne font plus basculer le statut à `error` | le ramassage P41 écrivait le fichier sur disque sans créer de fiche : invisible au gestionnaire (qui liste la base) ; et `echec = bool(stderr)` traitait le moindre warning comme un échec — chaque réussite affichait `status: error` — journal v0.0.60 |
| **P109** | `android_fm.py` (gabarit `/fm`) + `android_main.py` | refonte du gestionnaire : sidebar **permanente** avec arbre Fichiers (tous, PDF, Images, Typst, Markdown, Autres) au niveau de Paramètres, filtre d'origine **base / disque / les deux**, bouton de retour fixe en **haut à droite**, retours inutiles supprimés ; écran Paramètres en **2 onglets** (OpenWebUI \| SearXNG) avec point vert/rouge d'état, champ service (démarrer/arrêter/redémarrer) puis réglages utiles (SearXNG : formats, limiter, clé) — journal v0.0.61 |
| **P110** | `android_fm.py` + `index.html` | cohérence des écrans Paramètres (largeur commune `.settings`, boutons alignés, cases à cocher `.chk` alignées) ; **plus de clé secrète** ni de génération pour l'instance SearXNG locale ; Maintenance et Journaux en **onglets sous Paramètres** (barre commune Open WebUI \| SearXNG \| Maintenance \| Journaux, points d'état conservés) ; bouton bleu de bascule /fm ↔ Open WebUI **au même endroit sur les deux écrans, déplaçable et synchronisé** (clé partagée `fabPos`) — journal v0.0.62 |
| **P111** | `android_fm.py` + `android_logs.py` | écran Journaux : vue **fusionnée** de tous les journaux (notation « fichier \| ligne », comme le flux live, 300 lignes/fichier — le plus généreux), **suivi automatique** (rafraîchissement 3 s, calage sur les dernières lignes, barre de défilement en bas) ; **journalisation désactivée par défaut** (case « désactiver » pré-cochée par défaut off, effet immédiat + mémorisé `OWUI_LOGS`) ; **évacuation réseau désactivable** (`OWUI_LOGS_NET`, téléchargement/zip/flux live fermés) ; bouton Live retiré de l'interface (route conservée) — journal v0.0.63 |
| **P112** | `android_fm.py` | l'onglet **Journaux** est l'unique entrée (activer la journalisation + visualiser) — le lien « Consulter les journaux » de l'onglet Open WebUI est retiré (redondant) ; contrôle P94 recentré sur l'onglet | journal v0.0.64 |
| **P113** | `android_fm.py` | l'onglet **Journaux** est TOUJOURS visible (côté sidebar et barre d'onglets) et l'écran s'affiche même avec la journalisation coupée | avec la journalisation off par défaut (P111), l'onglet était masqué par `_journaux_actifs()` → impossibilité de réactiver la journalisation depuis l'UI (œuf et poule) — journal v0.0.65 |
| **P114** | `android_fm.py` | correction de la bascule de journalisation : `os.environ` → `_osj.environ` (l'alias du module) | la route `/fm/logs/toggle` levait `NameError` (le module n'importe `os` que sous l'alias `_osj`) → « Internal Error » à l'activation des journaux — journal v0.0.66 |
| **P115** | `android_fm.py` | la bascule de journalisation utilise `_Redirect` (alias réel du module) | la route `/fm/logs/toggle` appelait `_Red`, alias local d'une autre route — `NameError` → 500 à chaque basculement (2ᵉ cause après P114) — journal v0.0.67 |
| **P116** | `android_fm.py` | écran Journaux : **boutons** ▶ Activer / ⏹ Désactiver (logs + évacuation réseau) au lieu des cases à cocher, avec état visible (points vert/rouge) | préférence utilisateur — cohérent avec le champ Service (boutons, même style) — journal v0.0.68 |
| **P117** | `android_fm.py` | carte Journalisation en **deux colonnes séparées verticalement** (Logs fichier \| Logs réseau) ; « Vider » possible **même sans journalisation** ; erreurs en **modale** (popup) sans changement de page (`fmPost`/`fmErr`) ; `OWUI_LOGS`/`OWUI_LOGS_NET` **invisibles** dans les réglages Open WebUI (gérés par l'onglet Journaux, transparents) — journal v0.0.69 |
| **P118** | `android_fm.py` | colonnes « Logs fichier » / « Logs réseau » de **taille égale** (grille `1fr \| filet \| 1fr`) et **espace sous chaque carte** (séparation visuelle renforcée) | retours de mise en page — journal v0.0.70 |
| **P119** | `android_fm.py` | **sidebar rétractable façon Open WebUI sur mobile** : la barre latérale devient un tiroir hors-canvas piloté par un bouton ☰ (voile d'assombrissement, fermeture au clic) au lieu d'être empilée au-dessus du contenu ; onglets sur **une seule ligne défilante** avec auto-centrage de l'onglet actif ; suppression du marqueur orphelin `@@OWUI_LOGS@@` resté dans les réglages Open WebUI (P117) ; cases à cocher **réalignées** avec leur libellé (les règles `.card label`/`.card input` les cassaient) — journal v0.0.71 |
| **P120** | `android_fm.py` | **sidebar /fm calquée sur celle d'Open WebUI** — relevée dans le frontend compilé (`src-assets`) : bouton `#sidebar-toggle-button` en tête (icône panneau, `rounded-lg`, hover gris), largeur `--sidebar-width` **245 px** (bornes **220–480**) redimensionnable par la poignée `#sidebar-resizer` (drag + flèches ←/→ ±10 px, `localStorage.sidebarWidth`), état visible persisté (`localStorage.sidebar`, mobile fermé par défaut), items `rounded-xl px-2 py-1.5` avec sélection translucide, bordures `gray-200`/`gray-800` ; **harmonisation du reste des pages /fm** sur la palette gray d'Open WebUI (50→900), ses rayons (`lg .5rem · xl .75rem · 2xl 1rem`) et son placeholder `#b4b4b4` — journal v0.0.72 |
| **P121** | `android_fm.py` | **rétraction de la sidebar en icônes seules + icônes Open WebUI** — suppression du bouton ☰ (`#sidebtn` : CSS, HTML et JS retirés) et de `body.sidehide` ; nouvel état `body.sideicons` : largeur **56 px**, libellés masqués (`.sl`), icônes centrées (`.si`), poignée de redimensionnement masquée, groupes `details` forcés ouverts (clic sur le titre neutralisé), tooltip `title` sur chaque entrée, bouton de repli qui bascule le titre (« Réduire en icônes » / « Agrandir la sidebar ») ; **13 icônes SVG reprises du sprite du frontend Open WebUI** (`immutable/chunks/wN8N8j40.js` : `folder, list, pdf-logo, image, code, markdown-logo, package, settings, brain, search, tools, page-text, sidebar-expand`, viewBox 24 stroke 1.5) remplacent les émojis ; structure `<span class="si">icône</span><span class="sl">libellé</span>` ; mobile : **colonne d'icônes permanente de 56 px** (le contenu est décalé de 68 px, padding haut 58 px conservé pour dégager le FAB), mode plein en overlay avec voile, retour aux icônes au clic sur le voile ; persistance `localStorage.sidebar = icons|full` (desktop) — mobile démarre toujours en icônes — journal v0.0.73 |
| **P122** | `android_fm.py` | **pied de page dégagé de la colonne en mode icônes** — « OpenWebUI Android x.y.z » (`.ver`, calé à `left:10px`) débordait sous/sur la colonne rétractée de 56 px ; en `body.sideicons` il passe à `left:66px` (56 + 10 de marge) avec la même transition `.18s` que la sidebar — mobile inchangé (déjà `66px`, masqué ≤480 px) — journal v0.0.74 |
| **P123** | `prepare_src.py` + `src-assets/frontend/index.html` | **icône du bouton flottant /fm : le trombone 📎 devient un SVG dessiné « fichier + roue crante »** (document à pli + 3 lignes, engrenage 8 dents en bas à droite sur disque de fond `#3b82f6`, viewBox 24, trait 1.5, `currentColor`, 22 px dans le disque de 42 px) ; titre du bouton : « Fichiers et paramètres de l'application — glisser pour déplacer » — le sprite amont (`wN8N8j40.js`) ne contient ni `paperclip` ni `gear` parmi ses 123 noms, l'icône est donc **dessinée** et non extraite ; contrôle `check_patches.py` : émoji `&#128206;` interdit + `<svg stroke-width="1.5">` exigé près de `#fab-spa` — journal v0.0.75 |
| **P124** | `android_fm.py` | **sidebar /fm responsive aux trois paliers** — téléphone **≤600 px** : plus de colonne permanente, la sidebar devient un tiroir hors-canvas (`translateX(-100%)` + `visibility:hidden`) ouvert par le nouveau bouton `#side-open` (icône `sidebar-expand`, haut à gauche) via le voile `.sideov.on ~ .wrap .side` (sélecteur `~`, le bouton étant inséré entre `.sideov` et `.wrap`) ; toggle et poignée de redimensionnement masqués ; tablette **601–820 px** inchangée (colonne d'icônes 56 px) ; desktop **≥821 px** inchangé (sidebar 245 px + resizer) — journal v0.0.76 |
| **P125** | `prepare_src.py` (`android_fm.py`) | **icônes et style des pages /fm calqués sur Open WebUI** — (a) les **23 entités d'émojis** des pages (`&#9654;` ▶, `&#9208;` ⏹, `&#8635;` ↺, `&#9888;` ⚠, `&#9989;` ✅, `&#9881;` ⚙, 🔌 🔍 💾 🤖 📑 🔒 🔧 📝 📷 📄 🌐 📥 🗅 🛠 📦 💬 + sélecteur de variation `&#65039;` supprimé) deviennent des **icônes SVG du sprite OWUI** (`play, stop, refresh, info, check, settings, plug, search, save, spark, database-script, lock, code, page-text, clock, list, globe, download, trash, tools, package, chat-bubble`) par le décorateur `_fm_deco()` appliqué **une fois sur le document complet** de `_fm_page` (contrôle préalable : 43 entités, **0 dans un attribut**, 0 dans le CSS/JS) ; 3 exceptions par placeholder `@@ICO:nom@@` (Fichiers journaux → `folder`, Index des documents → `grid`, Nettoyer l'index → `refresh`) ; 16 icônes ajoutées au dictionnaire `_FM_ICONS` (29 en tout) ; (b) **style OWUI** : boutons 28 px / 10 px de gouttière / 12 px / graisse 400 / `rounded-lg` en `inline-flex` (icône + libellé alignés, `vertical-align: middle`), secondaire **blanc + bordure** (`.ghost`, `.btn2`), champs 6×8 px / 11 px / sans contour de focus / bordure **blue-400** à l'activation, `textarea` idem, cases à cocher **règle OWUI** (14 px, `appearance:none`, radius .25rem, bleu 600 cochée, coche SVG blanche en `:after`), `html{word-break:break-word}`, palier **≤480 px** : boutons à 34 px de haut — journal v0.0.76 |
