# Koush Boot Instructions

You are reading a portable AI memory cartridge or a focused context pack exported from one.

## How to use this pack

1. Read `MANIFEST.json` first if present.
2. Read `02_CONTEXT_BRIEF.md` next.
3. Use `03_MATCHED_MEMORY.md`, `04_DECISIONS.md`, and `05_SOURCE_MAP.json` as the working source.
4. Do not assume missing systems, files, services, or prior decisions exist.
5. Preserve existing decisions unless the user explicitly asks you to change them.
6. At the end of substantial work, return a `MEMORY_RECEIPT` section so the user can
   absorb your output back into their cartridge.

## MEMORY_RECEIPT format (grammar the absorber understands)

```markdown
# MEMORY_RECEIPT

## New decisions
- Short title :: Optional longer body explaining the decision [project: Name]

## Corrections
- What was wrong and what is now true [ref: <existing-memory-id>]

## Generated files
- filename.ext :: what it is / where it lives

## Open gaps
- Something still unresolved

## Suggested memory updates
- A non-binding suggestion for the owner to consider
```

Notes for the model:
- `::` separates a short title from a longer body. If you omit it, the whole line is used.
- `[project: Name]` attaches the item to a project.
- `[ref: <id>]` in a Correction names the exact memory it corrects, so absorb can
  retire it deterministically. If you do not know the id, just describe the correction
  and the owner's tool will try to match it (and flag it if unsure).

This cartridge was created for: **user**.
