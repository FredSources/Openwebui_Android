"""Validation locale P154 : sessions aiohttp compatibles avec la version épinglée.

Usage : .venv313/bin/python3 scripts/test_p154.py

Régression signalée : « OpenAI: Network Problem » après la montée en v0.13.5.
L'amont ajoute `middlewares=(sign_aws_request,)` aux `aiohttp.ClientSession`,
paramètre introduit dans aiohttp 3.11 alors que le fork épingle 3.10.10 : chaque
création de session levait `TypeError`, avant même toute requête réseau.
"""
import asyncio
import os
import sys
import tempfile
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix='p154-', dir='/tmp/opencode'))
os.environ.update(
    WEBUI_SECRET_KEY='test-local-p154',
    HOME=str(TMP),
    DATA_DIR=str(TMP / 'data'),
    UPLOAD_DIR=str(TMP / 'uploads'),
    TMPDIR=str(TMP / 'tmp'),
    DATABASE_URL=f"sqlite:///{TMP}/db.sqlite3",
)
(TMP / 'tmp').mkdir(parents=True, exist_ok=True)
# Le banc écoute sur 127.0.0.1:8090 : aucun proxy ne doit détourner la requête.
for cle in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'):
    os.environ.pop(cle, None)
sys.path = [str(PROJ / 'src')] + [p for p in sys.path if p not in ('', str(PROJ))]

print('=== P154 — compatibilité aiohttp 3.10 des sessions OpenAI ===')

for rel in ('utils/aws.py', 'routers/openai.py', 'utils/session_pool.py'):
    source = (PROJ / 'src/open_webui' / rel).read_text(encoding='utf-8')
    assert 'middlewares=' not in source, f'{rel} : middlewares= encore présent'
    assert 'P154' in source, f'{rel} : marqueur P154 absent'
print('OK  source : aucun middlewares=, 3 fichiers marqués P154')

import aiohttp  # noqa: E402
from open_webui.utils.aws import client_session_kwargs  # noqa: E402

kwargs = client_session_kwargs(timeout=aiohttp.ClientTimeout(total=5), trust_env=True)
if 'middlewares' in kwargs:
    print('NOTE aiohttp récent : middleware AWS conservé (comportement amont)')
else:
    assert aiohttp.__version__.startswith('3.10.'), aiohttp.__version__
    print(f'OK  aiohttp {aiohttp.__version__} : middlewares omis, session constructible')


async def verif() -> None:
    async with aiohttp.ClientSession(**kwargs) as session:
        assert not session.closed
    print('OK  ClientSession construite et fermée sans TypeError')

    # Serveur factice sur 8090 (jamais 8080 : port de l'application).
    from aiohttp import web

    async def models(_request):
        return web.json_response({'data': [{'id': 'p154-fake-model'}]})

    app = web.Application()
    app.router.add_get('/v1/models', models)
    runner = web.AppRunner(app)
    await runner.setup()
    try:
        site = web.TCPSite(runner, '127.0.0.1', 8090)
        await site.start()

        from open_webui.routers.openai import get_models_request

        resultat = await get_models_request(url='http://127.0.0.1:8090/v1')
        assert resultat is not None, 'get_models_request a renvoyé None (réseau cassé)'
        assert resultat['data'][0]['id'] == 'p154-fake-model', resultat
        print('OK  get_models_request -> liste de modèles reçue du provider factice')
    finally:
        await runner.cleanup()


asyncio.run(verif())
print('\nTous les cas P154 sont valides.')
