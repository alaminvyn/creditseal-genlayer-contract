# Reviewer guide

1. Inspect `contracts/CreditSeal.py` and run the checks in the README. Direct Mode test results exercise the same code with mocked evidence and a separately invoked validator.
2. Inspect the three files under `fixtures/`. The demonstration policy uses asset URL `https://www.python.org/static/community_logos/python-logo.png`, display name `Python Software Foundation`, and credit URL `https://www.python.org/psf/`. The policy is illustrative and the sample uses only an external image reference.
3. Once publication is approved, use the exact commit containing the fixture files to form each GitHub Raw URL. Verify that each URL serves the repository file bytes directly without redirection.
4. Once deployment is approved and recorded in [Evidence](EVIDENCE.md), open each Bradbury explorer transaction. Check finalization and successful contract execution. For each fixture, read `get_latest_assessment` with the asset ID, policy version, and pinned URL. Pass the returned ID to `get_assessment` and compare its verdict and reason with the table. Use `get_policy` to inspect the governing policy.

| Fixture | Expected outcome | Expected reason |
| --- | --- | --- |
| `pass.html` | PASS | NAME_AND_LINK_MATCH |
| `fail.html` | FAIL | LINK_MISMATCH |
| `unverifiable.html` | UNVERIFIABLE | ASSET_ABSENT |
