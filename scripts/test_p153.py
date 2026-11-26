"""Validation locale P153 : RUN_DIR des machines sous TMPDIR, jamais /tmp en dur.

Usage : .venv313/bin/python3 scripts/test_p153.py

Contrôle du incident signalé sur l'appareil :
`PermissionError: [Errno 13] Permission denied: '/tmp/open-webui-71ndqf72'`.
"""
import os
import sys
import tempfile
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix='p153-', dir='/tmp/opencode'))
os.environ.update(
    WEBUI_SECRET_KEY='test-local-p153',
    HOME=str(TMP),
    DATA_DIR=str(TMP / 'data'),
    UPLOAD_DIR=str(TMP / 'uploads'),
    TMPDIR=str(TMP / 'tmp'),
    DATABASE_URL=f"sqlite:///{TMP}/db.sqlite3",
)
(TMP / 'tmp').mkdir(parents=True, exist_ok=True)
sys.path = [str(PROJ / 'src')] + [p for p in sys.path if p not in ('', str(PROJ))]

print('=== P153 — temporaires machines sous TMPDIR ===')

source = (PROJ / 'src/open_webui/utils/machines/managed.py').read_text(encoding='utf-8')
assert "dir='/tmp'" not in source, 'chemin /tmp encore en dur dans managed.py'
assert "os.environ.get('TMPDIR')" in source
assert 'P153 : RUN_DIR suit TMPDIR' in source
print('OK  source : aucun /tmp en dur, TMPDIR explicite, marqueur P153')

from open_webui.utils.machines import managed  # noqa: E402

assert managed.RUN_DIR.exists(), managed.RUN_DIR
assert managed.RUN_DIR.parent == Path(os.environ['TMPDIR']), managed.RUN_DIR
assert str(managed.RUN_DIR).startswith(str(TMP)), managed.RUN_DIR
print(f'OK  RUN_DIR importé sous TMPDIR -> {managed.RUN_DIR.name}')

print('\nTous les cas P153 sont valides.')
