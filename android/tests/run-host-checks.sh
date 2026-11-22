#!/usr/bin/env bash
set -eu
cd -- "$(dirname -- "$0")/.."
check_dir="$(mktemp -d)"
trap 'rm -rf -- "$check_dir"' EXIT
java_dir=app/src/main/java/app/frankesso/android
if command -v javac >/dev/null; then
    compiler=(javac --release 17)
else
    compiler=(java -m jdk.compiler/com.sun.tools.javac.Main -source 17 -target 17)
fi
"${compiler[@]}" -d "$check_dir" "$java_dir/ModelImport.java" "$java_dir/ChatPrompt.java" "$java_dir/LocalReply.java" tests/AndroidHostChecks.java
java -cp "$check_dir" app.frankesso.android.AndroidHostChecks
