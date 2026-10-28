# Frankesso agent controller

An offline-first command-line companion for a local llama.cpp setup. Core tools use Python's standard library. The launcher prefers the existing Codex bundled Python, which includes pypdf and Pillow for PDF text and image metadata. It falls back to Python on PATH; no downloads or installations occur.

Run `Start Agent Preview.cmd`. It starts a separate CPU-only llama.cpp server on `127.0.0.1:18081`, then opens the interactive controller in the current console. The ordinary chat launcher and port 18080 are unchanged. Exit with `/quit`; the agent's own server is stopped. The launcher refuses to take over an occupied port.

For a source checkout, place these files in an `agent` directory. The default runtime root is its parent, containing `runner/llama-server.exe` and `models/Qwen3-4B-Q4_K_M.gguf`. Alternatively, set the private `runtime_root` in `access.json` to an existing LocalAI folder; this allows moving source into a code repository without moving model files or breaking the ordinary chat launcher. The code does not download a runner or model. Keep this machine-specific configuration untracked.

## Permissions

Private `access.json` records approved local roots. Relative paths use a temporary session sandbox; absolute paths use approved roots within existing Windows permissions. No elevation or permission changes occur. Without that file, no persistent roots are granted. `access.example.json` is a safe empty-root example for publication. The installed private configuration is separate from public-ready source.

Frankesso also reads `%LOCALAPPDATA%\Frankesso\access.json` when no sibling configuration exists. This keeps machine-specific paths and private skill locations outside the public repository. The launcher strips inherited `LLAMA_ARG_*` variables before starting the model, so ambient tool/MCP settings cannot override the controller's configured boundary.

Every write displays its destination and diff and requires the human to type `APPROVE ONCE`. Denials do not write anything. Existing text is saved beside the target with a unique `.backup-...` suffix after approval. The controller checks for changes while approval is pending. It does not offer delete, shell, browser, executable code, plugin, or arbitrary URL tools. Approval cannot be supplied as a model tool argument.

With `web_mode` set to `ask_each_request`, the web tool shows the exact query, encoded body, and destination before asking for approval. It sends at most one HTTPS POST to `https://html.duckduckgo.com/html/`. Denial occurs before DNS or connection creation. There are no cookies, environment proxies, redirects, retries, browser scripts, or source-page fetches. Returned titles and links are untrusted data. A query itself can contain private information, so inspect the exact preview before approving. Search failure leaves local tools usable. `mock` mode remains available for tests.

Live search was verified on 2026-10-28 with one explicitly approved request for `Python official documentation`, returning five titles and links. No source pages were fetched. The request record is in `WEB-TEST-REQUEST.md`. Every future search still requires its own approval. The provider can return a challenge or change its HTML format; no alternate destination is silently tried.

The model connection uses a fixed numeric loopback address without proxies or redirect following. The launcher uses `--offline --no-agent --no-ui-mcp-proxy --no-ui`; model-provided tool calls are interpreted by this controller, not executed by llama.cpp's built-in tools.

UNC paths, network shares, junctions, symlinks, reparse points, Windows device names, alternate streams, and cloud/offline placeholders are rejected. Searches are bounded to 2,000 entries, a five-second traversal budget, and 25 matches; listings return at most 100 files. These are partial results, not exhaustive drive indexing. Text reads/writes are limited to 32 KiB and returned content is limited to 6,000 characters. Content search covers small UTF-8 text files; it does not index documents.

`read_document` adds offline PDF text (up to five pages), DOCX/PPTX/XLSX and ODT/ODS/ODP extraction, BOM-aware text, ZIP member listings, image dimensions/format, and WAV duration/audio metadata. Office macros, formulas, relationships and embedded scripts are not executed; spreadsheet formulas expose cached values only. It does not render layout or edit binary documents. Extraction is bounded and may omit content. Scanned-PDF/image OCR, speech transcription, video understanding, old .doc/.xls/.ppt formats, encrypted files and arbitrary binary interpretation are unsupported. PDF and image support depend on the available local libraries. No universal-file support is claimed.

## Offline use and limitations

Private local skills can be configured with `private_skills_root` in the untracked access file. `list_skills` lists Markdown paths and `load_skill` reads one selected file locally. Reference Markdown files can be selected in the same way. The active file is reread on later user turns, so user edits are picked up without copying private contents into source. One new file can load per turn, with a 6,000-byte limit, to keep the 4096-token model context manageable. Only one selected file remains active across turns, not the whole repository. Skill text does not install hooks, execute scripts, create tools or grant permissions.

Once a session lists, loads or otherwise accesses the configured private skills tree, the controller blocks all web searches for that session before asking for approval or opening a connection. A file search covering that tree also marks the session private. A fresh agent session is required for web use without private skills. This is deliberate: reviewing a generated search query alone cannot guarantee that private preferences were not paraphrased into it. No private skill contents are included in the public source package. Local model behavior is still fallible; successful loading does not guarantee every preference will be followed.

The downloaded model is loaded from the sibling `models` folder. CPU settings preserve the prior Vulkan repair. The 4B model can make mistakes; malformed tool calls and unknown tools are rejected. Each prompt is a fresh model conversation; there is no durable conversational memory. File backups persist, but temporary session files are deleted on exit.

This is a capability-restricted controller, not an OS security boundary against malicious concurrent local processes. Do not expose its model port to a network or add unrestricted execution tools. Runtime tests restrict controller socket connections to localhost; the PC's physical internet connection was not disabled. The server's offline mode is used, rather than a system firewall rule.

## Tests

`python -B -m unittest -v test_agent test_web_search test_documents test_private_skills` exercises permissions, real-broker denial without networking, fake HTTP responses, bounded parsers, private skill isolation and synthetic fixtures. Use the existing bundled Python to include PDF and image tests; those tests skip when libraries are unavailable.

`python -B integration_test.py <LocalAI-folder>` launches the existing model and verifies actual text/document reads, denied writes, and denied real-broker web calls with temporary fixtures. It terminates only the server it started. Controller sockets are restricted to localhost during this test.

## Publication

This folder has not been pushed. Keep the private `access.json`, local logs, user data, skills, chat history, and model/runner binaries out of any public repository. The approved public project and private skills repository are separate destinations. Use a reviewed generic configuration example for publication.
