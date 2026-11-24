# Frankesso for Android

Frankesso v2 for Android is **offline-only**. The text chat app runs its bundled model on **64-bit ARM phones with Android 8.0 or newer**. Android blocks the app from opening internet connections because the APK does not request the `INTERNET` permission. No account, separate model download, or root access is required.

## Install and chat

1. Download and install the APK. It is roughly 500 MB because the model is included. The GitHub Actions test artifact is a direct debug APK download for signed-in GitHub users, not a production distribution.
2. Open **Frankesso** from the app launcher. On first launch, it prepares and verifies its bundled model automatically, with progress. No model picker, separate download, or import is needed. The initial private model copy needs **at least 525 MB free after installing**; if storage is low, free some space and tap **Retry setup**.
3. Start chatting when the status says **Ready.** Replies appear as they’re generated. Tap **Stop** to end a reply; a one-minute limit protects against a slow or stalled generation. **New chat** clears the visible transcript and in-memory context. Chats are not synced or saved; the small model can get answers wrong and uses a short context. Desktop file tools are not included.

The workflow skips the Android emulator test when the runner cannot access KVM. A passing build with that warning does not verify launch or chat on Android; use the airplane-mode phone check below.

Debug builds from independent CI runners may have different signing certificates and may not update an existing debug installation in place. This workflow is for development verification, not a public download or signed production update channel.

The app uses the Windows chat layout: status above the transcript, a separate multiline **Message** field, and **New chat** and **Send** underneath. On a physical keyboard, Enter sends and Shift+Enter inserts a line break. On a phone keyboard, use the **Send** button.

## Build

Use JDK 17, Gradle 8.11.1, Python 3.8 or newer, and the Android SDK (platform 35, build tools 35.0.0, NDK 29.0.14206865 and CMake 3.31.5). Set `ANDROID_HOME` to the SDK. Allow 4 GB of Java heap for packaging the model asset. The first build needs access to the official Gradle repositories, GitHub, and Hugging Face. For build machines with the exact model already downloaded, set `FRANKESSO_MODEL_FILE` to its path; the build still checks its SHA-256 before packaging.

From the repository root:

```sh
bash android/tests/run-host-checks.sh
gradle -p android :app:assembleDebug :app:lintDebug
python3 android/scripts/bundled_model.py verify-apk android/app/build/outputs/apk/debug/app-debug.apk
```

## Verify on a fresh phone

1. Install the debug APK on an ARM64 test phone without Frankesso app data. Turn on airplane mode and turn Wi-Fi off **before opening it for the first time**, so the test verifies a genuinely offline first launch.
2. Open **Frankesso** from the launcher. Observe **Preparing offline chat**, then **Ready.** without any account, import, or download prompt. Ask a new ordinary question, such as “Suggest a name for a tiny herb garden.” A generated reply, not the deterministic `test` response, verifies local inference.
3. Ask for a longer answer and tap **Stop** when text starts appearing. Verify the partial reply stays visible and a new message can be sent. Force-stop and reopen while offline, send another ordinary question, and confirm the app reuses its prepared model. On a separate low-storage test device, check that first launch explains the space required and that Retry succeeds after space is available.

## Included components

The APK includes the unmodified [official Qwen2.5 0.5B Instruct Q4_K_M GGUF](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/blob/9217f5db79a29953eb74d5343926648285ec7e67/qwen2.5-0.5b-instruct-q4_k_m.gguf) (491,400,032 bytes), under [Apache-2.0](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/blob/9217f5db79a29953eb74d5343926648285ec7e67/LICENSE). It compiles [llama.cpp](https://github.com/ggml-org/llama.cpp/tree/78a8ae14be559b45f5f13ddee82c188b683d5d8d) into one local native runtime. The license and attribution files ship in the APK under `assets/third-party/`.
