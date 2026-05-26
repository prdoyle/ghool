import os
from pathlib import Path

from ghool import core

_xdg = os.environ.get("XDG_CONFIG_HOME")
CONFIG_DIR: Path = Path(_xdg) / "ghool" if _xdg else Path.home() / ".config" / "ghool"
SECRETS_FILE: Path = CONFIG_DIR / "secrets.toml"


def read_secrets() -> dict[str, str]:
    """Read and parse secrets.toml; return empty dict if the file doesn't exist."""
    if not SECRETS_FILE.exists():
        return {}
    return core.parse_secrets_toml(SECRETS_FILE.read_text())


def write_secrets(tokens: dict[str, str]) -> None:
    """Write tokens to secrets.toml, creating parent dirs and applying chmod 600."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SECRETS_FILE.write_text(core.format_secrets_toml(tokens))
    SECRETS_FILE.chmod(0o600)
