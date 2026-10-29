# Frankesso

An offline-first Windows command-line assistant for an existing llama.cpp and Qwen3-4B setup, with explicit approval for every file edit and web search. It runs the model locally and uses no paid model API.

Frankesso supports bounded local text search, text edits with previews and backups, document text extraction, and one-at-a-time approved web searches. It has no shell, browser automation, arbitrary code execution, or automatic publishing tool.

## Start locally

1. Keep the repository's folder structure intact. You need an existing runtime folder containing `runner/llama-server.exe` and `models/Qwen3-4B-Q4_K_M.gguf`, plus a local Python interpreter. No runner, model, package, or driver is downloaded automatically.
2. For a new installation, copy [agent/access.example.json](agent/access.example.json) to `%LOCALAPPDATA%\Frankesso\access.json`. Set `runtime_root` to the existing runtime folder; an empty value defaults to the repository root. Keep this machine-specific file outside the repository.
3. Add only the local folders you want Frankesso to access to `approved_local_roots`. Leaving it empty grants only temporary sandbox access. The optional `private_skills_root` points to user-owned local Markdown skills; accessing them disables web search for that session.
4. Run `Start Frankesso.cmd` from the repository root. Exit with `/quit`.

Existing installations can keep their private configuration and use the same `Start Frankesso.cmd` entry point. A legacy `agent/access.json`, if present, takes precedence over `%LOCALAPPDATA%\Frankesso\access.json`; keep it untracked too.

The launcher prefers an existing Codex bundled Python and falls back to `python` on PATH. Core tools use Python's standard library; PDF text extraction requires `pypdf`, and image metadata requires Pillow, in the selected interpreter. No dependency installation runs automatically.

The launcher starts a separate CPU-only llama.cpp server on `127.0.0.1:18081` and opens the interactive controller in the current console. It refuses to take over an occupied port and stops only its own server on exit. An existing ordinary chat launcher and port 18080 are unchanged. See the [test evidence](agent/TEST-RESULTS.md) for the runtime version previously verified.

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

## Web search

With `web_mode` set to `ask_each_request`, the web tool shows the exact query, encoded body, and destination before asking for approval. It sends at most one HTTPS POST to `https://html.duckduckgo.com/html/`. Denial occurs before DNS or connection creation. There are no cookies, environment proxies, redirects, retries, browser scripts, or source-page fetches. `mock` mode remains available for tests.

The request exposes the query, standard HTTPS headers, and the requesting computer's public IP. No files or chat history are attached, but the query itself can contain private information: inspect the exact preview before approving. Returned titles and links are untrusted data. Search failure leaves local tools usable.

Live search was verified on 2026-10-28 with one explicitly approved request for `Python official documentation`, returning five titles and links. No source pages were fetched. See the [approved live-search test](agent/WEB-TEST-REQUEST.md). That approval is consumed; every future search requires its own approval. The provider can return a challenge or change its HTML format, and no alternate destination is silently tried.

## Private local skills

Set `private_skills_root` in the untracked access file to a user-owned local Markdown skills folder. `list_skills` lists Markdown paths and `load_skill` reads one selected file locally. Reference Markdown files can be selected in the same way. The active file is reread on later user turns, so user edits are picked up without copying private contents into source.

One new file can load per turn, with a 6,000-byte limit to keep the 4096-token model context manageable. Only one selected file remains active across turns, not the whole repository. Skill text does not install hooks, execute scripts, create tools, or grant permissions.

Once a session lists, loads, or otherwise accesses the configured private skills tree, the controller blocks all web searches for that session before asking for approval or opening a connection. A file search covering that tree also marks the session private. Start a fresh session without accessing private skills to use web search again. This is deliberate: reviewing a generated search query alone cannot guarantee that private preferences were not paraphrased into it. Local model behavior is still fallible; successful loading does not guarantee every preference will be followed.

## Offline behavior and limitations

The model connection uses a fixed numeric loopback address without proxies or redirect following. The launcher strips inherited `LLAMA_ARG_*` variables and uses `--offline --no-agent --no-ui-mcp-proxy --no-ui`; model-provided tool calls are interpreted by this controller, not executed by llama.cpp's built-in tools.

The 4B model can make mistakes; malformed tool calls and unknown tools are rejected. Each prompt is a fresh model conversation, with the selected private skill reloaded when applicable. There is no durable conversational memory. File backups persist, but temporary session files are deleted on exit.

This is a capability-restricted controller, not an OS security boundary against malicious concurrent local processes. Do not expose its model port to a network or add unrestricted execution tools. Recorded runtime tests restricted controller socket connections to localhost; the PC's physical internet connection was not disabled. The server's offline mode is used, rather than a system firewall rule.

## Tests

Run these commands on Windows, from the repository root:

```cmd
cd agent
python -B -m unittest -v test_agent test_web_search test_documents test_private_skills
```

The suite exercises permissions, real-broker denial without networking, fake HTTP responses, bounded parsers, private-skill isolation, and synthetic fixtures. Use the existing bundled Python, or another interpreter with `pypdf` and Pillow, to include PDF and image tests; those tests skip when the libraries are unavailable. The absolute-path permission test targets Windows path semantics, not POSIX paths.

From the same `agent` directory, run the actual-model integration test with the path to your existing runtime folder:

```cmd
python -B integration_test.py "C:\path\to\LocalAI"
```

It launches the existing model and verifies text/document reads, denied writes, and denied real-broker web calls with temporary fixtures. It terminates only the server it started. Controller sockets are restricted to localhost during this test. The placeholder path above must be replaced with your runtime folder.

See [test evidence](agent/TEST-RESULTS.md) for the recorded results and verification limits, and the [live-search request record](agent/WEB-TEST-REQUEST.md) for the separately approved network test.

## Repository contents

This is the public source repository. Keep machine-specific `access.json`, local logs, user data, private skills, credentials, chat history, and model/runner binaries out of it. The repository provides a generic [configuration example](agent/access.example.json), not private configuration or skill contents. It does not vendor third-party skill repositories. The public project and any private skills repository are separate destinations.

## License

Frankesso's original source code and documentation are available under the [MIT License](LICENSE). You may use, modify, and redistribute them, including commercially, provided the copyright and license notices are retained. The software is provided without warranty.

Separately installed models, runtimes, libraries, private skills, and user data are not covered by this grant. See [third-party components](THIRD_PARTY_NOTICES.md) for upstream license references.
