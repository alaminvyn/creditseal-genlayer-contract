# Verification evidence

## Source and environment

- Contract SHA-256: `8c0cb70494b4cecafd28aa7448d7655d11e66e1f578f3197731a3ee3f5e65435`.
- Python 3.12.16, `genlayer-test` 0.30.0rc3, `genvm-linter` 0.11.0.
- GenVM manager 0.6.0-rc10, executor 0.3.0-rc10. The release metadata lists the exact Python runner pinned by CreditSeal. The same pin appears in source returned for an existing finalized Phase 2 contract.

## Local checks

| Check | Result |
| --- | --- |
| `python -m compileall -q contracts scripts tests` | Passed |
| `genvm-lint lint contracts/CreditSeal.py` | Three checks passed |
| `GENVM_VERSION=v0.6.0-rc10 python -m pytest -q -W 'error:.*not picklable:RuntimeWarning'` | 39 passed, zero skipped against the checksum-verified release runners |
| `genvm check` on executor 0.3.0-rc10 | All 10 runner hashes verified |
| Native GenVM smoke test with local mock storage | Constructor, ABI, asset registration, policy write, live HTTP retrieval, and persisted `UNVERIFIABLE:HTTP_STATUS` read-back passed |

Direct Mode uses the real SDK equivalence callback with a test-only adapter for its sandbox operation. Agreement, disagreement, and fetch-failure tests exercise mocked evidence. The native smoke used a read-only HTTPS request to a missing path in an unrelated public repository. The sample was deliberately chosen to exercise the HTTP error path before publication.

For the native check, start the official 0.6.0-rc10 manager with `--socket /tmp/creditseal-genvm-manager.sock` and use its local `POST /module/start` API to start Web and Llm with `config: null` and `allow_empty_backends: true` for Llm. Then run:

```sh
PYTHONPATH=/path/to/genvm-manager/tests/runner .venv/bin/python scripts/genvm_smoke.py
```

The script depends on the [matching upstream test host](https://github.com/genlayerlabs/genvm-manager/tree/v0.6.0-rc10/tests/runner). It needs no wallet or LLM provider. The local execution uses mock chain storage and produces no public transaction.

## Bradbury preflight

`python scripts/bradbury_preflight.py --quote-default` performs read-only checks. Bradbury returned chain ID `4221`, the documented genesis hash, deployed AddressManager bytecode, and Finalized for a public reference transaction. The SDK's bundled Bradbury addresses differ from the current deployment. The fee probe loads the official manifest, verifies its registry and chain ID, and uses the current FeeManager.

The network-default protocol deposit quote was `100000000000010352` wei per transaction, approximately 0.10 test GEN. For six transactions the illustrative sum of deposits is about 0.60 test GEN, excluding outer L2 gas. Unused deposits can be refunded. The quote uses network-default settings. CreditSeal-specific fee measurements and spending approval are pending. Requote on the live deployment before approval and verify the public wallet balance separately.

[Phase 2 network documentation](https://docs.genlayer.com/developers/networks) · [Fee policy](https://docs.genlayer.com/developers/decentralized-applications/fees-and-transaction-kit)

## External evidence pending

GitHub publishing and blockchain writes require separate owner approvals. No CreditSeal contract address, public fixture URLs, or transaction receipts exist yet. After publishing, verify the exact fixture bytes with `python scripts/bradbury_preflight.py --fixtures OWNER/REPO COMMIT`. Deploy with that repository and commit after approval. Track one deployment, one asset registration, one policy write, and three assessments. Capture the protocol transaction ID, explorer link, finalized consensus and successful execution, plus the public view read-back for each assessment.
