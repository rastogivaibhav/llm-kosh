# Intake Control Plane Specification (v1.2)

The Koush Intake Control Plane is a unified subsystem that tracks every incoming item (MEMORY_RECEIPTs, text files, daemon intakes, import exports) before they are applied to the core AI memory cartridge.

## Subdirectories
- `intake/pending/`: Unprocessed intake items.
- `intake/reviewed/`: Items that have been manually reviewed by the user.
- `intake/applied/`: Items successfully absorbed into memory.
- `intake/rejected/`: Items the user explicitly rejected.
- `intake/quarantined/`: Items containing malicious content, secrets, or malformed data that need quarantine.
- `reports/intake/`: Human-readable review reports generated for intake items.

## Workflows

1. **Scan**: `intake scan` discovers new files in `receipts/`, `inbox/`, `attachments/imports/`, and `source/receipts/`. It creates JSON `koush.intake.v1` records in `intake/pending/`.
2. **Validate**: Checks if the file structurally aligns with its processor (e.g. `parse_receipt`).
3. **Review**: Generates an audit report in `reports/intake/` outlining decisions, files, gaps, or corrections to be applied.
4. **Apply**: Uses the appropriate processor (like `absorb_receipt` or `ingest_path`) to apply the intake to memory. Modifies the state to `applied`.
5. **Reject/Quarantine**: Skips processing and moves the records out of the pending flow.

## Policy
`KOUSH_POLICY.json` supports an `intake` configuration block determining auto-apply behavior:
```json
"intake": {
  "auto_apply_receipts": false,
  "auto_apply_folder_notes": false,
  "require_review_for_corrections": true,
  "require_review_for_private": true
}
```
