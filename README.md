# Frankesso
<img src="assets/frankesso-logo.png" alt="Frankesso AI coffee bunny logo" align="right" width="160">

Frankesso v2 is **offline-only** on Windows desktop, Windows terminal, and Android. Chats run on your device, with no web search, telemetry, cloud fallback, or in-app model downloads.

Frankesso supports bounded local text search, text edits with previews and backups, and document text extraction. Every file edit requires explicit approval. It has no shell, browser automation, arbitrary code execution, or automatic publishing tool.

## Platform roadmap

- **Available now:** Windows.
- **Planned:** Linux, Android, macOS, and iOS.

## Windows desktop app

Frankesso v2's Windows x64 installer is in development and not released. Once the release is available, run `Frankesso-2.0.0-Windows-x64-Setup.exe` and open **Frankesso** from Start. Setup is for the current Windows user and bundles Python, Tk, and the CPU model runner. No admin access, Git, separate Python, or terminal setup is required. The installer requires an AVX2-capable x64 processor. Native ARM64 and 32-bit Windows are not supported.

Before first use, obtain the [pinned Qwen3-4B GGUF model](https://huggingface.co/Qwen/Qwen3-4B-GGUF/blob/bc640142c66e1fdd12af0bd68f40445458f3869b/Qwen3-4B-Q4_K_M.gguf) (2.5 GB) separately in your browser, or copy it from local storage. Open Frankesso, paste the full local file path, and choose **Import model**. The app verifies the model before using it. Import works without a connection. Desktop chat is text-only. The separate CLI retains approved local file tools. Uninstalling removes the desktop app, Start shortcut, and its imported model without touching your original file or separate CLI setup.

## Developer setup and command-line tools

1. Keep the repository's folder structure intact. You need an existing runtime folder containing `runner/llama-server.exe` and `models/Qwen3-4B-Q4_K_M.gguf`, plus a local Python interpreter. No runner, model, package, or driver is downloaded automatically.
2. For a new installation, copy [agent/access.example.json](agent/access.example.json) to `%LOCALAPPDATA%\Frankesso\access.json`. Set `runtime_root` to the existing runtime folder; an empty value defaults to the repository root. Keep this machine-specific file outside the repository.
3. Add only the local folders you want Frankesso to access to `approved_local_roots`. Leaving it empty grants only temporary sandbox access. The optional `private_skills_root` points to user-owned local Markdown skills. Sessions accessing those skills are excluded from saved chat history.
4. Run `Start Frankesso.cmd` from the repository root. Exit with `/quit`.

Existing installations can keep their private configuration and use the same `Start Frankesso.cmd` entry point. A legacy `agent/access.json`, if present, takes precedence over `%LOCALAPPDATA%\Frankesso\access.json`; keep it untracked too.

The launcher prefers an existing Codex bundled Python and falls back to `python` on PATH. Core tools use Python's standard library; PDF text extraction requires `pypdf`, and image metadata requires Pillow, in the selected interpreter. No dependency installation runs automatically.

The launcher starts a separate CPU-only llama.cpp server on `127.0.0.1:18081` and opens the interactive controller in the current console. It refuses to take over an occupied port and stops only its own server on exit. An existing ordinary chat launcher and port 18080 are unchanged. See the [test evidence](agent/TEST-RESULTS.md) for the runtime version previously verified.

## Local chat history & memory

In desktop chat and the CLI, type `Remember this: I label herb pots in teal.` to save a note. Type `/memories` to see saved notes, and `Forget <note ID or exact text>` to remove one. Frankesso does not save notes automatically. Use `/chats`, `/open <ID>`, `/new`, and `/delete <ID>` to inspect, reopen, start, or delete local chats. Forgetting a note does not erase old chats that mention it; deleting a chat does not remove separate notes.

Use `Let's talk:` to discuss an idea or `Just the diff:` to see a proposed patch without editing a file. The GUI always runs text-only. CLI turns that use tools or follow loading private skills are not recorded.

Chats and notes are ordinary unencrypted files local to this Windows account. Uninstall removes the app and model but keeps separate chat and note data so it stays available for the CLI or a reinstall. To remove it, delete the relevant chats and notes from Frankesso. The local data folder is `%LOCALAPPDATA%\Frankesso\chat-state`.

## File access and approvals

Private `access.json` records approved local roots. Relative paths use a temporary session sandbox; absolute paths use approved roots within existing Windows permissions. Without a configuration file, no persistent roots are granted. No elevation or permission changes occur.

Every write displays its destination and diff and requires the human to type `APPROVE ONCE`. Denials do not write anything. Existing text is saved beside the target with a unique `.backup-...` suffix after approval. The controller checks for changes while approval is pending. Approval cannot be supplied as a model tool argument.

UNC paths, network shares, junctions, symlinks, reparse points, Windows device names, alternate streams, and cloud/offline placeholders are rejected. There are no delete, shell, browser, executable-code, plugin, or arbitrary-URL tools.

File searches are bounded to 2,000 entries, a five-second traversal budget, and 25 matches; listings return at most 100 files. These are partial results, not exhaustive drive indexing. Plain-text reads and writes are limited to 32 KiB, with returned text limited to 6,000 characters. Content search covers small UTF-8 text files; it does not index documents.

## Document support

`read_document` provides bounded offline extraction:

| Format | Support |
| --- | --- |
| PDF | Text layer from at most five pages; requires `pypdf` |
| DOCX, PPTX, XLSX | Text extraction; spreadsheet formulas expose cached values only |
| ODT, ODS, ODP | Text extraction |
| Supported text files | BOM-aware text reading |
| ZIP | First 100 member names and sizes; nothing extracted or executed |
| Images | Dimensions, format, and mode only; requires Pillow |
| WAV | Duration, channels, and sample rate only |

Extraction is bounded and may omit content. It does not render layout or edit binary documents. Office macros, formulas, external relationships, and embedded scripts are not executed. Scanned-PDF/image OCR, speech transcription, video understanding, old `.doc`/`.xls`/`.ppt` formats, encrypted files, and arbitrary binary interpretation are unsupported. PDF and image support depend on the available local libraries; no universal-file support is claimed.

## Private local skills

Set `private_skills_root` in the untracked access file to a user-owned local Markdown skills folder. `list_skills` lists Markdown paths and `load_skill` reads one selected file locally. Reference Markdown files can be selected in the same way. The active file is reread on later user turns, so user edits are picked up without copying private contents into source.

One new file can load per turn, with a 6,000-byte limit to keep the 4096-token model context manageable. Only one selected file remains active across turns, not the whole repository. Skill text does not install hooks, execute scripts, create tools, or grant permissions.

Sessions that access the private skills tree are excluded from saved chat context. A file search covering that tree also marks the session private.

## Offline behavior and limitations

The Windows controller allows Python socket operations only for its same-device model at `127.0.0.1:18081`. It does not use proxies, DNS hostnames, or redirects. The runner binds to loopback with `--offline --no-agent --no-ui-mcp-proxy --no-ui`, and the launcher strips inherited `LLAMA_ARG_*` settings. Windows file tools and model import reject UNC paths, mapped network drives, and reparse points.

The 4B model can make mistakes; malformed tool calls and unknown tools are rejected. Only the current request can authorize tool planning. Saved chat context is available solely for text-only replies. The CLI reloads a selected private skill when applicable. File backups persist, but temporary session files are deleted on exit.

The Windows restriction is enforced within the application, not by a system firewall. It does not isolate a modified native runner, unrelated apps, or the operating system. Do not expose the model port to a network. The Android package has no internet permission and the build rejects any requested permissions.

## Tests

Run these commands on Windows, from the repository root:

```cmd
cd agent
python -B -m unittest -v test_agent test_local_only test_documents test_private_skills test_desktop test_model_setup test_chat_state
```

The suite exercises permissions, real-broker denial without networking, fake HTTP responses, bounded parsers, private-skill isolation, and synthetic fixtures. Use the existing bundled Python, or another interpreter with `pypdf` and Pillow, to include PDF and image tests; those tests skip when the libraries are unavailable. The absolute-path permission test targets Windows path semantics, not POSIX paths.

The [Windows installer workflow](.github/workflows/windows-installer.yml) builds an unsigned test artifact and runs install/Start shortcut/uninstall checks in a separate Windows runner. The full-model check fetches the fixture outside the installed app, then verifies local import and on-device inference. See [installer verification](installer/README.md) for the Windows release gate. A source checkout can still launch the developer desktop preview using `Install Frankesso Desktop.cmd` after setting up a local Python with Tkinter and the runtime; that's not the v2 installer.

From the same `agent` directory, run the actual-model integration test with the path to your existing runtime folder:

```cmd
python -B integration_test.py "C:\path\to\LocalAI"
```

It launches the existing model and verifies text/document reads, denied writes, and rejection of the removed web tool with temporary fixtures. It terminates only the server it started. Controller sockets are restricted to localhost during this test. The placeholder path above must be replaced with your runtime folder.

See [test evidence](agent/TEST-RESULTS.md) for the recorded results and verification limits, and the [live-search request record](agent/WEB-TEST-REQUEST.md) for the separately approved network test.

## Repository contents

This is the public source repository. Keep machine-specific `access.json`, local logs, user data, private skills, credentials, chat history, and model/runner binaries out of it. The repository provides a generic [configuration example](agent/access.example.json), not private configuration or skill contents. It does not vendor third-party skill repositories. The public project and any private skills repository are separate destinations.

## License

<img src="assets/frankesso-favicon.png" alt="Frankesso AI bunny favicon" align="left" width="64">

Frankesso's original source code and documentation are available under the [MIT License](LICENSE). You may use, modify, and redistribute them, including commercially, provided the copyright and license notices are retained. The software is provided without warranty.

Separately installed models, runtimes, libraries, private skills, and user data are not covered by this grant. See [third-party components](THIRD_PARTY_NOTICES.md) for upstream license references.
