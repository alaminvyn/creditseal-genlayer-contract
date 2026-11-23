"""Exercise CreditSeal in native GenVM on a Unix socket with a mock chain host."""

import argparse
import asyncio
import json
import pickle
import tempfile
from pathlib import Path

from origin import base_host
from origin.calldata import Address, encode
from gvm_extra.mock_host import MockHost, MockStorage


class QuietContext:
    def __init__(self):
        self.logger = self

    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


async def main(manager_socket):
    address = Address("0x" + "01" * 20)
    sender = Address("0x" + "02" * 20)
    message = dict(contract_address=address, sender_address=sender, origin_address=sender,
                   signer_address=sender, chain_id=0, value=0, is_init=True)
    ctx = QuietContext()
    code = (Path(__file__).resolve().parents[1] / "contracts/CreditSeal.py").read_bytes()
    manager = "unix://" + str(manager_socket.resolve())

    with tempfile.TemporaryDirectory(prefix="creditseal-genvm-") as root:
        storage = Path(root) / "storage.pickle"
        storage.write_bytes(pickle.dumps(MockStorage()))
        sock = str(Path(root) / "host.sock")
        async with base_host.ManagerClient(manager) as client:
            repo = "genlayerlabs/genvm-executor"
            commit = "2e094c6fdd7fb3b620706a2d20845e004fb6d298"
            asset_id = None
            assessment_id = None
            asset_url = "https://example.org/asset.png"
            page_url = f"https://raw.githubusercontent.com/{repo}/{commit}/fixtures/creditseal-missing.html"
            for method in ("", "#get-schema", "register_asset", "add_policy_version", "assess", "get_assessment"):
                args = {
                    "": [repo, commit],
                    "#get-schema": [],
                    "register_asset": [asset_url],
                    "add_policy_version": [asset_id, "Example", "https://example.org/credit"],
                    "assess": [asset_id, 1, page_url, "native-smoke"],
                    "get_assessment": [assessment_id],
                }[method]
                host = MockHost(path=sock, storage_path_pre=storage, storage_path_post=storage,
                                balances={}, running_address=address, ctx=ctx)
                payload = {"args": args}
                if method:
                    payload[""] = method
                with host:
                    result = await base_host.run_genvm(
                        host, manager_uri=manager, manager_client=client, ctx=ctx,
                        message={**message, "is_init": method == ""}, is_sync=method != "assess",
                        host_data=json.dumps({"node_address": "0x" + "00" * 20,
                                              "tx_id": "0x" + "00" * 32,
                                              "signerUrl": "https://test-server.genlayer.com/genvm/sign"}),
                        host="unix://" + sock, code=code if not method else None,
                        calldata=encode(payload), timeout=30,
                        bucket_totals=base_host.default_bucket_totals(3),
                        request_extra={"no_modules": method != "assess"}, major=0,
                    )
                    await host.stop_connections()
                    for key, value in result.result_storage_deltas:
                        assert len(key) == 36
                        host.storage.write(address, key[:32], int.from_bytes(key[32:], "big") * 32, value)
                if result.result_kind != 0:
                    raise RuntimeError(f"{method or 'constructor'}: {result.result_data}")
                print(f"{method or 'constructor'} succeeded")
                if method == "#get-schema":
                    assert "assess" in json.loads(result.result_data)["methods"]
                elif method == "register_asset":
                    asset_id = result.result_data
                elif method == "assess":
                    assessment_id = result.result_data
                elif method == "get_assessment":
                    assert result.result_data["reason"] == "HTTP_STATUS"
                    print("Native HTTP retrieval and stored UNVERIFIABLE:HTTP_STATUS verified")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manager-socket", type=Path, default=Path("/tmp/creditseal-genvm-manager.sock"))
    asyncio.run(main(parser.parse_args().manager_socket))
