"""Validation locale P124 : résolution de `file_path` pour compile_typst.

Usage : .venv313/bin/python3 scripts/test_p124.py

Hors APK : on remplace `typst` par un stub qui vérifie que compile() reçoit
un CHEMIN (str) pointant vers un .typ lisible — exactement le contrat qui
échouait avec « a bytes-like object is required ».
"""
import asyncio
import os
import shutil
import sys
import tempfile
import types
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix="p124-", dir="/tmp/opencode"))
UPLOAD = TMP / "uploads"
UPLOAD.mkdir()
os.environ.update(
    WEBUI_SECRET_KEY="test-local-p124",
    HOME=str(TMP),
    DATA_DIR=str(TMP),
    UPLOAD_DIR=str(UPLOAD),
    TYPST_CACHE_DIR=str(TMP / "cache"),
    DATABASE_URL=f"sqlite:///{TMP}/db.sqlite3",
)
sys.path = [str(PROJ / "src")] + [
    p for p in sys.path if p not in ("", str(PROJ), str(PROJ / "typst"))
]

VU = []


def _compile(chemin):
    assert isinstance(chemin, str), f"compile() attend un chemin str, reçu {type(chemin)}"
    p = Path(chemin)
    assert p.is_file() and p.suffix == ".typ", f"chemin invalide : {chemin}"
    contenu = p.read_text(encoding="utf-8")
    VU.append((str(p), contenu))
    return b"%PDF-1.4\n%P124-test\n"


sys.modules["typst"] = types.SimpleNamespace(compile=_compile)

from open_webui.models import files as files_mod  # noqa: E402
from open_webui.storage import provider as storage_mod  # noqa: E402
from open_webui.tools import android_tools  # noqa: E402


class FauxFichier:
    def __init__(self, fid, filename, path, name):
        self.id = fid
        self.filename = filename
        self.path = path
        self.meta = {"name": name, "content_type": "text/plain", "size": 12}


class FauxFiles:
    enregistres = []

    @staticmethod
    async def get_file_by_id(fid):
        return next((f for f in FauxFiles.enregistres if f.id == fid), None)

    @staticmethod
    async def get_files_by_user_id(user_id):
        return list(FauxFiles.enregistres)

    @staticmethod
    async def insert_new_file(user_id, form):
        enr = FauxFichier(form.id, form.filename, form.path, (form.meta or {}).get("name") or "")
        enr.meta = dict(form.meta or {})
        FauxFiles.enregistres.append(enr)
        return form.id


class FauxStorage:
    @staticmethod
    def get_file(file_path):
        if str(file_path).startswith("/mnt/uploads/"):
            return str(UPLOAD / Path(file_path).name)
        return str(file_path)

    @staticmethod
    def upload_file(file, filename, tags):
        chemin = UPLOAD / filename
        chemin.write_bytes(file.read())
        return filename, str(chemin)


source_typ = "= Rapport P124\n\nTest de résolution de chemin.\n"
stocke = UPLOAD / "abc123_rapport.typ"
stocke.write_text(source_typ, encoding="utf-8")
FauxFiles.enregistres = [
    FauxFichier("fid-1", "abc123_rapport.typ", str(stocke), "rapport.typ")
]

files_mod.Files = FauxFiles
storage_mod.Storage = FauxStorage

user = {"id": "u-test", "name": "Test"}

cas = [
    ("chemin /mnt/uploads (nom affiché)", "/mnt/uploads/rapport.typ"),
    ("file_id", "fid-1"),
    ("URL /files/<id>/content", "/api/v1/files/fid-1/content"),
    ("nom affiché", "rapport.typ"),
    ("chemin disque", str(stocke)),
]

try:
    for label, valeur in cas:
        VU.clear()
        resultat = asyncio.run(
            android_tools.compile_typst(file_path=valeur, output_name=f"pdf-{len(VU)}", __user__=user)
        )
        assert '"file_id"' in resultat, resultat
        assert VU[-1][1] == source_typ, (label, VU[-1][1])
        print(f"OK  {label:36s} -> {Path(VU[-1][0]).name}")

    VU.clear()
    asyncio.run(
        android_tools.compile_typst(source=source_typ, output_name="pdf-source", __user__=user)
    )
    assert VU[-1][1] == source_typ
    print(f"OK  {'source (régression D14)':36s} -> {Path(VU[-1][0]).name}")

    # P124a : un fichier du même nom déjà sur disque (mais pas en base) ne
    # doit plus faire sauter l'enregistrement — c'était le bug list_files.
    import base64

    (UPLOAD / "resultat.csv").write_text("vieux contenu", encoding="utf-8")
    avant = len(FauxFiles.enregistres)
    notes = asyncio.run(
        android_tools.remonte_fichiers_sable(
            {"files": [{"name": "resultat.csv",
                        "data": base64.b64encode(b"col1,col2\n1,2\n").decode()}]},
            "u-test",
        )
    )
    assert len(notes) == 1 and notes[0]["name"] == "resultat.csv", notes
    assert len(FauxFiles.enregistres) == avant + 1
    print("OK  {'sortie execute_code -> list_files':36s} ->", notes[0]["file_id"])

    # Doublon réel (même nom, même taille, déjà en base) : on réutilise l'id.
    notes2 = asyncio.run(
        android_tools.remonte_fichiers_sable(
            {"files": [{"name": "resultat.csv",
                        "data": base64.b64encode(b"col1,col2\n1,2\n").decode()}]},
            "u-test",
        )
    )
    assert len(notes2) == 1 and notes2[0]["file_id"] == notes[0]["file_id"]
    assert len(FauxFiles.enregistres) == avant + 1
    print("OK  {'dedup sans doublon':36s} ->", notes2[0]["file_id"])
finally:
    shutil.rmtree(TMP, ignore_errors=True)

print("\nTous les cas P124 sont valides.")
