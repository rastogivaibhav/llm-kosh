# Pack Conformance Standard

The `.koushpack.zip` is a portable AI context artifact designed to be universally readable by LLMs. To allow external tools, agents, or SaaS platforms to parse and generate these packs reliably, Koush enforces a **Level 0 to Level 3** conformance scale.

## Pack Levels

### Level 0: Human-Readable Boot Pack
The absolute bare minimum required for an LLM to understand what to do.
- `01_BOOT.md`: Explicit boot sequence instructions.
- `11_MANIFEST.json`: Identifies the schema version, target, and query.
- `12_MEMORY_RECEIPT_TEMPLATE.md`: The output grammar you expect the LLM to write back.

### Level 1: Source Mapped Pack
Contains actual user memory mapped predictably.
- Requirements of Level 0
- `10_SOURCE_MAP.json`: Relational mapping of internal IDs to the provided files.
- Files matching the paths dictated in `10_SOURCE_MAP.json` must exist inside the pack.

### Level 2: Provider Projection Pack
A tailored pack intended to be used over an API.
- Requirements of Level 1
- Provider-specific files (e.g., `provider/CHATGPT_CONTEXT.md`).
- Explicit budget or redaction metadata in the manifest.

### Level 3: Signed & Provenance Pack
(Future) Guaranteed integrity.
- Requirements of Level 2
- Includes content hashes tying memories to the ledger.
- (Optional) cryptographic signatures.

## How Another Tool Can Support Koush Packs

Third party integrations can interact with Koush by adopting this standard:

1. **Ingest a Koush Pack:**
   Parse `11_MANIFEST.json` and read the `10_SOURCE_MAP.json` to understand the provided state without needing to grep through markdown.
   
2. **Generate a Koush Pack:**
   If your system outputs context, generate a ZIP adhering to Level 1. Ensure you include `01_BOOT.md` and a receipt template, so if the pack is uploaded manually to an LLM, the output can seamlessly round-trip back to Koush.

## Testing Conformance
Run `koush conformance generate-sample` to build reference packs locally.
Run `koush conformance pack <pack.zip>` to test an external pack for validity against the specs.
