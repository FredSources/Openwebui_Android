"""Validation locale P151 : options d'extraction sans service local implicite.

Usage : .venv313/bin/python3 scripts/test_p151.py

Contrôles :
1. les défauts MinerU/Tika/Docling ne pointent plus vers un service local ;
2. le patch frontend masque bien le switch « PDF Extract Images (OCR) » ;
3. PDFLoader._extract_images() ignore proprement l'OCR quand rapidocr est
   absent (même si une ancienne configuration avait `PDF_EXTRACT_IMAGES=true`).
"""
import io
import os
import sys
import tempfile
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix="p151-", dir="/tmp/opencode"))
os.environ.update(
    WEBUI_SECRET_KEY="test-local-p151",
    HOME=str(TMP),
    DATA_DIR=str(TMP),
    UPLOAD_DIR=str(TMP / "uploads"),
    DATABASE_URL=f"sqlite:///{TMP}/db.sqlite3",
)
sys.path = [str(PROJ / "src")] + [
    p for p in sys.path if p not in ("", str(PROJ))
]

print("=== P151 — extraction sans service local ===")

# 1. Défauts neutralisés dans la configuration générée.
cfg = (PROJ / "src/open_webui/config.py").read_text(encoding="utf-8")
for attendu in (
    "MINERU_API_MODE = os.getenv('MINERU_API_MODE', 'cloud')",
    "MINERU_API_URL = os.getenv('MINERU_API_URL', '')",
    "TIKA_SERVER_URL = os.getenv('TIKA_SERVER_URL', '')",
    "DOCLING_SERVER_URL = os.getenv('DOCLING_SERVER_URL', '')",
):
    assert attendu in cfg, attendu
    print(f"OK  défaut neutralisé : {attendu.split(' = ')[0]}")

# 2. Patch frontend appliqué au source Svelte (CI recompile ce source).
svelte = (PROJ / "vendor/open-webui/src/lib/components/admin/Settings/Documents.svelte").read_text(
    encoding="utf-8"
)
for marqueur in ("P151 : OCR PDF local", "{#if false && RAGConfig.CONTENT_EXTRACTION_ENGINE === ''}"):
    assert marqueur in svelte, marqueur
print("OK  switch OCR PDF masqué dans Documents.svelte")

# 3. Garde-fou runtime : rapidocr absent => OCR ignoré, pas d'exception.
sys.modules["rapidocr"] = None  # force ModuleNotFoundError sur l'import
from open_webui.retrieval.loaders.pdf import PDFLoader  # noqa: E402
from PIL import Image  # noqa: E402

tampon = io.BytesIO()
Image.new("RGB", (2, 2), "white").save(tampon, format="PNG")
png = tampon.getvalue()


class FluxImage:
    """XObject PDF minimal : assez pour que Pillow lise l'image."""

    def get(self, cle):
        return "/Image" if cle == "/Subtype" else None

    def get_data(self):
        return png


page = {"/Resources": {"/XObject": {"/Im1": FluxImage()}}}
chargeur = PDFLoader(str(TMP / "absent.pdf"), extract_images=True)
assert chargeur._extract_images(page) == ""
assert chargeur.ocr is False
print("OK  OCR PDF ignoré sans rapidocr (ancienne config true incluse)")

pdf = (PROJ / "src/open_webui/retrieval/loaders/pdf.py").read_text(encoding="utf-8")
assert "P151 OCR PDF ignore" in pdf
print("OK  marqueur P151 présent dans pdf.py")

print("\nTous les cas P151 sont valides.")
