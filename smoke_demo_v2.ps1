Write-Host "Starting v2.0 Smoke Test..."
python -m koush.cli init
python -m koush.cli add --kind project --title "Apollo"
python -m koush.cli add --kind decision --title "Use Python" --project Apollo
python -m koush.cli pack Apollo --out exports/packs/Apollo_pack.zip
python -m koush.cli validate-pack exports/packs/Apollo_pack.zip
python -m koush.cli daemon once --mode polling
python -m koush.cli workbench build
Write-Host "Smoke test passed."
