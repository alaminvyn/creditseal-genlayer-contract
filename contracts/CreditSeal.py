# v0.3.0
# { "Depends": "py-genlayer:babwp9t37jw9g4j2bccgn14g6x7x9s1f7dsmh7emvz735pz4zxa0" }

import hashlib
import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser

import genlayer as gl
from genlayer.storage import TreeMap
from genlayer.types import Address, u256


MAX_BODY = 65536
MAX_DEPTH = 64
RAW_ORIGIN = "https://raw.githubusercontent.com/"
VOID_TAGS = frozenset("area base br col embed hr img input link meta param source track wbr".split())
SUPPORTED_TAGS = frozenset(
    "html head title meta body main article section div p span figure figcaption img a em strong b i script".split()
)
HIDDEN_ATTRIBUTES = frozenset(("hidden", "aria-hidden", "inert", "style"))


def require(condition, message):
    if not condition:
        raise gl.vm.UserError(message)


def canonical_url(value):
    require(len(value) <= 512, "URL too long")
    match = re.fullmatch(
        r"https://([A-Za-z0-9.-]+)(/[A-Za-z0-9_./~-]*)", value
    )
    require(match is not None, "invalid HTTPS URL")
    host, path = match.groups()
    labels = host.lower().split(".")
    require(
        len(labels) >= 2
        and labels[-1] not in ("local", "localhost", "internal", "test", "invalid", "onion")
        and labels[-1].isascii()
        and labels[-1].isalpha()
        and all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", x) for x in labels)
        and not any(x in (".", "..") for x in path.split("/"))
        and "//" not in path,
        "invalid host or path",
    )
    return "https://" + host.lower() + path


def normalized_name(text):
    return re.sub(r"[ \t\n\r\f]+", " ", text).strip(" ")


