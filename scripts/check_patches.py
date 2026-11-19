#!/usr/bin/env python3
"""check_patches.py — vérifie que les patchs P1–P30 sont correctement appliqués
dans l'arbre généré `src/` (+ build.gradle, + frontend).

Chaque contrôle correspond à un patch réel ; un patch « appliqué » par
prepare_src mais mal placé (ex. compile_typst sans son gate « Outils »,
P28/P126) ou cassé (_os2.sub) est ici détecté.

Usage : python3 scripts/check_patches.py   (appelé en fin de prepare_src + CI)
"""
import pathlib
import py_compile
import re
import sys

PROJ = pathlib.Path(__file__).resolve().parent.parent
SRC = PROJ / "src"
ERREURS: list[str] = []

# (label, fichier, motif exact attendu)
CHECKS = [
    ("P1 VECTOR_DB=local", "open_webui/config.py",
     "VECTOR_DB = os.getenv('VECTOR_DB', 'local')"),
    ("P3 factory local/none", "open_webui/retrieval/vector/factory.py", "'local'"),
    ("P5 pydub/audioop neutralisé", "open_webui/routers/audio/__init__.py", "pydub"),
    ("P9b moteur embedded-searxng", "open_webui/routers/retrieval.py", "embedded-searxng"),
    ("P21 recurrence en thread", "open_webui/utils/recurrence.py",
     "to_thread.run_sync(_next_occurrences"),
    ("P22 journal SearXNG (outil)", "open_webui/tools/builtin.py", "searxng.log"),
    ("P24 version_frozen SearXNG", "searx/version_frozen.py", 'VERSION_STRING = "1.0.0+a30b2d4"'),
    ("P24b version.py tolère OSError", "searx/version.py", "(subprocess.CalledProcessError, OSError)"),
    ("P27 navigateur /fm", "open_webui/android_fm.py", "async def fm_browser("),
    ("P27 aperçu /fm/preview", "open_webui/android_fm.py", "async def fm_preview("),
    ("P27 suppression /fm/delete", "open_webui/android_fm.py", "async def fm_delete("),
    ("P30a alias /mnt/uploads (storage)", "open_webui/storage/provider.py", 'startswith("/mnt/uploads/")'),
    ("P30b alias /mnt/uploads (display_file)", "open_webui/tools/builtin.py", "startswith('/mnt/uploads/')"),
    ("P30c orientation view_note", "open_webui/tools/builtin.py", "utilisez view_note"),
    ("P30 taille/humaine (fm)", "open_webui/android_fm.py", "def _fm_size("),
    ("P31 purge index /fm/delete", "open_webui/android_fm.py", "P31 : purger aussi l'index vectoriel"),
    ("P33 sonde HTTP fetch_url", "open_webui/tools/android_tools.py", "def _probe_fetch_url("),
    ("P36 get_collections LocalVectorDB", "open_webui/retrieval/vector/dbs/local.py", "def get_collections("),
    ("P39a recherche mémoires normalisée", "open_webui/utils/memory.py", "_norm_memory_text"),
    ("P39b auto-réparation index KB", "open_webui/tools/builtin.py", "P39b : réparer l'index sémantique"),
    ("P41c fichiers produits enregistrés", "open_webui/tools/builtin.py", "fichiers_sortie"),
    ("P42a \\n littéraux write_note", "open_webui/tools/builtin.py", "P42 : \\n littéraux"),
    ("P0 import android_tools (builtin)", "open_webui/tools/builtin.py", "from open_webui.tools.android_tools import"),
    ("P45a rrule create_automation", "open_webui/tools/builtin.py", "P45 : \\n littéraux convertis"),
    ("P46a détection paquets serveur", "open_webui/tools/android_tools.py", "_pyodide_packages"),
    ("P48 jetons normalisés", "open_webui/models/knowledge.py", "nom_norm"),
    ("P51 uploads injectés", "open_webui/tools/android_tools.py", "_uploads_pour_sable"),
    ("P52 bootstrap réseau", "open_webui/tools/android_tools.py", "SANDBOX_NET_BOOTSTRAP"),
    ("P84 repli session vivante", "open_webui/socket/main.py", "P84 : session expirée"),
    ("P88 bootstrap sans sonde urlopen", "open_webui/tools/android_tools.py", "renseigné par une sonde JS bornée"),
    ("P88 sonde JS bornée au boot", "open_webui/tools/android_tools.py", "AbortSignal"),
    ("P68 timeout search_web", "open_webui/retrieval/web/searxng.py", "timeout=30"),
    ("P69 delete_file to_thread", "open_webui/tools/android_tools.py", "asyncio.to_thread(Storage.delete_file"),
    ("P69b fm_delete to_thread", "open_webui/android_fm.py", "asyncio.to_thread(Storage.delete_file"),
    ("P51/P77 injection des uploads", "open_webui/tools/android_tools.py", "_uploads_pour_sable"),
    ("P54 fallback contenu KB", "open_webui/tools/builtin.py", "'source': 'content'"),
    ("P57 write_note auto-lecture", "open_webui/tools/builtin.py", "P57 : la note vient d'être écrite"),
    ("P58 list_tools", "open_webui/tools/android_tools.py", "async def list_tools("),
    ("P59 delete_file", "open_webui/tools/android_tools.py", "async def delete_file("),
    ("P65 délai garanti execute_code", "open_webui/tools/builtin.py", "timeout=320"),
    ("P94 module journaux", "open_webui/android_logs.py", "def journal_exec("),
    ("P94 handler fichier journaux", "open_webui/android_logs.py", "class _Handler(logging.Handler)"),
    ("P94 rotation par taille", "open_webui/android_logs.py", "def _rotation("),
    ("P94 journal execute_code (builtin)", "open_webui/tools/builtin.py", "P94 : journal des exécutions"),
    ("P94 capture au démarrage (/fm)", "open_webui/android_fm.py", "_allog.install()"),
    ("P94 page journaux (/fm)", "open_webui/android_fm.py", "if folder == 'logs':"),
    ("P94 téléchargement journaux", "open_webui/android_fm.py", "async def fm_logs_download("),
    ("P94/P111 entrée journaux (onglet, plus le bouton des réglages)", "open_webui/android_fm.py", "folder=logs"),
    ("P95 reprise appel événementiel", "open_webui/tools/android_tools.py", "def appel_avec_reprise("),
    ("P95 reprise branchée (builtin)", "open_webui/tools/builtin.py", "_appel_reprise(__event_call__"),
    ("P95 suite flux live (journaux)", "open_webui/android_logs.py", "def suite("),
    ("P95 route flux live (/fm)", "open_webui/android_fm.py", "async def fm_logs_live("),
    ("P96 create_tool contrainte id", "open_webui/tools/builtin.py", "lowercase letters, digits and underscores ONLY"),
    ("P96 update_calendar start/end", "open_webui/tools/builtin.py", "pass BOTH start and end"),
    ("P96 liste outils publics (sans _)", "open_webui/tools/android_tools.py", "not n.startswith('_')"),
    ("P96 trace entrée execute_code", "open_webui/tools/builtin.py", "DEBUT execute_code"),
    ("P96 trace timeout execute_code", "open_webui/tools/builtin.py", "TIMEOUT 320s"),
    ("P97 trace engine execute_code", "open_webui/tools/builtin.py", "P97 engine="),
    ("P97 trace tentatives event_call", "open_webui/tools/android_tools.py", "P97 event_call essai"),
]


def err(msg: str) -> None:
    ERREURS.append(msg)


