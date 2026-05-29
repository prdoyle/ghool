from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from typing import Union


# ---------------------------------------------------------------------------
# Token lookup
# ---------------------------------------------------------------------------

@dataclass
class MissingToken:
    owner: str

    def to_json(self) -> dict:
        return {
            "error": "missing_token",
            "owner": self.owner,
            "message": f"No API token configured for owner '{self.owner}'.",
            "suggested_command": f"ghool auth setup {self.owner}",
        }


def lookup_token(owner: str, secrets: dict[str, str]) -> Union[str, MissingToken]:
    """Return the stored token for owner, or MissingToken if not configured."""
    token = secrets.get(owner)
    if not token:
        return MissingToken(owner)
    return token


# ---------------------------------------------------------------------------
# Owner-name validation
# ---------------------------------------------------------------------------

@dataclass
class InvalidOwner:
    owner: str

    def to_json(self) -> dict:
        return {
            "error": "invalid_owner",
            "owner": self.owner,
            "message": (
                f"Owner name '{self.owner}' is not a valid GitHub owner name. "
                "Use only letters, digits, and hyphens (max 39 characters, "
                "starting and ending with a letter or digit)."
            ),
        }


# GitHub usernames/orgs: alphanumeric and hyphens, must start and end
# alphanumeric, up to 39 chars. Gating here keeps owner names safe to use as
# secrets.toml keys (no quotes, backslashes, or newlines reach the serialiser).
_OWNER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")


def validate_owner(owner: str) -> InvalidOwner | None:
    """Return InvalidOwner if owner is not a safe GitHub owner name, else None."""
    if _OWNER_RE.match(owner):
        return None
    return InvalidOwner(owner)


# ---------------------------------------------------------------------------
# Smoke-test result classification
# ---------------------------------------------------------------------------

@dataclass
class ConfidentValid:
    owner: str
    private_count: int

    def to_json(self) -> dict:
        return {
            "success": True,
            "owner": self.owner,
            "verified": True,
            "message": (
                f"Token verified: {self.private_count} private repo(s) visible "
                f"for '{self.owner}'."
            ),
        }


@dataclass
class WarningNoPrivateRepos:
    owner: str

    def to_json(self) -> dict:
        return {
            "success": True,
            "owner": self.owner,
            "verified": False,
            "warning": (
                f"No private repos visible for '{self.owner}'. Token saved, but "
                "scope cannot be confirmed. Verify the token's resource owner is "
                f"'{self.owner}' at github.com/settings/personal-access-tokens."
            ),
        }


@dataclass
class Invalid:
    status_code: int
    reason: str

    def to_json(self) -> dict:
        return {
            "error": "token_rejected",
            "status_code": self.status_code,
            "message": self.reason,
        }


SmokeResult = Union[ConfidentValid, WarningNoPrivateRepos, Invalid]


def classify_smoke_test(owner: str, status_code: int, repos: list) -> SmokeResult:
    """Classify a GitHub repos-list response into a save decision.

    Takes already-fetched HTTP status and response body; makes no network calls.
    Returns ConfidentValid, WarningNoPrivateRepos, or Invalid.
    """
    if status_code == 401:
        return Invalid(status_code, "Token rejected (401 Unauthorized). Check the token value.")
    if status_code == 403:
        return Invalid(
            status_code,
            "Token rejected (403 Forbidden). Grant these Read-only permissions: "
            "Actions, Commit statuses, Contents, Issues, Metadata, Pull requests. "
            "Do NOT add Administration — it allows deleting repos.",
        )
    if status_code == 404:
        return Invalid(status_code, f"Owner '{owner}' not found (404). Check the owner name.")
    if status_code >= 400:
        return Invalid(status_code, f"GitHub API returned {status_code}.")
    private_count = sum(1 for r in repos if r.get("private"))
    if private_count > 0:
        return ConfidentValid(owner, private_count)
    return WarningNoPrivateRepos(owner)


# ---------------------------------------------------------------------------
# Secrets serialisation
# ---------------------------------------------------------------------------

def parse_secrets_toml(text: str) -> dict[str, str]:
    """Parse secrets.toml content and return the tokens dict."""
    data = tomllib.loads(text)
    return {k: str(v) for k, v in data.get("tokens", {}).items()}


def format_secrets_toml(tokens: dict[str, str]) -> str:
    """Serialise a tokens dict to secrets.toml content (sorted by owner name).

    Values are interpolated without escaping: this is safe because owner names
    are gated by validate_owner and token values by is_github_pat, so neither
    can contain quotes, backslashes, or newlines.
    """
    lines = [
        "# KEEP THIS FILE PRIVATE — contains GitHub API tokens\n",
        "# Do not commit or share this file.\n",
        "\n",
        "[tokens]\n",
    ]
    for owner in sorted(tokens):
        lines.append(f'{owner} = "{tokens[owner]}"\n')
    return "".join(lines)


# ---------------------------------------------------------------------------
# Token format validation
# ---------------------------------------------------------------------------

_GITHUB_PAT_PREFIXES = ("github_pat_", "ghp_")
_GITHUB_PAT_RE = re.compile(r"^(?:github_pat_|ghp_)[A-Za-z0-9_]+$")


def is_github_pat(token: str) -> bool:
    """Return True if token looks like a GitHub PAT.

    Requires a known prefix plus a body of only [A-Za-z0-9_], so any value that
    passes this check is also safe to write as a secrets.toml value.
    """
    return bool(_GITHUB_PAT_RE.match(token))


def safe_preview(value: str) -> str:
    """Return an identifying-but-unusable preview of a secret-ish value.

    For a recognised PAT, show the fixed (non-secret) prefix plus the first 4
    characters of the random body — tokens carry dozens of random characters, so
    this always hides far more than enough to make the key unusable while staying
    recognisable. For anything else (e.g. a rejected clipboard value with no
    known prefix), show only the first 4 characters.
    """
    for prefix in _GITHUB_PAT_PREFIXES:
        if value.startswith(prefix):
            return value[:len(prefix) + 4] + "…"
    return value[:4] + "…"


# ---------------------------------------------------------------------------
# Payload builders
# ---------------------------------------------------------------------------

def build_auth_setup_payload(owner: str) -> dict:
    """Build the JSON payload printed by `ghool auth setup`."""
    url = "https://github.com/settings/personal-access-tokens/new"
    return {
        "action": "create_token",
        "owner": owner,
        "browser_url": url,
        "instructions": (
            f"Set 'Resource owner' to '{owner}'. "
            "Grant these Read-only permissions: Actions, Commit statuses, Contents, "
            "Issues, Metadata (required), Pull requests. "
            "Do NOT add Administration — it allows deleting repos. "
            "Scope to 'All repositories' or only the repos you need."
        ),
        "note": (
            f"If '{owner}' is an organisation, it must have fine-grained PATs "
            "enabled (org Settings → Personal access tokens → Allow). "
            "Use one PAT per resource owner — e.g. one for your personal account "
            "(covers forks) and a separate one for each org."
        ),
        "next_step": f"Copy the token to your clipboard, then run: ghool auth save {owner}",
    }
