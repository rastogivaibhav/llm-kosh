# Developer FAQ

This page answers the questions that come up most often when wiring up a
cartridge, debugging the MCP server, or deciding whether to use the service or
daemon runtime.

## 1. What is the root repo?

The root repo is the Git checkout you are working in now:

`C:\Users\vrast\Documents\Projects\test\ai_memory_cartridge_v1.0`

Inside that repo, the cartridge root is a separate concept. It is the folder
that stores the live memory cartridge state for a specific installation.

## 2. How do I set the root folder?

You can set it in one of three ways:

- pass `--root` on the command line
- set the `LLMKOSH_ROOT` environment variable
- run `llm-kosh init` after pointing at the folder you want to use

Typical examples:

```powershell
llm-kosh --root .\my-cartridge init
llm-kosh --root .\my-cartridge status
```

If you do not pass a root, the tooling falls back to the configured default
cartridge root.

## 3. Can I drop files into the root and have them processed asynchronously?

Not directly into the root itself. The current runtime processes files from the
cartridge intake surfaces, mainly:

- `receipts/`
- `intake/`

If watchdog support is installed, the service can notice changes there and
process them in the background. That is the supported “drop a file and let it
process” flow.

For a raw file you want absorbed, place it in the cartridge intake path instead
of the root directory.

## 4. Can it listen to Claude Code folders, Antigravity folders, or other external folders?

Yes.

The service watches the cartridge’s own intake folders, and it can also watch
extra folders listed in `[daemon].watched_directories` when `watchdog` is
available. That is the right place to point editor export folders, automation
drop zones, or other external sources you want ingested automatically.

If you are using the legacy foreground daemon, the same watched-folder concept
is available there too.

## 5. How do I feed information into the system?

Common ingestion paths are:

- `llm-kosh add`
- `llm-kosh inbox`
- `llm-kosh ingest`
- `llm-kosh intake`
- `llm-kosh receipt`

From MCP, the corresponding receipt and intake tools are the preferred way to
submit memory. The important idea is that everything should land in a traceable
receipt or intake record so the ledger stays auditable.

## 6. How do I configure daemons for this project?

There are two layers:

- the modern service runtime, which is what we recommend for day-to-day use
- the legacy daemon runtime, which still supports additional watch policies

If you need the service installed as an OS background job, use the installer or
the `service` commands.

If you need external-folder watching, configure the daemon policy with watched
directories and make sure the folders are accessible to the process account.

## 7. How do I troubleshoot MCP errors?

Start with the quickest checks:

```powershell
llm-kosh --root .\my-cartridge mcp-test
llm-kosh --root .\my-cartridge mcp-tools
python -m json.tool server.json
```

Then verify:

- the cartridge root exists and is initialized
- the MCP config points at the current project
- the server manifest and version match the repo state
- any required environment variables are present

If the server fails to publish or authenticate, check the token scope and
expiry first. If the server starts but tools are missing, compare the manifest
with the registered MCP tools.

## 8. How do I uninstall?

Use the project’s uninstall flow rather than deleting files by hand:

```powershell
llm-kosh uninstall --yes
```

If the OS service was installed, the uninstaller should remove that too. If you
used a custom cartridge folder, back it up first if you want to preserve data.

## 9. How do I extract memory via MCP or otherwise?

Use MCP for structured extraction when you are inside a tool-enabled client.
Use the CLI when you want to work directly on files or exports.

The cleanest pattern is:

1. capture the source material
2. convert it into a receipt or intake artifact
3. absorb it into the cartridge
4. verify the resulting memory state with `status` or search commands

## 10. What prompt should I use to ask for receipts in Gemini or another tool?

A good reusable prompt is:

> Extract the important facts from this conversation as a memory receipt. Keep it concise, factual, and timestamped. Include decisions, open questions, file paths, commands, and any follow-up actions that should be preserved for future work. Return the result as a Markdown receipt suitable for ingestion.

If you want a more structured version, add:

> Use headings for context, decisions, actions, risks, and next steps.

## 11. What is developer experience?

Developer experience is how easy the project feels to understand, run, debug, and
extend.

For this repo, good developer experience means:

- one obvious cartridge root
- predictable install and uninstall flows
- clear MCP and service troubleshooting commands
- a small set of supported runtime modes
- docs that explain what is supported today versus what is only available in
  legacy compatibility paths

In short: if a new contributor can install, ingest, debug, and publish without
guessing, the developer experience is good.
