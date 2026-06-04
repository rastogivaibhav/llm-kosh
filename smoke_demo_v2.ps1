Write-Host "Starting v2.0 Smoke Test..."
python -m llm-kosh.cli init
python -m llm-kosh.cli add --kind project --title "Apollo"
python -m llm-kosh.cli add --kind decision --title "Use Python" --project Apollo
python -m llm-kosh.cli pack Apollo --out exports/packs/Apollo_pack.zip
python -m llm-kosh.cli validate-pack exports/packs/Apollo_pack.zip
python -m llm-kosh.cli daemon once --mode polling
python -m llm-kosh.cli workbench build
Write-Host "Smoke test passed."
