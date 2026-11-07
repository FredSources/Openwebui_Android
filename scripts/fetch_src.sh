#!/usr/bin/env bash
# fetch_src.sh — sources amont Open WebUI (wheel PyPI) → vendor/unpacked/.
# vendor/ n'est pas versionné : ce script est la source de vérité pour le
# reconstruire (CI + machine neuve). Version figée = décision D6 (journal).
set -euo pipefail
PROJ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJ"
VERSION="${OPEN_WEBUI_VERSION:-0.13.0}"
DEST="$PROJ/vendor/unpacked"
WHL_DIR="$PROJ/downloads"
WHL="$WHL_DIR/open_webui-$VERSION.whl"

if [ -f "$DEST/open_webui/__init__.py" ]; then
  echo "[fetch] déjà présent : $DEST/open_webui"
  exit 0
fi

PY="$PROJ/.venv313/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"
mkdir -p "$WHL_DIR" "$DEST"

if [ ! -f "$WHL" ]; then
  echo "[fetch] téléchargement open-webui $VERSION depuis PyPI…"
  # --ignore-requires-python : le wheel porte un cap <3.13 (dû à pydub/audioop,
  # neutralisé par P5) — le wheel est py3-none-any, le cap ne nous concerne pas.
  "$PY" -m pip download "open-webui==$VERSION" --no-deps --only-binary :all: \
    --ignore-requires-python -d "$WHL_DIR" --no-cache-dir
  # pip nomme le wheel open_webui-<version>-py3-none-any.whl
  mv "$WHL_DIR"/open_webui-*.whl "$WHL"
fi

echo "[fetch] extraction dans vendor/unpacked/…"
"$PY" - "$WHL" "$DEST" <<'PYEOF'
import sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as z:
    z.extractall(sys.argv[2])
PYEOF

[ -f "$DEST/open_webui/__init__.py" ] || { echo "ERREUR : extraction incomplète"; exit 1; }
echo "[fetch] OK — $DEST/open_webui"
