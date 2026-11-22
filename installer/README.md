# Windows installer build and verification

The draft installer targets native x64 Windows 10/11 on AVX2-capable processors. It is per-user, unsigned, and not a release. The GitHub Actions workflow creates an installer artifact for testing only, plus SHA256SUMS.txt. It does not publish tags or releases.

The Windows build uses the pinned [Python 3.13.16 Windows distribution](https://www.python.org/downloads/release/python-31316/) and its published SHA-256, a static CPU build from the [upstream llama.cpp b11865 commit](https://github.com/ggml-org/llama.cpp/attestations/59465966), and [Inno Setup 6.7.4](https://jrsoftware.org/inno-setup/downloads) checked against its publisher signature. Visual Studio 2022 and CMake run only on the builder. The [official Qwen quantization](https://huggingface.co/Qwen/Qwen3-4B-GGUF/blob/bc640142c66e1fdd12af0bd68f40445458f3869b/Qwen3-4B-Q4_K_M.gguf) is downloaded by the app only after the user chooses Download model.

## Before shipping

1. Get a passing build and clean install/uninstall workflow from Windows. Do not use an unsigned PR artifact as a public release.
2. Run the full-model check and verify the downloaded model, one genuine local reply, and clean startup/shutdown with the bundled executables.
3. On a fresh standard Windows x64 user profile without Python/Git or the model, open Setup, search **Frankesso** in Start, and confirm the bunny icon launches the app. Confirm the model prompt is opt-in, try cancel/retry, and verify no model is left on cancel.
4. Download the model, disconnect networking, and verify two replies and a new chat. Confirm the installed app shuts down only its own local runner, cannot take over an occupied port, and relaunches once the other process closes.
5. Uninstall through Windows **Installed apps** and check that the app, shortcut, and downloaded model are removed while the source-only CLI is unaffected. Assess signing before any public distribution; do not ask users to disable security warnings or protection.


## Windows / Android chat parity

When changing the UI, check both platforms: cream #FAF2E4 and near-black #0A0909, swapped in dark mode; crimson #B64147 stays in the bunny artwork. The app silently follows the system appearance on launch and while open (light fallback if Windows has no readable app theme). There is no app Settings entry or appearance override, and old appearance-only preference files are ignored without being deleted. Theme changes must preserve the transcript, composer, and any reply in progress. Native title and system bars remain platform-owned.

The exact standalone test reply uses the same on-screen reveal as an ordinary response. The first chunk appears on the first render tick after a reply is available, followed by four Unicode code points each 30 ms. Windows reveals the reply after the local model has returned; Stop during reveal keeps the displayed portion out of history. Verify this along with the fixed text, offline inference, and chat/memory behavior.

For button parity, compare enabled and model-download-disabled rows in both palettes: 10 dp corners, 48 dp height, equal action height/width, 8 dp pair gap, solid primary, outlined secondary, and a muted solid disabled outline at 30% foreground and readable disabled label at 70% foreground. The Windows CI optionally saves isolated screenshots of those synthetic controls as the windows-button-smoke artifact; system-window capture support varies on hosted runners.

The transcript and draft composer use the same rounded chat surfaces as Android. Check that text selection and focus still work and the transcript scrolls inside the outline at smaller widths.

The full bunny in the chat header uses the shared transparent dark artwork when needed, with no tile in either theme. The native app and Start menu icons are separate.

The initial Download model action uses the same rounded primary image and focus treatment as Send. CI captures it beside enabled and disabled chat actions.