def digest(*fields):
    payload = json.dumps(fields, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


class UnsupportedHTML(ValueError):
    pass


class FigureParser(HTMLParser):
    def __init__(self, asset_url, name, credit_url):
        super().__init__(convert_charrefs=True)
        self.asset_url = asset_url
        self.name = name
        self.credit_url = credit_url
        self.stack = []
        self.matches = 0
        self.total_uses = 0
        self.figure_uses = 0
        self.figure_images = 0
        self.caption_count = 0
        self.caption_text = []
        self.credit_link = False
        self.anchor_text = None
        self.missing_caption = False
        self.name_match = False
        self.link_match = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if (
            len(attributes) != len(attrs)
            or len(self.stack) >= MAX_DEPTH
            or tag not in SUPPORTED_TAGS
            or HIDDEN_ATTRIBUTES.intersection(attributes)
        ):
            raise UnsupportedHTML
        parent = self.stack[-1] if self.stack else ""
        if tag == "figure":
            if "figure" in self.stack:
                raise UnsupportedHTML
            self.figure_uses = self.figure_images = self.caption_count = 0
            self.caption_text = []
            self.credit_link = False
        elif tag == "figcaption":
            if parent != "figure" or self.caption_count:
                raise UnsupportedHTML
            self.caption_count += 1
        elif tag == "img":
            if "srcset" in attributes or "figcaption" in self.stack:
                raise UnsupportedHTML
            if "figure" in self.stack:
                self.figure_images += 1
            if attributes.get("src") == self.asset_url:
                self.total_uses += 1
                if parent == "figure":
                    self.figure_uses += 1
        elif tag == "a" and "figcaption" in self.stack:
            if "a" in self.stack:
                raise UnsupportedHTML
            if attributes.get("href") == self.credit_url:
                self.anchor_text = []
        if tag not in VOID_TAGS:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            raise UnsupportedHTML
        if tag == "a" and self.anchor_text is not None:
            self.credit_link |= bool(normalized_name("".join(self.anchor_text)))
            self.anchor_text = None
        if tag == "figure" and self.figure_uses:
            if self.figure_images != self.figure_uses:
                raise UnsupportedHTML
            self.matches += self.figure_uses
            self.name_match = normalized_name("".join(self.caption_text)) == self.name
            self.link_match = self.credit_link
            self.missing_caption = self.caption_count == 0

    def handle_startendtag(self, tag, attrs):
        if tag not in VOID_TAGS:
            raise UnsupportedHTML
        self.handle_starttag(tag, attrs)

    def handle_data(self, data):
        if self.stack and self.stack[-1] != "script" and "figcaption" in self.stack:
            self.caption_text.append(data)
            if self.anchor_text is not None:
                self.anchor_text.append(data)

    def unknown_decl(self, data):
        raise UnsupportedHTML


def derive_facts(body, asset_url, name, credit_url):
    if len(body) > MAX_BODY:
        return "UNVERIFIABLE:BODY_LIMIT"
    parser = FigureParser(asset_url, name, credit_url)
    try:
        source = body.decode("utf-8", errors="strict")
        if "\x00" in source:
            raise UnsupportedHTML
        parser.feed(source)
        parser.close()
        if parser.stack:
            raise UnsupportedHTML
    except (UnicodeError, UnsupportedHTML):
        return "UNVERIFIABLE:UNSUPPORTED_HTML"

    if parser.total_uses == 0:
        return "UNVERIFIABLE:ASSET_ABSENT"
    if parser.total_uses > 1:
        return "UNVERIFIABLE:AMBIGUOUS_USE"
    if parser.matches != 1:
        return "UNVERIFIABLE:UNSUPPORTED_USE"
    if parser.missing_caption:
        return "FAIL:CAPTION_MISSING"
    if parser.name_match and parser.link_match:
        return "PASS:NAME_AND_LINK_MATCH"
    if parser.name_match:
        return "FAIL:LINK_MISMATCH"
    if parser.link_match:
        return "FAIL:NAME_MISMATCH"
    return "FAIL:NAME_AND_LINK_MISMATCH"


def observe_page(page_url, asset_url, name, credit_url):
    response = gl.nondet.web.request(page_url, method="GET")
    if response.status != 200:
        return "UNVERIFIABLE:HTTP_STATUS"
    # GitHub Raw serves the commit-pinned fixture bytes as text/plain.
    content_type = response.headers.get("content-type", "")
    if isinstance(content_type, bytes):
        content_type = content_type.decode("ascii", errors="replace")
    if content_type.split(";", 1)[0].strip().lower() not in ("text/plain", "text/html"):
        return "UNVERIFIABLE:CONTENT_TYPE"
    if response.body is None:
        return "UNVERIFIABLE:EMPTY_RESPONSE"
    return derive_facts(response.body, asset_url, name, credit_url)


@gl.storage.allow
@dataclass
class Asset:
    registrant: Address
    url: str
    policy_count: u256


@gl.storage.allow
@dataclass
class Policy:
    name: str
    credit_url: str


@gl.storage.allow
@dataclass
class Assessment:
    asset_id: str
    policy_version: u256
    page_url: str
    requester: Address
    facts: str
    transaction_time: str


@gl.storage.allow
@dataclass
class Request:
    scope: str
    assessment_id: str


class CreditSeal(gl.contract.Contract):
    fixture_prefix: str
    assets: TreeMap[str, Asset]
    policies: TreeMap[str, Policy]
    assessments: TreeMap[str, Assessment]
    requests: TreeMap[str, Request]
    latest: TreeMap[str, str]
    assessment_count: u256

    def __init__(self, fixture_repository: str, fixture_commit: str):
        require(
            len(fixture_repository) <= 141
            and re.fullmatch(r"[A-Za-z0-9-]{1,39}/[A-Za-z0-9_-][A-Za-z0-9_.-]{0,99}", fixture_repository)
            is not None,
            "invalid fixture repository",
        )
        require(
            len(fixture_commit) == 40 and re.fullmatch(r"[0-9a-f]{40}", fixture_commit) is not None,
            "invalid fixture commit",
        )
        self.fixture_prefix = RAW_ORIGIN + fixture_repository + "/" + fixture_commit + "/fixtures/"

    @gl.public.write
    def register_asset(self, asset_url: str) -> str:
        url = canonical_url(asset_url)
        registrant = gl.message.sender_address
        asset_id = digest(str(registrant), url)
        require(asset_id not in self.assets, "asset already registered")
        self.assets[asset_id] = Asset(registrant, url, u256(0))
        return asset_id

    @gl.public.write
    def add_policy_version(self, asset_id: str, required_name: str, required_credit_url: str) -> u256:
        require(len(asset_id) == 64 and asset_id in self.assets, "unknown asset")
        asset = self.assets[asset_id]
        require(asset.registrant == gl.message.sender_address, "registrant only")
        require(len(required_name) <= 128, "name too long")
        name = normalized_name(required_name)
        require(0 < len(name.encode("utf-8")) <= 128 and name.isprintable(), "invalid name")
        credit_url = canonical_url(required_credit_url)
        version = u256(asset.policy_count + 1)
        self.policies[digest(asset_id, int(version))] = Policy(name, credit_url)
        asset.policy_count = version
        return version

    @gl.public.write
    def assess(self, asset_id: str, policy_version: u256, page_url: str, request_id: str) -> str:
        require(len(asset_id) == 64 and asset_id in self.assets, "unknown asset")
        policy_key = digest(asset_id, int(policy_version))
        require(policy_key in self.policies, "unknown policy")
        url = self._page_url(page_url)
        require(len(request_id) <= 64 and re.fullmatch(r"[A-Za-z0-9_-]+", request_id), "invalid request ID")
        requester = gl.message.sender_address
        request_key = digest(str(requester), request_id)
        scope = digest(policy_key, url)
        if request_key in self.requests:
            request = self.requests[request_key]
            require(request.scope == scope, "conflicting request ID")
            return request.assessment_id

        policy = self.policies[policy_key]
        asset_url, name, credit_url = self.assets[asset_id].url, policy.name, policy.credit_url

        def observation():
            return observe_page(url, asset_url, name, credit_url)

        facts = gl.eq_principle.strict_eq(observation)
        assessment_id = digest(scope, facts)
        if assessment_id not in self.assessments:
            self.assessments[assessment_id] = Assessment(
                asset_id, policy_version, url, requester, facts, gl.message.raw["datetime"]
            )
            self.latest[scope] = assessment_id
            self.assessment_count = u256(self.assessment_count + 1)
        self.requests[request_key] = Request(scope, assessment_id)
        return assessment_id

    def _page_url(self, page_url: str) -> str:
        url = canonical_url(page_url)
        require(url.startswith(self.fixture_prefix), "unapproved fixture repository or commit")
        suffix = url[len(self.fixture_prefix):]
        require(
            re.fullmatch(r"[A-Za-z0-9_-]{1,64}\.html", suffix)
            is not None,
            "invalid fixture filename",
        )
        return url

    @gl.public.view
    def get_asset(self, asset_id: str) -> dict:
        require(len(asset_id) == 64 and asset_id in self.assets, "unknown asset")
        asset = self.assets[asset_id]
        return {"registrant": str(asset.registrant), "url": asset.url, "policy_count": int(asset.policy_count)}

    @gl.public.view
    def get_policy(self, asset_id: str, version: u256) -> dict:
        require(len(asset_id) == 64, "unknown asset")
        key = digest(asset_id, int(version))
        require(key in self.policies, "unknown policy")
        policy = self.policies[key]
        return {"name": policy.name, "credit_url": policy.credit_url}

    @gl.public.view
    def get_assessment(self, assessment_id: str) -> dict:
        require(len(assessment_id) == 64 and assessment_id in self.assessments, "unknown assessment")
        assessment = self.assessments[assessment_id]
        outcome, reason = assessment.facts.split(":", 1)
        return {
            "asset_id": assessment.asset_id,
            "policy_version": int(assessment.policy_version),
            "page_url": assessment.page_url,
            "requester": str(assessment.requester),
            "outcome": outcome,
            "reason": reason,
            "transaction_time": assessment.transaction_time,
        }

    @gl.public.view
    def get_latest_assessment(self, asset_id: str, version: u256, page_url: str) -> str:
        require(len(asset_id) == 64, "unknown asset")
        return self.latest.get(digest(digest(asset_id, int(version)), self._page_url(page_url)), "")

    @gl.public.view
    def get_assessment_count(self) -> u256:
        return self.assessment_count
