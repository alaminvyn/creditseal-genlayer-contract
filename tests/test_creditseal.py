from pathlib import Path
import re
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
REPO = "creditseal-test/creditseal"
COMMIT = "a" * 40
PREFIX = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/fixtures/"
ASSET = "https://www.python.org/static/community_logos/python-logo.png"
CREDIT = "https://www.python.org/psf/"
NAME = "Python Software Foundation"
IMG = f'<img src="{ASSET}">'
CAP = f'<figcaption><a href="{CREDIT}">{NAME}</a></figcaption>'
GOOD = f"<figure>{IMG}{CAP}</figure>"


@pytest.fixture
def registered(direct_deploy, direct_vm):
    # Direct Mode reloads the module for each deployment in the same interpreter.
    # GenVM itself loads a single contract per interpreter.
    direct_vm.strict_mocks = True
    sdk_contract = sys.modules.get("genlayer.contract")
    if sdk_contract is not None:
        sdk_contract.__known_contract__ = None
    contract = direct_deploy(str(ROOT / "contracts/CreditSeal.py"), REPO, COMMIT)
    asset_id = contract.register_asset(ASSET)
    version = contract.add_policy_version(asset_id, " Python   Software Foundation ", CREDIT)
    return contract, asset_id, version


def mock_page(vm, url, body, status=200, content_type="text/plain"):
    vm.mock_web(
        "^" + re.escape(url) + "$",
        {"method": "GET", "response": {
            "status": status, "body": body.encode() if isinstance(body, str) else body, "headers": {"content-type": content_type.encode()},
        }},
    )


@pytest.mark.parametrize(
    ("fixture", "outcome", "reason"),
    [
        ("pass", "PASS", "NAME_AND_LINK_MATCH"),
        ("fail", "FAIL", "LINK_MISMATCH"),
        ("unverifiable", "UNVERIFIABLE", "ASSET_ABSENT"),
    ],
)
def test_fixtures(registered, direct_vm, fixture, outcome, reason):
    contract, asset_id, version = registered
    direct_vm.strict_mocks = True
    direct_vm.check_pickling = True
    url = PREFIX + fixture + ".html"
    mock_page(direct_vm, url, (ROOT / "fixtures" / f"{fixture}.html").read_text())
    record_id = contract.assess(asset_id, version, url, "first")
    record = contract.get_assessment(record_id)
    assert (record["outcome"], record["reason"]) == (outcome, reason)
    assert record["asset_id"] == asset_id
    assert record["policy_version"] == 1
    assert record["transaction_time"]
    assert contract.get_latest_assessment(asset_id, version, url) == record_id
    assert contract.get_assessment_count() == 1


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        (GOOD.replace(NAME, "Other Name"), "NAME_MISMATCH"),
        (f"<figure>{IMG}</figure>{CAP.replace('figcaption', 'div')}", "CAPTION_MISSING"),
        (GOOD + GOOD, "AMBIGUOUS_USE"),
        (GOOD + IMG, "AMBIGUOUS_USE"),
        (f"<figure><div>{IMG}</div>{CAP}</figure>", "UNSUPPORTED_USE"),
        (f"<figure hidden>{IMG}{CAP}</figure>", "UNSUPPORTED_HTML"),
        (f"<template>{GOOD}</template>", "UNSUPPORTED_HTML"),
        (f"<script>{GOOD}</script><!--{GOOD}-->", "ASSET_ABSENT"),
        (GOOD.removesuffix("</figure>"), "UNSUPPORTED_HTML"),
        (GOOD.replace("<img ", '<img src="duplicate" '), "UNSUPPORTED_HTML"),
        (GOOD.replace(f">{NAME}</a>", f"></a>{NAME}"), "LINK_MISMATCH"),
        (GOOD + " " * 65536, "BODY_LIMIT"),
    ],
)
def test_evidence(registered, direct_vm, body, reason):
    contract, asset_id, version = registered
    url = PREFIX + "adversarial.html"
    mock_page(direct_vm, url, body)
    record = contract.get_assessment(contract.assess(asset_id, version, url, "request"))
    assert record["reason"] == reason


def test_policy_access_and_history(registered, direct_vm, direct_bob):
    contract, asset_id, version = registered
    assert contract.get_asset(asset_id)["policy_count"] == 1
    assert contract.get_policy(asset_id, version)["name"] == NAME
    url = PREFIX + "pass.html"
    mock_page(direct_vm, url, GOOD)
    with direct_vm.prank(direct_bob):
        with direct_vm.expect_revert("registrant only"):
            contract.add_policy_version(asset_id, "Mallory", CREDIT)
        first = contract.assess(asset_id, version, url, "same")
    assert contract.get_assessment(first)["outcome"] == "PASS"
    second_version = contract.add_policy_version(asset_id, "Other", CREDIT)
    assert second_version == 2
    second = contract.assess(asset_id, second_version, url, "same")
    assert contract.get_assessment(second)["outcome"] == "FAIL"
    assert contract.get_assessment(first)["outcome"] == "PASS"
    assert contract.get_policy(asset_id, version)["name"] == NAME
    with direct_vm.expect_revert("unknown policy"):
        contract.assess(asset_id, 3, url, "new")


def test_replay_dedup_and_latest(registered, direct_vm):
    contract, asset_id, version = registered
    url = PREFIX + "pass.html"
    mock_page(direct_vm, url, GOOD)
    first = contract.assess(asset_id, version, url, "one")
    assert contract.assess(asset_id, version, url, "two") == first
    direct_vm.clear_mocks()
    assert contract.assess(asset_id, version, url, "one") == first
    with direct_vm.expect_revert("conflicting request ID"):
        contract.assess(asset_id, version, PREFIX + "fail.html", "one")
    mock_page(direct_vm, url, GOOD.replace(NAME, "Other"))
    second = contract.assess(asset_id, version, url, "three")
    assert second != first
    assert contract.get_assessment_count() == 2
    assert contract.get_latest_assessment(asset_id, version, url) == second
    assert contract.get_assessment(first)["outcome"] == "PASS"


