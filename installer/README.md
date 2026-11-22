# Windows installer build and verification

The draft installer targets native x64 Windows 10/11. It is per-user, unsigned, and not a release. The GitHub Actions workflow creates an installer artifact for testing only, plus SHA256SUMS.txt. It does not publish tags or releases.

The Windows build uses the pinned [Python 3.13.16 Windows distribution](https://www.python.org/downloads/release/python-31316/) and its published SHA-256, a static CPU build from the [upstream llama.cpp b11865 commit](https://github.com/ggml-org/llama.cpp/attestations/59465966), and [Inno Setup 6.7.4](https://jrsoftware.org/inno-setup/downloads) checked against its publisher signature. Visual Studio 2022 and CMake run only on the builder. The [official Qwen quantization](https://huggingface.co/Qwen/Qwen3-4B-GGUF/blob/bc640142c66e1fdd12af0bd68f40445458f3869b/Qwen3-4B-Q4_K_M.gguf) is downloaded by the app only after the user chooses Download model.

## Before shipping

1. Get a passing build and clean install/uninstall workflow from Windows. Do not use an unsigned PR artifact as a public release.
2. Run the full-model check and verify the downloaded model, one genuine local reply, and clean startup/shutdown with the bundled executables.
3. On a fresh standard Windows x64 user profile without Python/Git or the model, open Setup, search **Frankesso** in Start, and confirm the bunny icon launches the app. Confirm the model prompt is opt-in, try cancel/retry, and verify no model is left on cancel.
4. Download the model, disconnect networking, and verify two replies and a new chat. Confirm the installed app shuts down only its own local runner, cannot take over an occupied port, and relaunches once the other process closes.
5. Uninstall through Windows **Installed apps** and check that the app, shortcut, and downloaded model are removed while the source-only CLI is unaffected. Assess signing before any public distribution; do not ask users to disable security warnings or protection.
