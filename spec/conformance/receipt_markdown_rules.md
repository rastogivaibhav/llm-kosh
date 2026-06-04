# Receipt Markdown Rules

The `MEMORY_RECEIPT.md` file returned by the LLM must follow strict structural rules to be safely parsed by LlmKosh.

## Grammar

- Must contain zero or more headers, matching exact strings (case-insensitive):
  - `# New decisions`
  - `# Corrections`
  - `# Generated files`
  - `# Open gaps`
  - `# Suggested memory updates`
- Beneath each header, list items begin with `- ` or `* `.
- Items contain a title and body separated by `::`, or just a title if no `::` exists.
- Items may contain tags like `[project: Name]` or `[ref: <memory_id>]`.
- `[ref: id]` is mandatory for corrections.
