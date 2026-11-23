# CreditSeal

CreditSeal is a GenLayer Intelligent Contract for checking published attribution against a wallet-controlled, versioned policy. A registry, marketplace, or another contract can use its public reads to inspect a reproducible assessment. A registration associates a wallet with a policy. CreditSeal makes no claim about creator identity, copyright ownership, licensing, or infringement.

## Contract

`register_asset` binds an exact public asset URL to the caller. `add_policy_version` lets that wallet append a required caption name and credit URL. Versions are immutable and start at 1. `assess` is public and takes an explicit version, a permitted page, and a requester-specific ID.

The leader and validators independently fetch the same HTTPS page through `gl.nondet.web.request`. The equivalence rule compares the exact decision and reason produced from each fetched page. The contract writes an assessment only after `strict_eq` returns agreed facts. A transport or runtime exception propagates. Validator disagreement is handled by the network consensus process.

Views expose an asset, a policy version, an assessment, the latest distinct assessment for a page and policy, and a count. The same caller and request ID return the same result for the same canonical arguments. Reusing the ID for different arguments reverts. A new request with a previously seen evidence fingerprint returns the original immutable assessment and preserves the latest distinct record. Stored timestamps are transaction timestamps. Records retain the agreed decision and reason, without archiving source bytes or validator responses.

## Evidence rules

V1 accepts commit-pinned HTTPS GitHub Raw files under `<owner>/<repo>/<40-lowercase-hex>/fixtures/<name>.html`. The constructor fixes the repository and commit. Deploy another instance to allow a different commit. The fetch issues one GET. Asset and credit URLs are strings used for exact reference comparisons. The contract does not retrieve them.

Registered URLs use the literal `https://` scheme, a dotted ASCII hostname and an explicit path. Hostnames are lowercased. Ports, queries, fragments, credentials, percent encodings, IP literals, dot segments, and repeated path separators are rejected. HTML-decoded `src` and `href` values must equal the stored strings exactly. Caption text is case-sensitive and collapses runs of ASCII HTML whitespace. The entire normalized caption must equal the required name. At least one nonempty caption link must match the required credit URL.

A supported use is one direct-child `img` in an explicitly closed `figure`, with at most one direct-child `figcaption`. Additional images in that figure are unsupported. An exact asset match outside the figure cannot establish a supported use, and multiple exact references are ambiguous. Comments and script text do not count. The parser allows a small static tag vocabulary, requires balanced markup, and treats duplicate attributes, explicit visibility-related attributes, and unsupported elements conservatively. The outcome describes static markup and does not certify rendered visibility or follow discovered URLs.

| Outcome | Meaning |
| --- | --- |
| PASS | A unique supported use with matching caption name and credit link. |
| FAIL | A unique supported use with a missing caption or a failed name/link check. |
| UNVERIFIABLE | Validators agree on a reason such as missing or ambiguous use, unsupported markup, or an unusable HTTP response. |

Inputs and stored fields are bounded. The 64 KiB parser limit is applied to the received body and cannot cap the download. DNS, TLS, and redirect handling are properties of the web runtime. The fixed commit, repository, and raw-file URL grammar constrain the fetch surface. GenVM's filtered client rejects private destinations and HTTPS downgrades, but can follow cross-host HTTPS redirects and does not expose the effective URL to the contract. The deployment depends on GitHub Raw serving the approved files directly. Verify the exact files before authorizing live writes. See [verification status](EVIDENCE.md) for the remaining live runtime gates.

## Reproduce

Use Python 3.12 and the pinned development dependencies.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/genvm-lint lint contracts/CreditSeal.py
GENVM_VERSION=v0.6.0-rc10 .venv/bin/python -m pytest -q -W 'error:.*not picklable:RuntimeWarning'
.venv/bin/python scripts/bradbury_preflight.py
```

The test suite also checks the SDK-generated ABI. On the first run, Direct Mode retrieves the pinned GenVM bundle.

See the [reviewer guide](REVIEWER_GUIDE.md) for fixtures and public verification, and the [submission draft](SUBMISSION_DRAFT.md) for portal copy.
