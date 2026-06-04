# Import Architecture

LlmKosh supports importing external conversational data (ChatGPT, Claude, Gemini, Generic) through a hardened transaction system.

## The Process

1. **Detect**: Identifies the payload origin without moving files.
2. **Preview**: Scans files to calculate totals (conversations, messages, parsed elements) and detects deduplication conflicts via `source_hash`.
3. **Apply**: 
   - Generates a unique transaction `import_id`.
   - Copies raw payloads unmodified into `attachments/imports/<import_id>/`.
   - Normalizes data into individual JSON bodies inside LlmKosh Memory records under `kind: conversation`.
   - Writes the transaction ID and related `record_ids` into the `reports/imports.json` ledger.
4. **Rollback**: Uses the transaction ledger to find all generated records and marks their status as `superseded`. It does NOT destroy the raw payload, ensuring non-destructive behavior.

## Normalization Format

All conversational imports compile down to a universal format:

```json
{
  "provider": "chatgpt",
  "conversation_id": "uuid-1234",
  "title": "A Conversation",
  "created_at": "timestamp",
  "messages": [
    {"role": "user", "text": "hello", "time": "timestamp"},
    {"role": "assistant", "text": "hi", "time": "timestamp"}
  ],
  "source_hash": "sha256-hash-of-original-zip"
}
```

## Supported Commands

- `llm-kosh import detect <path>`
- `llm-kosh import preview <path>`
- `llm-kosh import apply <path>`
- `llm-kosh import rollback <import_id>`
- `llm-kosh import list`
- `llm-kosh import show <import_id>`
- `llm-kosh import report <import_id>`
