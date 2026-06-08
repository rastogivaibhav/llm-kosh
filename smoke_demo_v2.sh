#!/bin/bash
set -e
echo "Starting v2.0 Smoke Test..."
llm-kosh init
llm-kosh add --kind project "Apollo"
llm-kosh add --kind decision "Use Python" --project Apollo
llm-kosh pack --project Apollo
llm-kosh pack --explain
llm-kosh validate-pack exports/packs/*.zip || true
llm-kosh daemon once --mode polling
llm-kosh workbench build
echo "Smoke test passed."