def check_fichiers() -> None:
    for label, rel, motif in CHECKS:
        p = SRC / rel
        if not p.exists():
            err(f"{label} : fichier absent — {rel}")
            continue
        if motif not in p.read_text(encoding="utf-8", errors="ignore"):
            err(f"{label} : motif introuvable dans {rel} — « {motif[:60]} »")


def check_audio_locale() -> None:
    """P127/P128/P129/P130 — chaîne audio locale (validation continue).
    Chaque élément est exigé : messages clairs du dispatch STT (P127), pont
    TextToSpeech natif + shim speechSynthesis (P128), prétraitement sans
    pydub (P129), découpage Android MediaExtractor/MediaMuxer (P130).
    """
    audio = SRC / "open_webui" / "routers" / "audio" / "__init__.py"
    if not audio.exists():
        err("P127/P129 : routers/audio/__init__.py absent")
        return
    text = audio.read_text(encoding="utf-8", errors="ignore")
    # P127 — branches web/inconnu explicites + garde-fou STT local absent
    for motif, lib in (
        ("ne transcrit pas les fichiers", "message « web » + fichiers joints"),
        ("Moteur STT inconnu", "message moteur inconnu"),
        ("STT local (faster-whisper) indisponible", "garde-fou STT local absent"),
    ):
        if motif not in text:
            err(f"P127 : motif absent — {lib}")
    # P129 — rendu local fonctionnel de transcode_audio_to_mp3 (PCM → WAV)
    if "PCM enveloppe en WAV" not in text:
        err("P129 : transcode_audio_to_mp3 sans enveloppage WAV local")
    # MINIMALITÉ (demande 2026-11-17) : les fonctions amont doivent rester
    # INTACTES (pydub absent géré par leurs propres try/except) — seul
    # l'appel de découpage est changé et les fonctions locales sont ajoutées.
    for motif, lib in (
        ("def is_audio_conversion_required", "is_audio_conversion_required (amont)"),
        ("mediainfo(file_path)", "mediainfo (amont, try/except interne)"),
        ("AudioSegment.from_file(file_path)", "split_audio/compress_audio (amont, intacts)"),
        ("def split_audio(", "split_audio (amont)"),
    ):
        if motif not in text:
            err(f"minimalité : fonction amont altérée — {lib}")
    if "_split_audio_local, file_path," not in text:
        err("P129/P130 : l'appel de découpage local (_split_audio_local) est absent de transcribe")
    for motif, lib in (
        ("def _split_audio_local", "découpage local"),
        ("def _split_wav_python", "découpage WAV pur Python"),
        ("def _split_mp3_python", "découpage MP3 pur Python"),
        ("def _split_via_android_bridge", "pont Android de découpage"),
    ):
        if motif not in text:
            err(f"P129 : motif absent — {lib}")
    bridge = PROJ / "app" / "src" / "main" / "python" / "audio_bridge.py"
    if not bridge.exists():
        err("P130 : audio_bridge.py absent (pont Python)")
    else:
        bt = bridge.read_text(encoding="utf-8", errors="ignore")
        if "def register_split" not in bt or "def get_split" not in bt:
            err("P130 : API audio_bridge incomplète (register_split/get_split)")
    am = PROJ / "app" / "src" / "main" / "python" / "android_main.py"
    if not am.exists():
        err("P130 : android_main.py absent")
    elif "register_audio_split" not in am.read_text(encoding="utf-8", errors="ignore"):
        err("P130 : register_audio_split absent de android_main.py")
    java_dir = PROJ / "app" / "src" / "main" / "java" / "org" / "openwebui" / "android"
    aud = java_dir / "AndroidAudio.java"
    if not aud.exists():
        err("P130 : AndroidAudio.java absent")
    else:
        at = aud.read_text(encoding="utf-8", errors="ignore")
        if "MediaExtractor" not in at or "MediaMuxer" not in at:
            err("P130 : AndroidAudio.java sans MediaExtractor/MediaMuxer")
    # P128 — pont TextToSpeech + shim speechSynthesis + câblage MainActivity
    tts = java_dir / "AndroidTTS.java"
    if not tts.exists():
        err("P128 : AndroidTTS.java absent")
    else:
        jt = tts.read_text(encoding="utf-8", errors="ignore")
        if "TextToSpeech" not in jt or "__androidTtsEvent" not in jt:
            err("P128 : AndroidTTS.java incomplet (TextToSpeech / __androidTtsEvent)")
    shim = PROJ / "app" / "src" / "main" / "assets" / "tts_polyfill.js"
    if not shim.exists():
        err("P128 : tts_polyfill.js absent (shim speechSynthesis)")
    else:
        st = shim.read_text(encoding="utf-8", errors="ignore")
        for motif in ("Object.defineProperty", "window.AndroidTTS", "__androidTtsEvent"):
            if motif not in st:
                err(f"P128 : shim tts_polyfill.js sans « {motif} »")
    main_java = java_dir / "MainActivity.java"
    if not main_java.exists():
        err("P128/P130 : MainActivity.java absent")
    else:
        mt = main_java.read_text(encoding="utf-8", errors="ignore")
        if "addJavascriptInterface(new AndroidTTS" not in mt:
            err("P128 : AndroidTTS non exposé à la WebView (MainActivity)")
        if "tts_polyfill.js" not in mt:
            err("P128 : shim speechSynthesis non injecté (MainActivity)")
        if "register_audio_split" not in mt:
            err("P130 : pont audio non enregistré (MainActivity)")


    # P131 — options des moteurs locaux morts masquées dans l'UI
    ui = PROJ / "src-assets" / "frontend" / "_app" / "immutable" / "nodes" / "2.DwSK4ZlF.js"
    if not ui.exists():
        err("P131 : chunk des réglages audio absent (2.*.js)")
    else:
        ut = ui.read_text(encoding="utf-8", errors="ignore")
        if "st.disabled=!0,st.hidden=!0" not in ut:
            err("P131 : option TTS « Transformers (Local) » toujours visible")
        if "E.disabled=!0,E.hidden=!0" not in ut:
            err("P131 : option STT « Whisper (Local) » toujours visible")
        # P132 — options RAG mortes masquées (embedding/rerank/découpage)
        for motif, lib in (
            ("j.disabled=!0,j.hidden=!0", "embedding « SentenceTransformers »"),
            ("Nt.disabled=!0,Nt.hidden=!0", "rerank « SentenceTransformers »"),
            ("ht.disabled=!0,ht.hidden=!0", "découpage « Token (Transformers) »"),
        ):
            if motif not in ut:
                err(f"P132 : option RAG « {lib} » toujours visible")


