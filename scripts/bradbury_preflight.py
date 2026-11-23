"""Read-only checks for a GenLayer Bradbury Phase 2 RPC."""

import argparse
from copy import deepcopy
import json
import re
import subprocess
from pathlib import Path

RPC = "https://rpc-bradbury.genlayer.com"
GENESIS = "0x17d89764d4f4f963158fc4c5e8f2cb670c2837740b35f37081c12860c3df97e4"
ADDRESS_MANAGER = "0x3F71AE080BD6270A91dBcc7960d88797828538E0"
MANIFEST = "https://docs.genlayer.com/validators/bradbury.protocol-manifest.json"
REFERENCE_TX = "0x53b84a5a976fee4c51f3443525c0284ea768f14c4d69c7594aeac4c94e9d7b4d"


def rpc(method, *params):
    data = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    response = subprocess.run(
        ["curl", "--disable", "--fail", "--silent", "--show-error", "--max-time", "15",
         "--header", "Content-Type: application/json", "--data-binary", "@-", RPC],
        input=data, text=True, capture_output=True, check=True,
    )
    envelope = json.loads(response.stdout)
    if "error" in envelope:
        raise RuntimeError(f"{method}: {envelope['error']}")
    return envelope["result"]


def network_default_fee_quote():
    from genlayer_py.chains import testnet_bradbury
    from genlayer_py.client.genlayer_client import GenLayerClient

    response = subprocess.run(
        ["curl", "--disable", "--fail", "--silent", "--show-error", "--max-time", "15", MANIFEST],
        capture_output=True, check=True,
    )
    manifest = json.loads(response.stdout)
    if str(manifest["chainId"]) != "4221" or manifest["registry"].lower() != ADDRESS_MANAGER.lower():
        raise SystemExit("Unexpected Phase 2 deployment manifest")
    entries = {entry["key"]: entry["addr"] for entry in manifest["entries"]}
    chain = deepcopy(testnet_bradbury)
    for field, key in (
        ("consensus_main_contract", "ConsensusMain"),
        ("consensus_data_contract", "ConsensusData"),
        ("fee_manager_contract", "FeeManager"),
        ("rounds_storage_contract", "Rounds"),
        ("appeals_contract", "Appeals"),
    ):
        configured = getattr(chain, field)
        if configured is not None:
            configured["address"] = entries[key]
    if rpc("eth_getCode", entries["FeeManager"], "latest") in ("0x", None):
        raise SystemExit("Manifest FeeManager has no bytecode")
    quote = GenLayerClient(chain, None).estimate_transaction_fees()
    print(f"Network-default fee deposit in wei: {quote['feeValue']} (excludes outer gas)")


def verify_fixtures(repo, commit):
    fixtures = Path(__file__).resolve().parents[1] / "fixtures"
    for name in ("pass.html", "fail.html", "unverifiable.html"):
        url = f"https://raw.githubusercontent.com/{repo}/{commit}/fixtures/{name}"
        response = subprocess.run(
            ["curl", "--disable", "--fail", "--silent", "--show-error", "--max-time", "15",
             "--max-filesize", "65536", "--write-out", "\n%{http_code}", url],
            capture_output=True, check=True,
        )
        body, status = response.stdout.rsplit(b"\n", 1)
        if status != b"200" or body != (fixtures / name).read_bytes():
            raise SystemExit(f"Fixture did not serve the expected bytes directly: {url}")
        print(f"Fixture verified: {url}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wallet", help="Optional public wallet address for a balance read")
    parser.add_argument("--fixtures", nargs=2, metavar=("OWNER/REPO", "COMMIT"),
                        help="Verify published fixture bytes without following redirects")
    parser.add_argument("--quote-default", action="store_true",
                        help="Read the live default protocol deposit, without signing")
    args = parser.parse_args()
    if args.fixtures:
        repo, commit = args.fixtures
        if not re.fullmatch(r"[A-Za-z0-9-]{1,39}/[A-Za-z0-9_-][A-Za-z0-9_.-]{0,99}", repo):
            parser.error("invalid fixture repository")
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            parser.error("commit must be a 40-character lowercase Git SHA")
    if args.wallet and not re.fullmatch(r"0x[0-9a-fA-F]{40}", args.wallet):
        parser.error("wallet must be a public Ethereum-format address")
    if rpc("eth_chainId") != "0x107d":
        raise SystemExit("Wrong chain ID")
    if rpc("eth_getBlockByNumber", "0x0", False)["hash"] != GENESIS:
        raise SystemExit("Wrong genesis hash")
    if rpc("eth_getCode", ADDRESS_MANAGER, "latest") in ("0x", None):
        raise SystemExit("AddressManager has no bytecode")
    reference = rpc("gen_getTransactionStatus", {"txId": REFERENCE_TX})
    if reference["status"] != "Finalized":
        raise SystemExit("Phase 2 reference transaction is missing or not finalized")
    print("Bradbury Phase 2 chain ID, genesis, AddressManager code, and GenLayer RPC verified")
    if args.quote_default:
        network_default_fee_quote()
    if args.fixtures:
        verify_fixtures(*args.fixtures)
    if args.wallet:
        balance = int(rpc("eth_getBalance", args.wallet, "latest"), 16)
        print(f"Wallet balance in wei: {balance}")


if __name__ == "__main__":
    main()
