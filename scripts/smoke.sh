#!/usr/bin/env bash
# smoke.sh — test de fumée hôte : lance l'app via android_main (comme dans l'APK),
# donc serveur Open WebUI + SearXNG embarqué, puis répond sur les ports 8080/8888.
set -u
PROJ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJ"
export PYTHONPATH="$PROJ/src:$PROJ/app/src/main/python"
export FRONTEND_BUILD_DIR="$PROJ/src/open_webui/frontend"
export STATIC_DIR="$PROJ/src/open_webui/static"
export DATA_DIR="$PROJ/.data-test"
export HOME="$PROJ/.home-test"
mkdir -p "$DATA_DIR" "$HOME"
export USE_CUDA_DOCKER=false
export ENABLE_OTEL=false
export WEBUI_AUTH=false
export ANONYMIZED_TELEMETRY=false
export DO_NOT_TRACK=true
export SCARF_NO_ANALYTICS=true
export HF_HUB_OFFLINE=1
exec .venv313/bin/python -c "
import time, android_main
android_main.start_server(8080)
print('smoke: serveur démarré (8080) + SearXNG (8888)', flush=True)
while True:
    time.sleep(60)
"
