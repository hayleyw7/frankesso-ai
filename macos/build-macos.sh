#!/bin/bash
# Build-time downloads only. The app and its bundled model need no network.
set -euo pipefail
[[ $(uname -s)/$(uname -m) == Darwin/arm64 ]] || { echo "Use an Apple Silicon Mac." >&2; exit 1; }
root="$(cd "$(dirname "$0")/.." && pwd -P)"
build="$(mktemp -d)"
build="$(cd "$build" && pwd -P)"
trap 'rm -rf "$build"' EXIT

python=${FRANKESSO_BUILD_PYTHON:-/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13}
"$python" -c 'import platform, tkinter; assert platform.machine() == "arm64"'
"$python" -m venv "$build/venv"
python="$build/venv/bin/python"
"$python" -m pip install --disable-pip-version-check --no-cache-dir 'pyinstaller==6.22.3'

# Same audited llama.cpp commit and offline feature flags as the Windows bundle.
llama_commit=78a8ae14be559b45f5f13ddee82c188b683d5d8d
git init --quiet "$build/llama"
git -C "$build/llama" fetch --depth=1 https://github.com/ggml-org/llama.cpp.git "$llama_commit"
git -C "$build/llama" checkout --quiet --detach FETCH_HEAD
[[ $(git -C "$build/llama" rev-parse HEAD) == "$llama_commit" ]]
cmake -S "$build/llama" -B "$build/llama-out" \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_OSX_ARCHITECTURES=arm64 -DCMAKE_OSX_DEPLOYMENT_TARGET=13.0 \
    -DBUILD_SHARED_LIBS=OFF -DGGML_BACKEND_DL=OFF -DGGML_OPENMP=OFF -DGGML_NATIVE=OFF \
    -DGGML_METAL=OFF -DGGML_RPC=OFF -DLLAMA_OPENSSL=OFF -DLLAMA_CONNECT=OFF \
    -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_UI=OFF \
    -DLLAMA_USE_PREBUILT_UI=OFF -DLLAMA_BUILD_APP=OFF -DLLAMA_BUILD_SERVER=ON
cmake --build "$build/llama-out" --target llama-server --parallel 3
runner="$build/llama-out/bin/llama-server"
[[ $(lipo -archs "$runner") == arm64 ]]
"$runner" --help > "$build/llama-help.txt" 2>&1
for flag in --offline --no-agent --no-ui-mcp-proxy --no-ui --no-op-offload --reasoning --no-warmup; do
    grep -Fq -- "$flag" "$build/llama-help.txt"
done

# Build the Dock/Finder icon from the project's existing bunny mark.
iconset="$build/Frankesso.iconset"
mkdir -p "$iconset"
for size in 16 32 128 256 512; do
    sips -z "$size" "$size" "$root/assets/frankesso-favicon.png" --out "$iconset/icon_${size}x${size}.png" >/dev/null
    twice=$((size * 2))
    sips -z "$twice" "$twice" "$root/assets/frankesso-favicon.png" --out "$iconset/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$iconset" -o "$build/Frankesso.icns"

cd "$root"
"$python" -m PyInstaller --noconfirm --onedir --windowed --target-architecture arm64 \
    --name Frankesso --osx-bundle-identifier app.frankesso.desktop \
    --icon "$build/Frankesso.icns" --add-data "$root/assets:assets" \
    --workpath "$build/pyinstaller" --specpath "$build" --distpath "$build/frozen" \
    agent/macos_desktop.py
app="$build/frozen/Frankesso.app"
runtime="$app/Contents/Resources/FrankessoRuntime"
mkdir -p "$runtime/runner" "$runtime/models" "$runtime/licenses"
install -m 755 "$runner" "$runtime/runner/llama-server"
cp "$build/llama/LICENSE" "$runtime/licenses/llama.cpp.txt"
cp -R "$build/llama/licenses" "$runtime/licenses/llama-upstream"
cp "$root/LICENSE" "$root/THIRD_PARTY_NOTICES.md" "$runtime/licenses/"
"$python" -c 'import pathlib, sys; print(pathlib.Path(sys.base_prefix) / "lib/python3.13/LICENSE.txt")' |
  while IFS= read -r license; do cp "$license" "$runtime/licenses/python.txt"; done
"$python" -c 'import pathlib, PyInstaller; print(pathlib.Path(PyInstaller.__file__).parent.parent)' |
  while IFS= read -r site; do
    for license in "$site"/pyinstaller-*.dist-info/licenses/COPYING.txt "$site"/pyinstaller-*.dist-info/COPYING.txt; do
        if [[ -f $license ]]; then cp "$license" "$runtime/licenses/pyinstaller.txt"; break; fi
    done
    test -s "$runtime/licenses/pyinstaller.txt"
  done

# Use the shared spec for size and digest and exactly the Windows upstream revision.
model_url='https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/bc640142c66e1fdd12af0bd68f40445458f3869b'
model_file="$("$python" -c 'import sys; sys.path.insert(0, "agent"); from model_setup import MODEL; print(MODEL.filename)')"
curl --fail --location --retry 3 --max-time 600 --silent --show-error \
    "$model_url/$model_file" -o "$runtime/models/$model_file"
"$python" - "$runtime/models/$model_file" <<'PY'
import sys
from pathlib import Path
from threading import Event
sys.path.insert(0, "agent")
from model_setup import verify
if not verify(Path(sys.argv[1]), Event()):
    raise SystemExit("The bundled model size or SHA-256 is incorrect.")
PY
curl --fail --location --retry 3 --max-time 60 --silent --show-error \
    "$model_url/LICENSE" -o "$runtime/licenses/qwen.txt"

/usr/libexec/PlistBuddy -c 'Set :CFBundleShortVersionString 2.0.0' "$app/Contents/Info.plist" ||
    /usr/libexec/PlistBuddy -c 'Add :CFBundleShortVersionString string 2.0.0' "$app/Contents/Info.plist"
"$python" - "$app/Contents/Info.plist" <<'PYPLIST'
from pathlib import Path
import plistlib
import sys

path = Path(sys.argv[1])
with path.open("rb") as source:
    metadata = plistlib.load(source)
metadata.update(LSMinimumSystemVersion="13.0", NSRequiresAquaSystemAppearance=False)
with path.open("wb") as target:
    plistlib.dump(metadata, target)
PYPLIST
codesign --force --sign - "$runtime/runner/llama-server"
codesign --force --sign - "$app"
codesign --verify --deep --strict "$app"
[[ $(lipo -archs "$app/Contents/MacOS/Frankesso") == arm64 ]]

# Run from a space-containing launch path with an empty home. No model can be
# reused from a previous installation, and the worker must reach real Qwen.
mkdir -p "$build/Empty user home"
HOME="$build/Empty user home" "$app/Contents/MacOS/Frankesso" --smoke

out="$root/dist/macos"
mkdir -p "$out"
ln -s /Applications "$build/frozen/Applications"
hdiutil create -volname 'Frankesso' -srcfolder "$build/frozen" -fs HFS+ -format UDRO \
    "$out/Frankesso-2.0.0-macOS-arm64.dmg"
(cd "$out" && shasum -a 256 Frankesso-2.0.0-macOS-arm64.dmg > SHA256SUMS.txt)
