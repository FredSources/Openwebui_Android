#!/usr/bin/env python3
"""check_patches.py — vérifie que les patchs P1–P30 sont correctement appliqués
dans l'arbre généré `src/` (+ build.gradle, + frontend).

Chaque contrôle correspond à un patch réel ; un patch « appliqué » par
prepare_src mais mal placé (P28, ex. compile_typst dans un bloc conditionnel)
ou cassé (_os2.sub) est ici détecté.

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
    ("P18 gate outils web", "open_webui/utils/tools.py",
     "if config.get('web.search.enable') and await has_user_permission('web_search')"),
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
    ("P68 timeout search_web", "open_webui/retrieval/web/searxng.py", "timeout=30"),
    ("P69 delete_file to_thread", "open_webui/tools/android_tools.py", "asyncio.to_thread(Storage.delete_file"),
    ("P69b fm_delete to_thread", "open_webui/android_fm.py", "asyncio.to_thread(Storage.delete_file"),
    ("P70 préchauffage bac à sable", "open_webui/tools/android_tools.py", "_uploads_pour_sable"),
    ("P54 fallback contenu KB", "open_webui/tools/builtin.py", "'source': 'content'"),
    ("P57 write_note auto-lecture", "open_webui/tools/builtin.py", "P57 : la note vient d'être écrite"),
    ("P58 list_tools", "open_webui/tools/android_tools.py", "async def list_tools("),
    ("P59 delete_file", "open_webui/tools/android_tools.py", "async def delete_file("),
    ("P65 délai garanti execute_code", "open_webui/tools/builtin.py", "timeout=200"),
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


def check_compile_typst_hors_bloc() -> None:
    """P28 : l'enregistrement doit être inconditionnel (indentation 4 espaces),
    pas greffé dans le bloc create_tool/workspace.tools."""
    p = SRC / "open_webui" / "utils" / "tools.py"
    lignes = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    reg = [l for l in lignes if "builtin_functions.append(compile_typst)" in l]
    if not reg:
        err("P28 : compile_typst non enregistré dans utils/tools.py")
        return
    if not reg[0].startswith("    builtin_functions.append(compile_typst)"):
        err(f"P28 : compile_typst mal placé (dans un bloc conditionnel ?) — {reg[0][:60]!r}")


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
    elif "/fm" not in (front / "index.html").read_text(encoding="utf-8", errors="ignore"):
        err("frontend : bouton /fm absent de index.html")
    if (SRC / "open_webui" / "frontend").exists():
        err("frontend : encore dans open_webui/ (P15 non appliqué)")


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
    """P38 : le worker Pyodide doit préinstaller numpy/pandas/sympy au boot.
    P15 déplace le frontend vers src-assets/ en fin de prepare → on contrôle
    la destination finale (nom de fichier haché → vérification par glob)."""
    import glob as _glob

    cibles = _glob.glob(
        str(PROJ / "src-assets" / "frontend" / "_app" / "immutable" / "workers" / "pyodide.worker-*.js")
    ) or _glob.glob(
        str(SRC / "open_webui" / "frontend" / "_app" / "immutable" / "workers" / "pyodide.worker-*.js")
    )
    if not cibles:
        err("P38 : worker pyodide introuvable dans frontend/_app/immutable/workers/")
        return
    for cible in cibles:
        with open(cible, encoding="utf-8", errors="ignore") as fh:
            contenu = fh.read()
        if 'packages:["micropip","numpy","pandas","sympy"]' not in contenu:
            err(f"P38 : paquets de boot numpy/pandas/sympy absents — {cible}")
        if "L.catch(()=>{L=null})" not in contenu:
            err(f"P49a : init du worker non réinitialisable — {cible}")
    # P44 : la voie worker doit être activée (sinon l'iframe contourne P38/P41)
    am = PROJ / "app" / "src" / "main" / "python" / "android_main.py"
    if am.exists() and 'ENABLE_PYODIDE_FILE_PERSISTENCE", "true"' not in am.read_text(encoding="utf-8", errors="ignore"):
        err("P44 : ENABLE_PYODIDE_FILE_PERSISTENCE non activé dans android_main.py")
    # P44b : filet de sécurité, le boot de l'iframe embarque aussi les paquets
    chunks = _glob.glob(str(PROJ / "src-assets" / "frontend" / "_app" / "immutable" / "chunks" / "*.js"))
    if chunks and not any(
        "packages: ['micropip','numpy','pandas','sympy']" in open(c, encoding="utf-8", errors="ignore").read()
        for c in chunks
    ):
        err("P44b : boot de l'iframe sans paquets scientifiques")


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
    for motif in ("nodes/0.*.js", "workers/pyodide.worker-*.js", "chunks/*.js"):
        cibles += _glob.glob(str(PROJ / "src-assets" / "frontend" / "_app" / "immutable" / motif))
    vus = set()
    for c in sorted(cibles):
        t = open(c, encoding="utf-8", errors="ignore").read()
        # ne contrôler que les fichiers que NOUS patchons
        if not any(m in t for m in ("__prewarm", "__inNames", "files:ge.files||[]", "u.packages||[]",
                                    "micropip','numpy'")):
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


def main() -> int:
    check_fichiers()
    check_compile_typst_hors_bloc()
    check_shims()
    check_searxng()
    check_frontend()
    check_pyodide_paquets()
    check_p41_harvest()
    check_p54_ciblage()
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