def check_compile_typst_hors_bloc() -> None:
    """P28/P126 : compile_typst doit être conditionné par le toggle « Outils » du
    modèle (ENABLE_TOOLS + is_builtin_tool_enabled('tools')), et rester
    indépendant de la permission de CRÉATION d'outils (workspace.tools).
    Historique : P28 l'avait rendu inconditionnel (v0.0.11, sortie du bloc
    create_tool) — P126 (v0.0.77) lui redonne un gate car l'outil restait
    visible et actif même avec le toggle désactivé. Le contrôle se RENFORCE :
    il exige désormais le gate (avant : il exigeait l'absence de bloc).
    """
    p = SRC / "open_webui" / "utils" / "tools.py"
    text = p.read_text(encoding="utf-8", errors="ignore")
    lignes = text.splitlines()
    reg = [l for l in lignes if "builtin_functions.append(compile_typst)" in l]
    if not reg:
        err("P28 : compile_typst non enregistré dans utils/tools.py")
        return
    if reg[0].startswith("    builtin_functions.append(compile_typst)"):
        err("P28/P126 : compile_typst enregistré SANS gate (inconditionnel) — "
            "il doit suivre le toggle « Outils »")
    elif reg[0].startswith("        builtin_functions.append(compile_typst)"):
        i = lignes.index(reg[0])
        if "is_builtin_tool_enabled('tools')" not in lignes[i - 1]:
            err("P28/P126 : compile_typst conditionné par autre chose que le toggle "
                f"« Outils » — {lignes[i - 1][:60]!r}")
    else:
        err(f"P28 : compile_typst mal placé — {reg[0][:60]!r}")
    # P18 révoqué (P126) : le gate forcé des outils web ne doit pas revenir
    if "if config.get('web.search.enable') and await has_user_permission('web_search'):" in text:
        err("P18 : le gate forcé des outils web est revenu (révoqué en P126)")
    # le gate web amont doit être rétabli (toggles respectés, dont celui
    # du composeur features.web_search)
    if "is_builtin_tool_enabled('web_search')" not in text:
        err("P126 : gate amont des outils web absent (is_builtin_tool_enabled)")
    if "features.get('web_search')" not in text:
        err("P126 : toggle du composeur non respecté (features.get('web_search') absent)")


def check_mode_vocal() -> None:
    """P133/P134 — dictée (erreur « client ») et mode d'interaction vocale."""
    java = PROJ / "app" / "src" / "main" / "java" / "org" / "openwebui" / "android"
    main_j = (java / "MainActivity.java").read_text(encoding="utf-8", errors="ignore")
    speech_j = (java / "AndroidSpeech.java").read_text(encoding="utf-8", errors="ignore")
    tts_j = (java / "AndroidTTS.java").read_text(encoding="utf-8", errors="ignore")

    # P133 — relance sur ERROR_CLIENT (sinon « client » brut affiché au 1er appel)
    if "MAX_CLIENT_RETRIES" not in speech_j:
        err("P133 : relance ERROR_CLIENT absente (AndroidSpeech)")
    if "ERROR_LANGUAGE_NOT_SUPPORTED" not in speech_j:
        err("P133 : codes de langue non mappés (retomberaient sur « client »)")
    if 'o.put("code", code)' not in speech_j:
        err("P133 : code Android brut absent du payload d'erreur")
    if "ERR_FR" not in main_j:
        err("P133 : libellé lisible du code « client » absent du shim")
    if "import java.util.Locale;" in speech_j:
        err("P133 : import Locale inutilisé revenu (langue forcée rétablie)")
    # diagnostic TTS : sans moteur installé, la WebView reste muette sans raison
    if "aucun moteur TTS installé" not in tts_j:
        err("P133 : diagnostic « aucun moteur TTS » absent (AndroidTTS)")

    # P134 — polyfill du mode vocal + injection
    poly = PROJ / "app" / "src" / "main" / "assets" / "call_polyfill.js"
    if not poly.exists():
        err("P134 : assets/call_polyfill.js absent")
    else:
        pt = poly.read_text(encoding="utf-8", errors="ignore")
        for motif in ("__callDictation", "__realMic", "hold:", "text:"):
            if motif not in pt:
                err(f"P134 : call_polyfill.js sans « {motif} »")
    if 'assetJs("call_polyfill.js")' not in main_j:
        err("P134 : call_polyfill.js non injecté (MainActivity)")
    if "window.__origGUM=origGUM" not in main_j:
        err("P134 : accès au vrai micro (__origGUM) absent du shim de dictée")

    # P134 — 7 micro-patchs dans le chunk d'appel
    chunk = PROJ / "src-assets" / "frontend" / "_app" / "immutable" / "chunks" / "BeEbX_lw.js"
    if not chunk.exists():
        err("P134 : chunk d'appel BeEbX_lw.js absent")
        return
    ct = chunk.read_text(encoding="utf-8", errors="ignore")
    # refus amont : leur PRÉSENCE signifierait un retour en arrière
    for motif, lib in (
        ('stt?.engine!=="web"&&(n()', "refus de bouton en STT « web » revenu"),
        ('engine==="web"){$t.error(f().t("Call feature', "refus d'appel (lo) revenu"),
        ('else if(s()?.audio?.stt?.engine==="web")', "refus d'overlay revenu"),
    ):
        if motif in ct:
            err(f"P134 : {lib}")
    # branchements locaux : leur ABSENCE signifierait un retour en arrière
    for motif, lib in (
        ("window.__callDictation.start(", "début d'énoncé non branché"),
        ("window.__callDictation.hold()", "fin d'énoncé non branchée"),
        ("window.__callDictation.text()", "transcription locale non branchée"),
        ("window.__realMic||navigator.mediaDevices.getUserMedia", "vrai micro non branché"),
    ):
        if motif not in ct:
            err(f"P134 : {lib}")


def check_appel_stt_local() -> None:
    """P141 — mode vocal : le SpeechRecognizer doit entendre le micro.

    Le MediaRecorder du mode vocal monopolisait le micro (conflit documenté
    par le shim de dictée) et la garde `blob < 100 o` étouffait la
    transcription locale : aucun énoncé n'arrivait dans le chat."""
    chunk = PROJ / "src-assets" / "frontend" / "_app" / "immutable" / "chunks" / "BeEbX_lw.js"
    if not chunk.exists():
        err("P141 : chunk d'appel BeEbX_lw.js absent")
        return
    ct = chunk.read_text(encoding="utf-8", errors="ignore")
    if ("J=new MediaRecorder(window.__callDictation"
            '&&o().audio?.stt?.engine==="web"&&window.__callSilent') not in ct:
        err("P141a : MediaRecorder non déporté sur le flux silencieux (STT local)")
    if "J=new MediaRecorder(z),J.onstart" in ct:
        err("P141a : MediaRecorder sur le vrai micro revenu (le natif sera sourd)")
    if "if((!Je||Je.size<100)&&!_w)return;" not in ct:
        err("P141b : garde blob non réservée au chemin serveur")
    if 'if(!Je||Je.size<100)return;await jt();' in ct:
        err("P141b : garde blob amont rétablie (transcription locale étouffée)")
    if 'console.warn(`Call STT: ' not in ct:
        err("P141b : trace de transcription absente")
    if "transcription vide (micro non entendu ?)" not in ct:
        err("P141b : toast de transcription vide absent")
    # P144 — la libération de micro est RETIRÉE (flux silencieux vivant)
    if "(z.getAudioTracks().forEach(zt=>zt.stop()),z=null)" in ct:
        err("P144c : libération de micro rétablie (arrêterait le MediaRecorder)")
    poly = PROJ / "app" / "src" / "main" / "assets" / "call_polyfill.js"
    if not poly.exists():
        err("P141 : assets/call_polyfill.js absent")
        return
    pt = poly.read_text(encoding="utf-8", errors="ignore")
    for motif, lib in (
        ("window.__callSilent", "flux silencieux __callSilent absent"),
        ("cur = t;", "repli sur résultats partiels absent"),
        ("function contenu()", "text() sans repli partiel"),
        ("[call-dict]", "traces du polyfill absentes"),
    ):
        if motif not in pt:
            err(f"P141 : call_polyfill.js — {lib}")


