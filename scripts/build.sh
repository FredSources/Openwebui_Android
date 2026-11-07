#!/usr/bin/env bash
# build.sh — build complet de l'APK (tout dans le projet, isolation D5).
set -euo pipefail
PROJ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJ"
source "$PROJ/scripts/env.sh" >/dev/null

export ANDROID_HOME="$PROJ/android-sdk"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export GRADLE_USER_HOME="$PROJ/.gradle-cache"
export TMPDIR="$PROJ/.tmp"
export PIP_CACHE_DIR="$PROJ/.pip-cache"
export JAVA_HOME="$PROJ/tools/jdk"          # JDK portable : javac requis (D5)
export PATH="$JAVA_HOME/bin:$PATH"

# 1. SDK + Gradle
bash "$PROJ/scripts/setup-sdk.sh"

# 2. Sources patchées (si absentes)
[ -d "$PROJ/src/open_webui" ] || "$PROJ/.venv313/bin/python" "$PROJ/scripts/prepare_src.py"

# 3. Wheels Rust cross-buildés (si absents)
if ! ls "$PROJ/wheels"/pydantic_core-*.whl >/dev/null 2>&1; then
  bash "$PROJ/scripts/build-wheels.sh"
fi

# 4. Build APK — nettoyage obligatoire : la packaging incrémentale d'AGP
#    (zipflinger) réutilise l'APK précédent et append les entrées changées ;
#    app.imy (110 Mo) étant réécrit à chaque patch, ses anciennes copies
#    s'accumulent dans le zip (193 → 303 Mo constatés). Cf. journal.
rm -rf "$PROJ/app/build/outputs/apk" "$PROJ/app/build/intermediates/apk"
# versionCode auto-incrémenté → purge du cache WebView à chaque nouvelle version
VC=1
[ -f "$PROJ/version_code" ] && VC=$(( $(cat "$PROJ/version_code") + 1 ))
echo "$VC" > "$PROJ/version_code"
echo "[build] versionCode=$VC"
GRADLE="$PROJ/tools/gradle/gradle-8.10.2/bin/gradle"
"$GRADLE" --no-daemon -p "$PROJ" "${1:-assembleDebug}" -Pvcode="$VC"

# 5. Copie vers dist/
mkdir -p "$PROJ/dist"
find "$PROJ/app/build/outputs/apk" -name '*.apk' -exec cp {} "$PROJ/dist/" \;
echo "[build] APK :"
ls -la "$PROJ/dist/"
