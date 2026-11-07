#!/usr/bin/env bash
# setup-sdk.sh — Android SDK + Gradle, TOUT installé dans le projet (isolation D5).
set -euo pipefail
PROJ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJ"
export TMPDIR="$PROJ/.tmp"

SDK="$PROJ/android-sdk"
TOOLS_ZIP="$PROJ/downloads/cmdline-tools.zip"
GRADLE_ZIP="$PROJ/downloads/gradle.zip"

# --- Android SDK ---
if [ ! -x "$SDK/cmdline-tools/latest/bin/sdkmanager" ]; then
  echo "[sdk] installation des cmdline-tools…"
  [ -f "$TOOLS_ZIP" ] || { echo "ERREUR: $TOOLS_ZIP absent (téléchargement requis)"; exit 1; }
  mkdir -p "$SDK/cmdline-tools"
  rm -rf "$SDK/cmdline-tools/latest" "$SDK/cmdline-tools/cmdline-tools"
  unzip -q "$TOOLS_ZIP" -d "$SDK/cmdline-tools"
  mv "$SDK/cmdline-tools/cmdline-tools" "$SDK/cmdline-tools/latest"
fi

export ANDROID_HOME="$SDK" ANDROID_SDK_ROOT="$SDK"
SM="$SDK/cmdline-tools/latest/bin/sdkmanager"

if [ ! -d "$SDK/platforms/android-34" ]; then
  echo "[sdk] acceptation des licences…"
  yes | "$SM" --licenses >/dev/null 2>&1 || true
  echo "[sdk] installation platform-34 + build-tools…"
  "$SM" "platform-tools" "platforms;android-34" "build-tools;34.0.0" >/dev/null
fi

# --- Gradle (dans le projet) ---
if [ ! -x "$PROJ/tools/gradle/gradle-8.10.2/bin/gradle" ]; then
  echo "[gradle] installation…"
  [ -f "$GRADLE_ZIP" ] || { echo "ERREUR: $GRADLE_ZIP absent"; exit 1; }
  mkdir -p "$PROJ/tools/gradle"
  unzip -q "$GRADLE_ZIP" -d "$PROJ/tools/gradle"
fi

echo "[sdk] OK — SDK=$SDK"
echo "[gradle] OK — $PROJ/tools/gradle/gradle-8.10.2/bin/gradle"