def check_appel_vad() -> None:
    """P142 — mode vocal : micro libéré à l'ouverture de l'énoncé, activité
    du recognizer entretenant la détection de parole."""
    chunk = PROJ / "src-assets" / "frontend" / "_app" / "immutable" / "chunks" / "BeEbX_lw.js"
    if not chunk.exists():
        err("P142 : chunk d'appel BeEbX_lw.js absent")
        return
    ct = chunk.read_text(encoding="utf-8", errors="ignore")
    if "window.__callVadHit&&window.__callVadHit()" not in ct:
        err("P142a : détection « parole continue » non pilotée par le recognizer")
    if 'ft.some(xr=>xr>0)&&(J&&J.state!=="recording"' in ct:
        err("P142a : garde VAD amont rétablie (muette pendant l'énoncé)")
    # P142c enchaîné sur P147 : le toast porte toujours l'erreur moteur,
    # mais sous forme de template literal (`${ce}`) depuis P147.
    if "(moteur : " not in ct:
        err("P142c : dernière erreur moteur absente du toast")
    poly = PROJ / "app" / "src" / "main" / "assets" / "call_polyfill.js"
    if not poly.exists():
        err("P142 : assets/call_polyfill.js absent")
        return
    pt = poly.read_text(encoding="utf-8", errors="ignore")
    for motif, lib in (
        ("window.__callVadHit", "signal d'activité du recognizer absent"),
        ("lastActivityAt = Date.now();", "horodatage d'activité absent"),
        ("error: info", "champ error absent de text()"),
    ):
        if motif not in pt:
            err(f"P142 : call_polyfill.js — {lib}")


def check_appel_diag() -> None:
    """P143 — préchauffage du recognizer + console JS journalisée."""
    chunk = PROJ / "src-assets" / "frontend" / "_app" / "immutable" / "chunks" / "BeEbX_lw.js"
    if not chunk.exists():
        err("P143 : chunk d'appel BeEbX_lw.js absent")
        return
    ct = chunk.read_text(encoding="utf-8", errors="ignore")
    if "window.__callDictation.warm&&window.__callDictation.warm()," not in ct:
        err("P143 : préchauffage du recognizer absent de l'ouverture d'appel")
    if 'return Ge(),E().addEventListener("chat:start",ct)' in ct:
        err("P143 : préchauffage amont rétabli (démarrage froid)")
    poly = PROJ / "app" / "src" / "main" / "assets" / "call_polyfill.js"
    if not poly.exists():
        err("P143 : assets/call_polyfill.js absent")
        return
    pt = poly.read_text(encoding="utf-8", errors="ignore")
    for motif, lib in (
        ("warm: function (lang)", "méthode warm() absente"),
        ("(prêt à ", "latence de démarrage non journalisée"),
        ("r.onstart = function ()", "prêt du moteur non horodaté"),
    ):
        if motif not in pt:
            err(f"P143 : call_polyfill.js — {lib}")


def check_appel_permanente() -> None:
    """P144 — mode vocal : écoute permanente (fin de la troncature de début).

    Le recognizer doit écouter AVANT la parole (comme en dictée) : `warm()`
    démarre l'écoute à l'ouverture de l'appel, les énoncés sont découpés par
    marqueurs, le micro réel est réservé au recognizer (flux silencieux pour
    le VAD), et la lecture TTS vide les tampons."""
    chunk = PROJ / "src-assets" / "frontend" / "_app" / "immutable" / "chunks" / "BeEbX_lw.js"
    if not chunk.exists():
        err("P144 : chunk d'appel BeEbX_lw.js absent")
        return
    ct = chunk.read_text(encoding="utf-8", errors="ignore")
    if "window.__callSpeechGate&&window.__callSpeechGate(" not in ct:
        err("P144a : silenciation TTS absente du VAD")
    if ("z=window.__callDictation&&o().audio?.stt?.engine===\"web\""
            "&&window.__callSilent?window.__callSilent()") not in ct:
        err("P144b : micro réel non réservé au recognizer (détection sur flux silencieux)")
    if "window.__callDictation.stop&&window.__callDictation.stop();" not in ct:
        err("P144d : arrêt de l'écoute permanente absent de la fermeture")
    poly = PROJ / "app" / "src" / "main" / "assets" / "call_polyfill.js"
    if not poly.exists():
        err("P144 : assets/call_polyfill.js absent")
        return
    pt = poly.read_text(encoding="utf-8", errors="ignore")
    for motif, lib in (
        ("window.__callSpeechGate", "porte de silenciation TTS absente"),
        ("function mark()", "marqueur de début d'énoncé absent"),
        ("segs.slice(-1)", "mark() ne garde pas le déclencheur (tête de phrase perdue)"),
        ("listening = false", "stop() sans arrêt de l'écoute"),
        ("Date.now() - lastActivityAt < 500", "fenêtre d'activité incohérente"),
    ):
        if motif not in pt:
            err(f"P144 : call_polyfill.js — {lib}")
    main_j = PROJ / "app" / "src" / "main" / "java" / "org" / "openwebui" / "android" / "MainActivity.java"
    if not main_j.exists():
        err("P143 : MainActivity.java absent")
        return
    mt = main_j.read_text(encoding="utf-8", errors="ignore")
    if "onConsoleMessage" not in mt:
        err("P143 : console JS non captée (onConsoleMessage absent)")
    if "data/logs/exec.log" not in mt:
        err("P143 : console JS non journalisée dans data/logs/exec.log")


def check_appel_silence_grace_tiling() -> None:
    """P145/P146/P147 — retour device : bip de tiling, écho IA, faux « aucun son ».

    P145 : le canal notification (STREAM_NOTIFICATION) joué par le service de
    reconnaissance est muet pendant les cycles start()/stop(), et restauré à la
    fermeture (onDestroy, restartApp) — jamais de canal bloqué en muet.
    P146 : grâce post-TTS de 2,5 s armée par __callSpeechGate(muted) et
    branchée aux 4 points (vadHit, onresult, onstart, mark) + réinit à stop().
    P147 : le silence normal (no-speech / aborted / aucun résultat) n'est plus
    un toast d'erreur — trace console seulement ; les vraies erreurs moteur
    restent toastées."""
    # P145 — Java
    sp = PROJ / "app" / "src" / "main" / "java" / "org" / "openwebui" / "android" / "AndroidSpeech.java"
    if not sp.exists():
        err("P145 : AndroidSpeech.java absent")
    else:
        st = sp.read_text(encoding="utf-8", errors="ignore")
        for motif, lib in (
            ("STREAM_NOTIFICATION", "canal notification non ciblé"),
            ("ADJUST_MUTE", "mute du canal absent"),
            ("isStreamMute(", "test d'état muet absent (orthographe API : "
                              "isStreamMute, SANS « d » final — "
                              "isStreamMuted n'existe pas → échec CI)"),
            ("unmuteNotifNow", "restauration du canal absente"),
            ("scheduleUnmute", "dé-mute différé (fin de cycle) absent"),
            ("muteNotif()", "mute avant startListening() absent"),
        ):
            if motif not in st:
                err(f"P145 : AndroidSpeech.java — {lib}")
    mj = PROJ / "app" / "src" / "main" / "java" / "org" / "openwebui" / "android" / "MainActivity.java"
    if not mj.exists():
        err("P145 : MainActivity.java absent")
    else:
        mt = mj.read_text(encoding="utf-8", errors="ignore")
        if mt.count("unmuteNotifNow()") < 2:
            err("P145 : dé-mute à la fermeture absent (onDestroy / restartApp)")
        if "androidSpeech = new AndroidSpeech(" not in mt:
            err("P145 : référence androidSpeech perdue (champ non instancié)")
    # P146 — polyfill
    poly = PROJ / "app" / "src" / "main" / "assets" / "call_polyfill.js"
    if not poly.exists():
        err("P146 : assets/call_polyfill.js absent")
    else:
        pt = poly.read_text(encoding="utf-8", errors="ignore")
        for motif, lib in (
            ("graceUntil = Date.now() + 2500", "armement de la grâce post-TTS absent"),
            ("if (Date.now() < graceUntil) return false;", "grâce non branchée à __callVadHit()"),
            ("résultat ignoré (grâce post-TTS)", "grâce non branchée à onresult()"),
            ("if (Date.now() >= graceUntil) lastActivityAt", "grâce non branchée à onstart()"),
            ("énoncé refusé (grâce post-TTS)", "grâce non branchée à mark()"),
            ("graceUntil = 0;", "grâce non réinitialisée à stop()"),
        ):
            if motif not in pt:
                err(f"P146 : call_polyfill.js — {lib}")
    # P147 — chunk d'appel
    chunk = PROJ / "src-assets" / "frontend" / "_app" / "immutable" / "chunks" / "BeEbX_lw.js"
    if not chunk.exists():
        err("P147 : chunk d'appel BeEbX_lw.js absent")
    else:
        ct = chunk.read_text(encoding="utf-8", errors="ignore")
        if "sil?console.warn(`Call STT: silence normal" not in ct:
            err("P147 : silence normal non silencieux en console (toast conservé)")
        if 'else _w&&$t.error(st&&st.error?"Call STT: transcription vide' in ct:
            err("P147 : toast bloquant amont rétabli (P142c non enchaînée)")


