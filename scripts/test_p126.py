"""Validation locale P126 : périmètre « utilisateur courant » et exhaustivité.

Usage : .venv313/bin/python3 scripts/test_p126.py

Contrôles :
1. `list_files` pagine au-delà de 200 fichiers et reste sur l'utilisateur courant,
   même avec `role=admin` (c'est la référence invoquée par l'utilisateur).
2. Le pont P124/P125 journalise un échec d'enregistrement au lieu de l'avaler.
3. `/fm` (source générée) utilise `user.id`, scanne les sous-dossiers et pagine
   l'union base + orphelins.
"""
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix="p126-", dir="/tmp/opencode"))
UPLOAD = TMP / "uploads"
UPLOAD.mkdir()
os.environ.update(
    WEBUI_SECRET_KEY="test-local-p126",
    HOME=str(TMP),
    DATA_DIR=str(TMP),
    UPLOAD_DIR=str(UPLOAD),
    DATABASE_URL=f"sqlite:///{TMP}/db.sqlite3",
)
sys.path = [str(PROJ / "src")] + [
    p for p in sys.path if p not in ("", str(PROJ))
]

from open_webui.models import files as files_mod  # noqa: E402
from open_webui.storage import provider as storage_mod  # noqa: E402
from open_webui.tools import android_tools  # noqa: E402

APPELS = []
PROPRES = [
    type("F", (), {"id": f"f-{i:03d}", "filename": f"{i:03d}_doc.txt",
                   "updated_at": 1700000000 + i,
                   "meta": {"name": f"doc-{i}.txt", "size": 10}})()
    for i in range(450)
]
AUTRE = type("F", (), {"id": "etranger", "filename": "999_autre.txt",
                       "updated_at": 1700000000,
                       "meta": {"name": "autre.txt", "size": 10}})()


class FauxFiles:
    @staticmethod
    async def get_file_list(user_id=None, skip=0, limit=50, db=None):
        APPELS.append((user_id, skip, limit))
        src = PROPRES if user_id == "u-courant" else [AUTRE]
        return type("R", (), {"items": src[skip:skip + limit]})()

    @staticmethod
    async def get_files_by_user_id(user_id):
        return list(PROPRES[:1])

    @staticmethod
    async def insert_new_file(user_id, form):
        assert user_id == "u-courant", user_id
        return form.id


class FauxStorage:
    @staticmethod
    def get_file(path):
        return str(UPLOAD / Path(str(path)).name)

    @staticmethod
    def upload_file(file, filename, tags):
        if "casse" in filename:
            raise OSError("disque plein simulé")
        chemin = UPLOAD / filename
        chemin.write_bytes(file.read())
        return filename, str(chemin)


files_mod.Files = FauxFiles
storage_mod.Storage = FauxStorage
TRACES = []
android_tools.journal_exec_ligne = TRACES.append

try:
    # 1. list_files : 450 fichiers, 3 pages, aucun admin bypass.
    brut = asyncio.run(android_tools.list_files(
        __user__={"id": "u-courant", "role": "admin"}))
    liste = json.loads(brut)
    assert len(liste) == 450, len(liste)
    assert all(appel[0] == "u-courant" for appel in APPELS), APPELS
    assert [a[1] for a in APPELS] == [0, 200, 400], APPELS
    assert all(f["id"] != "etranger" for f in liste)
    print(f"OK  {'list_files exhaustif (450 > 200)':36s} -> pages {[a[1] for a in APPELS]}")

    # 2. pont : l'échec d'un fichier est tracé, l'autre est enregistré.
    import base64
    donnees = [
        {"name": "0_casse.typ", "data": base64.b64encode(b"X").decode()},
        {"name": "1_ok.typ", "data": base64.b64encode(b"Y").decode()},
    ]
    produits = asyncio.run(android_tools.remonte_fichiers_sable(
        {"files": donnees}, "u-courant"))
    assert len(produits) == 1 and produits[0]["name"] == "1_ok.typ", produits
    echecs = [t for t in TRACES if "P126 echec enregistrement" in t]
    assert len(echecs) == 1 and "0_casse.typ" in echecs[0], TRACES
    print(f"OK  {'trace echec enregistrement':36s} -> {echecs[0][:70]}")

    # 3. /fm : généré depuis le patch, contrôle statique des 4 marqueurs.
    fm = (PROJ / "src/open_webui/android_fm.py").read_text(encoding="utf-8")
    for marqueur, libelle in [
        ("uid = user.id", "périmètre utilisateur courant"),
        ("_UP.rglob('*')", "orphelins récursifs"),
        ("entrees.sort(key=lambda e: e[0], reverse=True)", "union triée"),
        ("entrees[(page - 1) * per_page:page * per_page]", "pagination union"),
    ]:
        assert marqueur in fm, marqueur
        print(f"OK  {libelle:36s} -> présent")
finally:
    pass

print("\nTous les cas P126 sont valides.")