@pytest.mark.parametrize("url", [
    "http://example.org/a", "https://localhost/a", "https://127.0.0.1/a",
    "https://user@example.org/a", "https://example.org:443/a",
    "https://example.org/%2f", "https://example.org/../a",
    "https://example.org/" + "a" * 512,
])
def test_reject_invalid_registration(registered, direct_vm, url):
    contract, _, _ = registered
    with direct_vm.expect_revert():
        contract.register_asset(url)


@pytest.mark.parametrize("url", [
    "https://example.org/fixtures/pass.html",
    "https://raw.githubusercontent.com/other/creditseal/" + "a" * 40 + "/fixtures/pass.html",
    PREFIX.replace(COMMIT, "main") + "pass.html",
    PREFIX.replace(COMMIT, "b" * 40) + "pass.html",
    PREFIX + "%2e%2e.html",
])
def test_reject_unapproved_url_before_fetch(registered, direct_vm, url):
    contract, asset_id, version = registered
    with direct_vm.expect_revert():
        contract.assess(asset_id, version, url, "request")
    assert contract.get_assessment_count() == 0


@pytest.fixture
def validator_sandbox(registered, monkeypatch):
    # gltest 0.30.0rc3 does not execute the SDK's Sandbox operation. Use the
    # real strict_eq callback while emulating the sandbox boundary in-process.
    from genlayer import vm

    monkeypatch.setattr(vm, "spawn_sandbox", lambda fn: vm.Return(calldata=fn()))


def test_validator_agreement_and_disagreement(registered, direct_vm, validator_sandbox):
    contract, asset_id, version = registered
    url = PREFIX + "pass.html"
    snap = direct_vm.snapshot()
    direct_vm.check_pickling = True
    mock_page(direct_vm, url, GOOD)
    contract.assess(asset_id, version, url, "request")
    direct_vm.clear_mocks()
    mock_page(direct_vm, url, "<!--noise-->" + GOOD.replace("Python Software Foundation", "Python   Software Foundation"))
    assert direct_vm.run_validator() is True
    direct_vm.clear_mocks()
    mock_page(direct_vm, url, GOOD.replace(NAME, "Other"))
    assert direct_vm.run_validator() is False
    # Direct Mode executes the leader first. Restore the pre-call state explicitly.
    direct_vm.revert(snap)
    assert contract.get_assessment_count() == 0


def test_http_status_can_agree(registered, direct_vm, validator_sandbox):
    contract, asset_id, version = registered
    url = PREFIX + "pass.html"
    mock_page(direct_vm, url, "", status=404)
    result_id = contract.assess(asset_id, version, url, "request")
    assert contract.get_assessment(result_id)["reason"] == "HTTP_STATUS"
    assert direct_vm.run_validator() is True


def test_fetch_failure_no_state(registered, direct_vm):
    contract, asset_id, version = registered
    url = PREFIX + "pass.html"
    from gltest.direct.wasi_mock import MockNotFoundError

    with pytest.raises(MockNotFoundError):
        contract.assess(asset_id, version, url, "request")
    assert contract.get_assessment_count() == 0
    assert contract.get_latest_assessment(asset_id, version, url) == ""
    mock_page(direct_vm, url, GOOD)
    assert contract.assess(asset_id, version, url, "request")


def test_schema(registered):
    import json
    from genlayer import contract as sdk_contract

    schema = json.loads(sdk_contract.__known_contract__.__get_schema__())
    assert set(schema["methods"]) == {
        "register_asset", "add_policy_version", "assess", "get_asset", "get_policy",
        "get_assessment", "get_latest_assessment", "get_assessment_count",
    }


@pytest.mark.parametrize(("body", "content_type", "expected"), [
    (b"\xff", "text/html", "UNSUPPORTED_HTML"),
    (GOOD, "application/json", "CONTENT_TYPE"),
    (None, "text/html", "EMPTY_RESPONSE"),
])
def test_unsupported_response(registered, direct_vm, body, content_type, expected):
    contract, asset_id, version = registered
    url = PREFIX + "pass.html"
    mock_page(direct_vm, url, body, content_type=content_type)
    result_id = contract.assess(asset_id, version, url, "request")
    assert contract.get_assessment(result_id)["reason"] == expected


def test_wallet_scoped_registration(registered, direct_vm, direct_bob):
    contract, asset_id, _ = registered
    uppercase_host = ASSET.replace("www.python.org", "WWW.PYTHON.ORG")
    with direct_vm.expect_revert("asset already registered"):
        contract.register_asset(uppercase_host)
    with direct_vm.prank(direct_bob):
        another = contract.register_asset(uppercase_host)
    assert another != asset_id
    assert contract.get_asset(another)["url"] == ASSET
    assert contract.get_asset(another)["policy_count"] == 0


def test_rejected_policy_and_request_leave_no_records(registered, direct_vm):
    contract, asset_id, version = registered
    with direct_vm.expect_revert("invalid name"):
        contract.add_policy_version(asset_id, "界" * 43, CREDIT)
    with direct_vm.expect_revert("invalid request ID"):
        contract.assess(asset_id, version, PREFIX + "pass.html", "r" * 65)
    assert contract.get_asset(asset_id)["policy_count"] == 1
    assert contract.get_assessment_count() == 0