def check_tts_lecture() -> None:
    """P135/P136 — lecture à voix haute : le synthétiseur doit s'initialiser
    depuis getVoices(), et la boucle d'attente des voix doit être bornée."""
    java = PROJ / "app" / "src" / "main" / "java" / "org" / "openwebui" / "android"
    tts_j = (java / "AndroidTTS.java").read_text(encoding="utf-8", errors="ignore")

    # P135 — sans initialisation paresseuse, `tts` reste null tant que speak()
    # n'a pas été appelé : verrou (getVoices() vide → speak() jamais atteint).
    if "ensureTts(() -> { });" not in tts_j:
        err("P135 : voicesJson() n'initialise pas le synthétiseur (verrou)")
    if "initDone" not in tts_j:
        err("P135 : état « initialisation terminée » absent (file d'attente cassée)")
    if "private volatile boolean ready" not in tts_j:
        err("P135 : `ready` non volatile (visibilité depuis le thread JS)")

    # P136 — garde-fous de la boucle d'attente des voix dans le chunk d'appel
    chunk = PROJ / "src-assets" / "frontend" / "_app" / "immutable" / "chunks" / "BeEbX_lw.js"
    if not chunk.exists():
        err("P136 : chunk d'appel BeEbX_lw.js absent")
        return
    ct = chunk.read_text(encoding="utf-8", errors="ignore")
    for motif, lib in (
        ("Promise.race([new Promise(st=>{let et=null,gs=Date.now();",
         "boucle d'attente des voix non horodatée"),
        ("if(!Mt.length&&Date.now()-gs<5e3)return;",
         "lecture non forcée au-delà de 5 s sans voix"),
        ("at.aborted&&ft()}),new Promise(st=>setTimeout(st,15e3))])}",
         "garde-fous 15 s absent (une lecture sans retour fige la file)"),
    ):
        if motif not in ct:
            err(f"P136 : {lib}")
    # un retour en arrière signifierait l'ancienne boucle sans borne
    if "kt=setInterval(()=>{const Mt=speechSynthesis.getVoices();if(!Mt.length)return;" in ct:
        err("P136 : boucle d'attente des voix rétablie sans borne")


def check_appel_lecture() -> None:
    """P137 — la file de lecture d'un appel doit être relancée à chaque réponse."""
    chunk = PROJ / "src-assets" / "frontend" / "_app" / "immutable" / "chunks" / "BeEbX_lw.js"
    if not chunk.exists():
        err("P137 : chunk d'appel BeEbX_lw.js absent")
        return
    ct = chunk.read_text(encoding="utf-8", errors="ignore")

    # marqueur de boucle active : déclaré, effacé à la fin, testé au démarrage
    if 'let bt={},Wt={},Le="",ue=null,ntSig=null;' not in ct:
        err("P137 : marqueur de boucle de lecture absent (ntSig)")
    if "{a(q,!1),ntSig=null;break}" not in ct:
        err("P137 : fin de boucle sans effacement du marqueur")
    if "ntSig!==ce.signal&&(ntSig=ce.signal,nt(at,ce.signal)),a(q,!0)}" not in ct:
        err("P137 : ct ne relance pas la boucle / ne remet pas l'état « parle »")
    if "S=!0,bt[at]=!1," not in ct:
        err("P137 : drapeau « réponse finie » jamais effacé (relance immédiate "
            "puis re-arrêt de la boucle)")
    if "ce.signal.aborted&&(ce=new AbortController())" not in ct:
        err("P137 : signal annulé non recréé (interruption → plus de lecture)")
    # rétrogradation : version amont, la boucle ne se relance jamais
    if "}else if(bt[Je]&&rt[Je]&&rt[Je].length===0){a(q,!1);break}" in ct:
        err("P137 : boucle de lecture à nouveau non relançable (version amont)")
    if "ce=new AbortController,a(q,!0),nt(at,ce.signal))}" in ct:
        err("P137 : ct d'origine rétabli (relance conditionnée au changement de chat)")


def check_erreur_tts() -> None:
    """P138 — micro refusé et init Kokoro en échec : deux messages distincts,
    et l'init TTS jamais laissée en rejet silencieux."""
    chunk = PROJ / "src-assets" / "frontend" / "_app" / "immutable" / "chunks" / "BeEbX_lw.js"
    if not chunk.exists():
        err("P138 : chunk d'appel BeEbX_lw.js absent")
        return
    ct = chunk.read_text(encoding="utf-8", errors="ignore")
    # (a) découpe : le micro garde son message + return, l'init a son propre try
    if ('dr=null}catch{$t.error(c().t("Permission denied when accessing media '
        'devices"));return}try{f().audio?.tts?.engine==="browser-kokoro"') not in ct:
        err("P138a : découpe try micro / try init Kokoro absente")
    if ("catch(e1){$t.error(`Kokoro TTS: ${e1}`),"
        "console.warn(`Kokoro TTS: ${e1}`)}jn.set(!0),pi.set(!0)") not in ct:
        err("P138a : message Kokoro distinct + ouverture de l'appel absent")
    if "await D().init())),jn.set(!0),pi.set(!0)}catch{$t.error" in ct:
        err("P138a : try unique amont rétabli (toute erreur = micro refusé)")
    drz = PROJ / "src-assets" / "frontend" / "_app" / "immutable" / "chunks" / "DRZDe0Yd.js"
    if not drz.exists():
        err("P138 : chunk TTS DRZDe0Yd.js absent")
        return
    d = drz.read_text(encoding="utf-8", errors="ignore")
    if ("await he().init())}catch(e2){tr.error(`Kokoro TTS: ${e2}`),"
        "p(Me,!1),p(Se,!1);return}for(") not in d:
        err("P138b : init Kokoro de la file de lecture non interceptée")
    if "await he().init());for(const[,Ke]of gt.entries()){" in d:
        err("P138b : init non protégée amont rétablie (rejet silencieux)")


