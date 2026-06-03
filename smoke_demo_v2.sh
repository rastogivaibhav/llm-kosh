#!/bin/bash
set -e
echo "Starting v2.0 Smoke Test..."
koush init
koush add --kind project "Apollo"
koush add --kind decision "Use Python" --project Apollo
koush pack --project Apollo
koush pack --explain
koush validate-pack exports/packs/*.zip || true
koush daemon once --mode polling
koush workbench build
echo "Smoke test passed."
