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
# JDK portable du projet (D5) ; sur CI, le JDK système (setup-java) fait l'affaire
if [ -d "$PROJ/tools/jdk" ]; then
  export JAVA_HOME="$PROJ/tools/jdk"
  export PATH="$JAVA_HOME/bin:$PATH"
fi

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
#    + app/build/python : la tâche pip de Chaquopy ne suit que le FICHIER de
#    requirements — un wheel reconstruit (même nom/version) n'est jamais
#    réinstallé : l'ancien .so restait dans l'APK (cas uuid_utils/typst abi3).
rm -rf "$PROJ/app/build/outputs/apk" "$PROJ/app/build/intermediates/apk" \
       "$PROJ/app/build/python" "$PROJ/app/build/generated" \
       "$PROJ/app/build/intermediates/assets"
# versionCode auto-incrémenté → purge du cache WebView à chaque nouvelle version
VC=1
[ -f "$PROJ/version_code" ] && VC=$(( $(cat "$PROJ/version_code") + 1 ))
echo "$VC" > "$PROJ/version_code"
echo "[build] versionCode=$VC"
GRADLE="$PROJ/tools/gradle/gradle-8.10.2/bin/gradle"
# une ou plusieurs tâches Gradle (ex. assembleDebug assembleRelease) — même versionCode
[ $# -gt 0 ] || set -- assembleDebug
"$GRADLE" --no-daemon -p "$PROJ" "$@" -Pvcode="$VC"

# 5. Copie vers dist/
mkdir -p "$PROJ/dist"
find "$PROJ/app/build/outputs/apk" -name '*.apk' -exec cp {} "$PROJ/dist/" \;
echo "[build] APK :"
ls -la "$PROJ/dist/"