def _check_p139_fichier(path: pathlib.Path, setter: str, config: str, label: str) -> None:
    if not path.exists():
        err(f"P139 : {path.name} absent")
        return
    t = path.read_text(encoding="utf-8", errors="ignore")
    for motif, msg in (
        (f"const S={setter},C={config};", f"stores {label} ({setter}/{config})"),
        ("window.AndroidTTS.voicesJson()", "sonde de voix AndroidTTS absente"),
        ("if(eng===\"browser-kokoro\"){fix(!1);return}", "normalisation sync kokoro absente"),
        ("if((tt.engine??\"\")!==\"\")return;", "garde TTS serveur admin absente"),
        ("fix(!0)};", "forcing kokoro après sonde vide absent"),
        ('tt.engineConfig=Object.assign({},tt.engineConfig,{dtype:"q8"});',
         "dtype q8 par défaut absent"),
        ("tt.voice=\"af_heart\";", "voix de repli af_heart absente"),
        ("tt.defaultVoice=cv;", "alignement defaultVoice/config.voice absent"),
        ("window.__owuiSysTTS", "cache de voix système absent"),
    ):
        if motif not in t:
            err(f"P139 : {label} — {msg}")
    # rétrogradation : l'IIFE a disparu du chargeur
    if setter == "jr" and "jr.set(K.ui),t0(K?.keybindings)" in t:
        err("P139 : IIFE absente du chargeur de réglages (node 2)")
    if setter == "W" and "W.set(t)}if(await Oe.set(" in t:
        err("P139 : IIFE absente du chargeur de réglages (node 55)")


def check_default_kokoro() -> None:
    """P139 — les deux chargeurs de `$settings` forcent/normalisent Kokoro
    quand le « Default » navigateur est inutilisable."""
    imm = PROJ / "src-assets" / "frontend" / "_app" / "immutable" / "nodes"
    _check_p139_fichier(imm / "2.DwSK4ZlF.js", "jr", "Sr", "layout (app)")
    _check_p139_fichier(imm / "55.s0_1KP7y.js", "W", "Te", "/s/[id]")


def check_wasm_ort() -> None:
    """P140 — ONNX Runtime Web doit rester servi sous /wasm/ (Kokoro).

    Le worker Kokoro force `wasmPaths="/wasm/"` ; P13 supprimait le dossier
    entier, ce qui condamnait browser-kokoro à « no available backend found.
    ERR: [webgpu] TypeError: Failed to fetch dynamically imported module
    …/wasm/ort-wasm-simd-threaded.jsep.mjs » (rétroaction utilisateur)."""
    w = PROJ / "src-assets" / "frontend" / "wasm"
    for name, mini in (("ort-wasm-simd-threaded.jsep.mjs", 40_000),
                       ("ort-wasm-simd-threaded.jsep.wasm", 20_000_000)):
        f = w / name
        if not f.is_file():
            err(f"P140 : {name} absent de src-assets/frontend/wasm (Kokoro KO)")
        elif f.stat().st_size < mini:
            err(f"P140 : {name} tronqué ({f.stat().st_size} o < {mini})")
    workers = sorted((PROJ / "src-assets" / "frontend" / "_app" / "immutable"
                      / "workers").glob("kokoro.worker-*.js"))
    if not workers:
        err("P140 : worker kokoro.worker-*.js absent")
    else:
        t = workers[0].read_text(encoding="utf-8", errors="ignore")
        if 'wasmPaths="/wasm/"' not in t:
            err("P140 : wasmPaths du worker Kokoro ne pointe plus vers /wasm/")


def check_shims() -> None:
    if not (SRC / "tiktoken.py").exists():
        err("shim tiktoken.py absent")
    if not (SRC / "re2.py").exists():
        err("shim re2.py absent")
    if (SRC / "pycrdt.py").exists():
        err("stub pycrdt.py présent — il masquerait le module natif")


def check_searxng() -> None:
    if not (SRC / "searx" / "settings.yml").exists():
        err("searx/settings.yml absent")
    if not (SRC / "searx" / "version_frozen.py").exists():
        err("searx/version_frozen.py absent")


def check_frontend() -> None:
    front = PROJ / "src-assets" / "frontend"
    n_app = len(list((front / "_app").rglob("*"))) if (front / "_app").is_dir() else 0
    if n_app < 500:
        err(f"frontend : _app/ incomplet ({n_app} entrées)")
    if not (front / "pyodide" / "pyodide-lock.json").exists():
        err("frontend : pyodide absent (execute_code)")
    if not (front / "index.html").exists():
        err("frontend : index.html absent")
    else:
        idx = (front / "index.html").read_text(encoding="utf-8", errors="ignore")
        if "/fm" not in idx:
            err("frontend : bouton /fm absent de index.html")
        # P123 : l'icône du FAB doit être le SVG « fichier + roue crante »,
        # plus l'émoji 📎 (&#128206;) — un retour en arrière du patch
        # (ou un index.html régénéré sans patch_files_button) doit échouer ici.
        if 'id="fab-spa"' not in idx:
            err("frontend : FAB #fab-spa absent de index.html")
        if "&#128206;" in idx or "📎" in idx:
            err("frontend : émoji 📎 encore présent dans index.html (P123)")
        if 'id="fab-spa"' in idx and 'stroke-width="1.5"' not in idx:
            err("frontend : icône SVG du FAB absente de index.html (P123)")
    if (SRC / "open_webui" / "frontend").exists():
        err("frontend : encore dans open_webui/ (P15 non appliqué)")


def check_p125_fm() -> None:
    """P125 — icônes du sprite OWUI + style OWUI des pages /fm.

    Contrôle les deux pièces du patch sur les DEUX sources (prepare_src.py et
    le module généré android_fm.py) : le décorateur _fm_deco (émojis → SVG,
    3 placeholders @@ICO:nom@@) et le style OWUI (boutons 28 px, champs 11 px,
    cases 14 px avec coche, word-break, secondaire bordé). Un retour en
    arrière — module régénéré sans décorateur, CSS écrasé — échoue ici.
    """
    prep = (PROJ / "scripts" / "prepare_src.py").read_text(
        encoding="utf-8", errors="ignore")
    gen = SRC / "open_webui" / "android_fm.py"
    if not gen.exists():
        err("P125 : android_fm.py absent (prepare_src non lancé)")
        return
    txt = gen.read_text(encoding="utf-8", errors="ignore")
    # 1) le décorateur doit exister et être appelé sur le document complet
    if "def _fm_deco(" not in prep or "return _fm_deco(" not in prep:
        err("P125 : décorateur _fm_deco absent ou non appelé dans _fm_page "
            "(prepare_src.py)")
    if "def _fm_deco(" not in txt or "return _fm_deco(" not in txt:
        err("P125 : décorateur _fm_deco absent du module généré android_fm.py")
    # 2) la table émoji → icône, complète (23 entités au minimum)
    i = prep.find("_FM_EMO_ICO = {")
    if i < 0:
        err("P125 : table _FM_EMO_ICO absente de prepare_src.py")
    else:
        cles = prep[i:prep.find("\n}", i)]
        n = len(re.findall(r"'&#\d+;':", cles))
        if n < 23:
            err(f"P125 : _FM_EMO_ICO incomplet ({n} entrées, 23 attendues)")
        couvertes = set(re.findall(r"'(&#\d+;)':", cles))
        utilisees = set("&#" + e + ";" for e in re.findall(r"&#(\d+);", txt))
        reste = sorted(utilisees - couvertes)
        if reste:
            err(f"P125 : entité(s) non couverte(s) par le décorateur : {reste}")
    # 3) les 3 placeholders ciblés + aucun placeholder orphelin
    #    (on ignore les commentaires et la ligne du re.compile — le motif
    #     littéral @@ICO:nom@@ y serait un faux positif)
    k = prep.find("_FM_ICONS = {")
    ic = re.findall(r"^    '([a-z0-9-]+)':", prep[k:prep.find("\n}", k)], re.M)
    for ph in ("folder", "grid", "refresh"):
        if f"@@ICO:{ph}@@" not in txt:
            err(f"P125 : placeholder @@ICO:{ph}@@ absent de android_fm.py")
    vrais = []
    for ligne in txt.splitlines():
        s = ligne.strip()
        if s.startswith("#") or "re.compile(" in s:
            continue
        vrais += re.findall(r"@@ICO:([a-z0-9-]+)@@", ligne)
    orphelins = sorted(set(vrais) - set(ic))
    if orphelins:
        err(f"P125 : placeholder(s) @@ICO:@@ sans icône correspondante : {orphelins}")
    # 4) le style OWUI dans _FM_STYLE
    j = prep.find("_FM_STYLE = ")
    style = prep[j:prep.find("_FM_SVG = ", j)] if j >= 0 else ""
    for motif, lib in (
        ("input[type=checkbox]:after", "coche des cases à cocher"),
        ("html { word-break: break-word; }", "word-break OWUI"),
        ("min-height: 28px", "hauteur des boutons OWUI"),
        ("font-size: 11px", "taille des champs OWUI"),
        (".ghost { background: var(--btn2); color: var(--btn2-fg); "
         "border: 1px solid var(--border); }", "secondaire bordé OWUI"),
    ):
        if motif not in style:
            err(f"P125 : style OWUI manquant dans _FM_STYLE — {lib}")


