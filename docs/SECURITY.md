# Security

Policies reside in `LLM_KOSH_POLICY.json` at the root of your cartridge. The Trust Gate prevents AI from deleting source data unsupervised.

> [!WARNING]
> Do not confuse this with `CARTRIDGE_POLICY.json` which is a deprecated naming convention. Always use `LLM_KOSH_POLICY.json`.

All exports via `llm-kosh pack` adhere to the visibility rules defined in the policy, ensuring that `private` and `quarantine` memories are never accidentally leaked to an LLM context window.