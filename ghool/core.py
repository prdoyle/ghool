from __future__ import annotations

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
            "Token rejected (403 Forbidden). Ensure the token has Contents and Metadata read permissions.",
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
    """Serialise a tokens dict to secrets.toml content (sorted by owner name)."""
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


def is_github_pat(token: str) -> bool:
    """Return True if token looks like a GitHub PAT."""
    return any(token.startswith(p) for p in _GITHUB_PAT_PREFIXES)


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
            "Grant 'Contents: Read-only' and 'Metadata: Read-only'. "
            "Scope to only the repositories you need."
        ),
        "note": (
            f"If '{owner}' is an organisation, it must have fine-grained PATs "
            "enabled (org Settings → Personal access tokens → Allow)."
        ),
        "next_step": f"Copy the token to your clipboard, then run: ghool auth save {owner}",
    }