def check_build_gradle() -> None:
    g = (PROJ / "app" / "build.gradle").read_text(encoding="utf-8", errors="ignore")
    lignes = [l for l in g.splitlines() if "ignoreAssetsPattern =" in l]
    if not lignes:
        err("P20 : ignoreAssetsPattern absent")
    elif "<dir>_*" in lignes[0]:
        err("P20 : ignoreAssetsPattern contient encore <dir>_*")
    if '"searx"' not in g:
        err("P16 : extractPackages sans searx")


def check_pyodide_paquets() -> None:
    """P38/P102/P103 : le worker Pyodide (la copie RÉELLEMENT exécutée —
    android_main.py force ENABLE_PYODIDE_FILE_PERSISTENCE) doit démarrer
    ALLÉGÉ ['micropip','numpy'], pandas/sympy en chargement à la demande.
    Évolution justifiée (journal v0.0.54) : l'ancien contrôle EXIGEAIT le boot
    lourd numpy/pandas/sympy dans le worker — il validait l'état qui tuait le
    worker par OOM (~115 Mo de wasm) et aurait bloqué le correctif P103. Le
    piège des DEUX copies est couvert : boot allégé exigé dans le worker ET
    dans la copie de repli (chunks), boot lourd rejeté partout.
    P15 déplace le frontend vers src-assets/ en fin de prepare → on contrôle
    la destination finale (nom de fichier haché → vérification par glob)."""
    import glob as _glob

    cibles = _glob.glob(
        str(PROJ / "src-assets" / "frontend" / "_app" / "immutable" / "workers" / "pyodide.worker-*.js")
    ) or _glob.glob(
        str(SRC / "open_webui" / "frontend" / "_app" / "immutable" / "workers" / "pyodide.worker-*.js")
    )
    if not cibles:
        err("P103 : worker pyodide introuvable dans frontend/_app/immutable/workers/")
        return
    for cible in cibles:
        with open(cible, encoding="utf-8", errors="ignore") as fh:
            contenu = fh.read()
        if 'packages:["micropip","numpy"]' not in contenu:
            err(f"P103 : boot allégé absent du worker (attendu packages:[\"micropip\",\"numpy\"]) — {cible}")
        if 'packages:["micropip","numpy","pandas","sympy"]' in contenu:
            err(f"P103 : boot lourd numpy/pandas/sympy encore présent dans le worker — {cible}")
        if "L.catch(()=>{L=null})" not in contenu:
            err(f"P49a : init du worker non réinitialisable — {cible}")
    # P44 : la voie worker doit être activée (sinon l'iframe contourne P103/P41)
    am = PROJ / "app" / "src" / "main" / "python" / "android_main.py"
    if am.exists() and 'ENABLE_PYODIDE_FILE_PERSISTENCE", "true"' not in am.read_text(encoding="utf-8", errors="ignore"):
        err("P44 : ENABLE_PYODIDE_FILE_PERSISTENCE non activé dans android_main.py")
    # P44b/P102 : la copie de repli (chunks, iframe/blob) doit être alignée —
    # boot allégé (numpy au boot, pandas/sympy à la demande — ~115 Mo de wasm
    # au boot tuaient le worker par lowmemorykiller Android).
    chunks = _glob.glob(str(PROJ / "src-assets" / "frontend" / "_app" / "immutable" / "chunks" / "*.js"))
    if chunks and not any(
        "packages: ['micropip','numpy']" in open(c, encoding="utf-8", errors="ignore").read()
        for c in chunks
    ):
        err("P44b/P102 : boot allégé absent (attendu packages: ['micropip','numpy'])")
    for c in chunks:
        if "packages: ['micropip','numpy','pandas','sympy']" in open(c, encoding="utf-8", errors="ignore").read():
            err(f"P103 : boot lourd présent dans la copie de repli — {c}")


def check_p41_harvest() -> None:
    """P41 : la remontée des fichiers /mnt/uploads repose sur 3 maillons
    (worker → frontend → execute_code) ; les deux premiers ont des noms hachés
    → vérification par glob sur la destination finale (src-assets/)."""
    import glob as _glob

    workers = _glob.glob(
        str(PROJ / "src-assets" / "frontend" / "_app" / "immutable" / "workers" / "pyodide.worker-*.js")
    )
    if workers and not any(
        "out.push({name:n,data:btoa(s)" in open(c, encoding="utf-8", errors="ignore").read()
        for c in workers
    ):
        err("P41a : worker pyodide sans remontée des fichiers /mnt/uploads")
    nodes = _glob.glob(
        str(PROJ / "src-assets" / "frontend" / "_app" / "immutable" / "nodes" / "0.*.js")
    )
    if nodes and not any(
        "files:ge.files||[]" in open(c, encoding="utf-8", errors="ignore").read()
        for c in nodes
    ):
        err("P41b : frontend sans transmission des fichiers produits")
    if nodes and not any(
        "u.packages||[]" in open(c, encoding="utf-8", errors="ignore").read()
        for c in nodes
    ):
        err("P46c : frontend sans transit des paquets serveur")


def check_p54_ciblage() -> None:
    """P54 : le fallback contenu doit être dans search_knowledge_bases — et SURTOUT
    pas dans list_knowledge_bases (queues identiques : en v0.0.30 l'ancre avait
    frappé le mauvais outil → 'query' is not defined)."""
    p = SRC / "open_webui" / "tools" / "builtin.py"
    t = p.read_text(encoding="utf-8", errors="ignore")
    for fn, attendu in (('list_knowledge_bases', False), ('search_knowledge_bases', True)):
        i = t.index(f'async def {fn}(')
        j = t.index('\nasync def ', i + 10)
        dedans = '# P54 :' in t[i:j]
        if dedans != attendu:
            err(f"P54 : fallback contenu mal placé dans {fn} (présent={dedans}, attendu={attendu})")


