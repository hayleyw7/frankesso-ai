# Frankesso

An offline-first Windows assistant for an existing llama.cpp and Qwen3-4B setup, with explicit approval for every file edit and web search. It runs the model locally and uses no paid model API.

See [setup, capabilities and limits](agent/README.md), [test evidence](agent/TEST-RESULTS.md), and the [approved live-search test](agent/WEB-TEST-REQUEST.md).

## Start locally

1. Existing installations can run `Start Frankesso.cmd`. Private configuration stays outside the repository at `%LOCALAPPDATA%\Frankesso\access.json`.
2. For a new installation, use `agent/access.example.json` as a starting point and set `runtime_root` to the existing folder containing `runner/llama-server.exe` and `models/Qwen3-4B-Q4_K_M.gguf`. No runner, model, package, or driver is downloaded automatically. Empty `approved_local_roots` grants only temporary sandbox access.
3. The optional `private_skills_root` points to user-owned local Markdown skills. Accessing them disables web search for that session. Every file edit requires a separate approval.

Python on PATH supports core functions. The launcher prefers an existing Codex bundled Python when available for PDF and image readers. Those readers need `pypdf` and Pillow in other environments. No dependency installation runs automatically.

## Scope

Frankesso supports bounded local text search, text edits with previews and backups, document text extraction, and one-at-a-time approved web searches. It has no shell, browser automation, arbitrary code execution, or automatic publishing tool. A 4B model can make mistakes, and some document formats are unsupported. See the detailed guide for limits and verified behavior.

This repository excludes model/runner binaries, machine-specific access configuration, private skills, user files, credentials, and chat logs. It does not vendor third-party skill repositories. Model and runtime licenses remain with their respective distributions.
