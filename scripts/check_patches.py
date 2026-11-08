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
    ("P27 navigateur /fm", "open_webui/main.py", "async def fm_browser("),
    ("P27 aperçu /fm/preview", "open_webui/main.py", "async def fm_preview("),
    ("P27 suppression /fm/delete", "open_webui/main.py", "async def fm_delete("),
    ("P30a alias /mnt/uploads (storage)", "open_webui/storage/provider.py", 'startswith("/mnt/uploads/")'),
    ("P30b alias /mnt/uploads (display_file)", "open_webui/tools/builtin.py", "startswith('/mnt/uploads/')"),
    ("P30c orientation view_note", "open_webui/tools/builtin.py", "utilisez view_note"),
    ("P30 taille/humaine (fm)", "open_webui/main.py", "def _fm_size("),
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


def main() -> int:
    check_fichiers()
    check_compile_typst_hors_bloc()
    check_shims()
    check_searxng()
    check_frontend()
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