def check_js_syntax() -> None:
    """Tout fichier JS patché doit rester syntaxiquement valide — un chunk
    cassé affiche « 500 : Internal Server Error » au lancement (page d'erreur
    du SPA), et AUCUN contrôle Python ne le voit. Exécuté via node --check."""
    import glob as _glob
    import os
    import subprocess
    import tempfile
    from pathlib import Path

    cibles = []
    for motif in ("nodes/0.*.js", "nodes/2.*.js", "nodes/55.*.js",
                  "workers/pyodide.worker-*.js", "chunks/*.js"):
        cibles += _glob.glob(str(PROJ / "src-assets" / "frontend" / "_app" / "immutable" / motif))
    # P134 : nos propres shims d'assets doivent aussi être valides
    cibles += [str(PROJ / "app" / "src" / "main" / "assets" / n)
               for n in ("call_polyfill.js", "tts_polyfill.js")]
    vus = set()
    for c in sorted(cibles):
        t = open(c, encoding="utf-8", errors="ignore").read()
        # ne contrôler que les fichiers que NOUS patchons
        if not any(m in t for m in ("__prewarm", "__inNames", "files:ge.files||[]", "u.packages||[]",
                                    "micropip','numpy'", "__callDictation", "__androidTtsPolyfilled",
                                    "Kokoro TTS: ", "__owuiSysTTS")):
            continue
        if c in vus:
            continue
        vus.add(c)
        with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False, encoding="utf-8") as fh:
            fh.write(t)
            tmp = fh.name
        r = subprocess.run(["node", "--check", tmp], capture_output=True, text=True)
        os.unlink(tmp)
        if r.returncode != 0:
            err(f"syntaxe JS invalide : {Path(c).name} — {r.stderr.strip().splitlines()[-1] if r.stderr else '?'}")


def check_compilation() -> None:
    for p in SRC.rglob("*.py"):
        try:
            py_compile.compile(str(p), doraise=True)
        except Exception as exc:
            err(f"syntaxe invalide : {p.relative_to(SRC)} — {exc}")


def check_typo_courantes() -> None:
    """Erreurs déjà rencontrées : méthodes inexistantes sur modules stdlib."""
    for p in SRC.rglob("*.py"):
        t = p.read_text(encoding="utf-8", errors="ignore")
        for motif, msg in (
            ("_os2.sub(", "utilise re.sub, pas os.sub"),
            ("os.match(", "utilise re.match, pas os.match"),
        ):
            if motif in t:
                err(f"{p.relative_to(SRC)} : {msg}")
        # un module qui utilise asyncio doit l'importer — le NameError n'est
        # visible qu'à l'exécution (cas android_tools en v0.0.33). Borné à
        # open_webui/ (le vendor searx importe asyncio localement).
        if "open_webui" in str(p) and "asyncio." in t and "import asyncio" not in t:
            err(f"{p.relative_to(SRC)} : utilise asyncio sans l'importer")


def check_p104_diag() -> None:
    """P104 — diagnostic de livraison des appels outils : le traçage des envois,
    l'état des participants, les raisons de déconnexion et la route d'auto-test
    doivent être présents. Évolution justifiée (journal v0.0.55) : la livraison
    sio.call(to=sid) ne se voit nulle part — sans ces traces, chaque test
    appareil reste muet."""
    t = (SRC / "open_webui" / "socket" / "main.py").read_text(encoding="utf-8", errors="ignore")
    for marqueur, label in (
        ("P104 SEND eio=", "traçage des envois"),
        ("P104 disconnect sid=", "raison de déconnexion"),
        ("P104 ETAT sid=", "état des participants"),
        ("_p104_send_packet", "monkeypatch d'envoi"),
        ("_p105_json_sur", "P105 : payload JSON-sûr (octets → listes)"),
    ):
        if marqueur not in t:
            err(f"P104 : {label} absent de socket/main.py (marqueur {marqueur})")
    fm = (SRC / "open_webui" / "android_fm.py").read_text(encoding="utf-8", errors="ignore")
    if "fm_diag_eventcall" not in fm:
        err("P104 : route d'auto-test /fm/diag/eventcall absente de android_fm.py")
    # P106 — la voie worker doit être FORCÉE dans le bundle (la décision au
    # chargement du module lit une config pas encore arrivée → iframe choisie,
    # qui n'a ni ramassage P41 ni persistance IDBFS : piège des deux copies).
    import glob as _g
    chunks = _g.glob(str(PROJ / "src-assets" / "frontend" / "_app" / "immutable" / "chunks" / "*.js"))
    if chunks and not any(
        "const cp=()=>new hp" in open(c, encoding="utf-8", errors="ignore").read()
        for c in chunks
    ):
        err("P106 : la voie worker n'est pas forcée dans le bundle (attendu const cp=()=>new hp)")
    for c in chunks:
        t2 = open(c, encoding="utf-8", errors="ignore").read()
        if "enable_pyodide_file_persistence?new hp:new ap" in t2:
            err(f"P106 : la décision iframe/worker conditionnelle est encore présente — {c}")
    # P107 — la signature de Me() doit déclarer TO (le corps l'utilise :
    # exec_timeout + minuteur) ; retirer le préchauffage P70 l'avait emporté.
    import glob as _g2
    nodes = _g2.glob(str(PROJ / "src-assets" / "frontend" / "_app" / "immutable" / "nodes" / "0.*.js"))
    if nodes and not any(
        "Me=async(t,i,F,P=[],X=[],TO=120)=>{" in open(c, encoding="utf-8", errors="ignore").read()
        for c in nodes
    ):
        err("P107 : le paramètre TO=120 est absent de la signature de Me()")
    # P108 — les fichiers produits doivent être ENREGISTRÉS (base + stockage,
    # sinon invisibles au gestionnaire) et les avertissements FS bénins ne
    # doivent pas faire basculer le statut à error.
    at = (SRC / "open_webui" / "tools" / "android_tools.py").read_text(encoding="utf-8", errors="ignore")
    if "await Files.insert_new_file(" not in at or "remonte_fichiers_sable" not in at:
        err("P108 : l'enregistrement des fichiers produits est absent d'android_tools.py")
    bt = (SRC / "open_webui" / "tools" / "builtin.py").read_text(encoding="utf-8", errors="ignore")
    if "FS.syncfs operations in flight" not in bt:
        err("P108 : le filtre d'avertissements FS bénins est absent de builtin.py")
    if "await remonte_fichiers_sable(output" not in bt:
        err("P108 : l'appel de remontée n'est pas async (avec user_id)")


def main() -> int:
    check_fichiers()
    check_compile_typst_hors_bloc()
    check_shims()
    check_searxng()
    check_frontend()
    check_p125_fm()
    check_audio_locale()
    check_mode_vocal()
    check_tts_lecture()
    check_appel_lecture()
    check_erreur_tts()
    check_default_kokoro()
    check_wasm_ort()
    check_appel_stt_local()
    check_appel_vad()
    check_appel_diag()
    check_appel_permanente()
    check_appel_silence_grace_tiling()
    check_pyodide_paquets()
    check_p41_harvest()
    check_p54_ciblage()
    check_p104_diag()
    check_js_syntax()
    check_build_gradle()
    check_compilation()
    check_typo_courantes()
    if ERREURS:
        for e in ERREURS:
            print(f"  ERREUR : {e}")
        print(f"\nÉCHEC : {len(ERREURS)} patch(s) mal appliqué(s)")
        return 1
    print("OK : tous les patchs sont correctement appliqués ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
