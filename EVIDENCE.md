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

## Bradbury on-chain evidence

The [audited public commit](https://github.com/alaminvyn/creditseal-genlayer-contract/commit/72a611b7422f7db41d0e13a5d890a06086eb708c) matches the finalized deployed source byte for byte. Each pinned fixture returned HTTP 200 directly and matched the audited bytes.

- **Contract** `0x5f5eD549DFB3631A632A4ce12186216AfCE952fE` on Bradbury Phase 2, chain 4221. [Finalized deployment](https://scan.bradbury.genlayer.com/tx/0x456525c69b230b1bdf4769bc9f2ad3e5c8a73581a42901fb268b79f0247c98a5)
- **Asset ID** `1690d62b063f721417081054650060369963dba48c55192b2d893034df4368d4`. [Finalized registration](https://scan.bradbury.genlayer.com/tx/0x5bd5b292849b8748f799cfd2fdaba9dd51c18eb5fcd91831f4dd1c57503e06b0)
- **Policy Version 1** stores display name Python Software Foundation and credit URL `https://www.python.org/psf/`. [Finalized policy write](https://scan.bradbury.genlayer.com/tx/0x61d3d965b815e24b8417891a8ce58c52aff66c47416f34883cd40539e8de8819)

| Assessment | Finalized result | Evidence |
| --- | --- | --- |
| PASS | FinishedWithReturn. Stored `PASS:NAME_AND_LINK_MATCH`. | [GenLayer transaction](https://scan.bradbury.genlayer.com/tx/0x1e6dd02bbb9f2a4441aedd673d596d0d766554f1ba588c878132ae188b515c99) · [Outer transaction](https://scan.testnet-chain.genlayer.com/tx/0x7ace225a40bd18d17a77bb3e7f2e43fe8c56f528a6e4b6cfeb75b99ed28f48a3) |
| FAIL | Pending | The sequence stopped before this assessment. |
| UNVERIFIABLE | Pending | The sequence stopped before this assessment. |

The PASS receipt shows four matching successful votes and one timeout vote. The underlying timeout cause is unverified. The sequence was halted before opening another wallet confirmation.

Finalized `get_latest_assessment` returned `ad5ae6c253cec4fc26d7e77221f9b0f0020845b0aa77fddb74fece5d1126fe48`. Finalized `get_assessment` confirmed the pinned PASS URL, asset ID, policy version 1, approved requester, and exact outcome and reason. `get_assessment_count` returned **1**.

PASS used **2,295,383** of **2,800,000** outer gas. The outer fee was **0.00002295383 test GEN**. The protocol receipt recorded **0.00006200925 test GEN** in execution and storage fees against the **0.10 test GEN** deposit.

**Submission status — NOT READY.** Finalized FAIL and UNVERIFIABLE evidence and the final count of 3 are pending.
