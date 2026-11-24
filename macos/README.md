# Frankesso for Apple Silicon

The Mac preview uses the same offline chat window and Qwen3-4B Q4_K_M as Windows. The Mac bundle targets Apple Silicon with macOS 13 or later. The disk image contains the model, runner, and chat app. It does not fetch a model, accept an account, offer model import, or make model traffic leave the device. The Python app accepts only the fixed process-local address and the native runner is built without optional network features. This is an application restriction, not a macOS network sandbox.

Chats and notes are stored in `~/Library/Application Support/Frankesso/chat-state`, outside the app. The preview is ad hoc signed, not Developer ID signed or notarized. It is a developer test artifact, not ready for public distribution.

## Build and verify

The [macOS preview workflow](../.github/workflows/macos-preview.yml) builds on an Apple Silicon runner and uploads the disk image only if verification passes. The runner checks package architecture and signature, loads both chat themes, confirms Python rejects external addresses before connecting, and sends a real question to the bundled Qwen from an empty profile. Bring-up on a personal Mac and Finder drag-and-drop are manual preview checks.

To build locally on an Apple Silicon Mac with CMake and an ARM64 Python 3.13 with Tk, run `bash macos/build-macos.sh` from this checkout. Build-only package and model downloads are verified where pinned and are not part of app startup. Set `FRANKESSO_BUILD_PYTHON` if the build interpreter is not installed in the standard Python.org framework location.
