import json
import stat
import subprocess
from types import SimpleNamespace

import pytest
import responses as rsps
from click.testing import CliRunner

from ghool import paths
from ghool.cli import cli


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """Redirect secrets storage to a tmp dir for each test."""
    config_dir = tmp_path / "ghool"
    secrets_file = config_dir / "secrets.toml"
    monkeypatch.setattr(paths, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(paths, "SECRETS_FILE", secrets_file)
    return tmp_path


def _write_token(isolated, owner, token):
    secrets_dir = isolated / "ghool"
    secrets_dir.mkdir(parents=True, exist_ok=True)
    secrets_file = secrets_dir / "secrets.toml"
    secrets_file.write_text(f'[tokens]\n{owner} = "{token}"\n')
    secrets_file.chmod(0o600)


class TestAuthListKeys:
    def test_empty(self, isolated):
        result = CliRunner().invoke(cli, ["auth", "list-keys"])
        assert result.exit_code == 0
        assert json.loads(result.output) == {"owners": []}

    def test_lists_owners_sorted(self, isolated):
        secrets_dir = isolated / "ghool"
        secrets_dir.mkdir(parents=True, exist_ok=True)
        (secrets_dir / "secrets.toml").write_text(
            '[tokens]\nzara = "github_pat_zzz"\nalice = "github_pat_aaa"\n'
        )
        result = CliRunner().invoke(cli, ["auth", "list-keys"])
        assert result.exit_code == 0
        assert json.loads(result.output) == {"owners": ["alice", "zara"]}


class TestAuthSetup:
    def test_prints_json_and_opens_browser(self, isolated, monkeypatch):
        opened = []
        monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url))
        result = CliRunner().invoke(cli, ["auth", "setup", "alice"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["owner"] == "alice"
        assert "browser_url" in payload
        assert "next_step" in payload
        assert opened == [payload["browser_url"]]


class TestAuthSave:
    def test_reads_from_clipboard(self, isolated, monkeypatch):
        token = "github_pat_" + "secretbody1234567890"
        monkeypatch.setattr(subprocess, "run",
            lambda *a, **kw: SimpleNamespace(stdout=token + "\n"))
        with rsps.RequestsMock() as m:
            m.add(rsps.GET, "https://api.github.com/users/alice/repos",
                  json=[{"private": True}], status=200)
            result = CliRunner().invoke(cli, ["auth", "save", "alice"])
        assert result.exit_code == 0
        assert json.loads(result.stdout)["success"] is True
        # The fixed prefix is fine to show; the full token must never appear.
        assert "github_pat_" in result.stderr
        assert token not in result.stderr

    def test_pbpaste_nonzero_exit(self, isolated, monkeypatch):
        def raise_cpe(*a, **kw):
            raise subprocess.CalledProcessError(1, "pbpaste")
        monkeypatch.setattr(subprocess, "run", raise_cpe)
        result = CliRunner().invoke(cli, ["auth", "save", "alice"])
        assert result.exit_code == 1
        assert json.loads(result.output)["error"] == "clipboard_read_failed"

    def test_empty_clipboard(self, isolated, monkeypatch):
        monkeypatch.setattr(subprocess, "run",
            lambda *a, **kw: SimpleNamespace(stdout="\n"))
        result = CliRunner().invoke(cli, ["auth", "save", "alice"])
        assert result.exit_code == 1
        assert json.loads(result.output)["error"] == "clipboard_not_a_token"

    def test_clipboard_not_a_pat(self, isolated, monkeypatch):
        monkeypatch.setattr(subprocess, "run",
            lambda *a, **kw: SimpleNamespace(stdout="some random text\n"))
        result = CliRunner().invoke(cli, ["auth", "save", "alice"])
        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert payload["error"] == "clipboard_not_a_token"
        assert "suggested_action" in payload
        # Only a 4-char preview is emitted, never the whole clipboard value.
        assert payload["clipboard_preview"] == "some…"
        assert "random text" not in result.output

    def test_pbpaste_not_found(self, isolated, monkeypatch):
        def raise_fnf(*a, **kw):
            raise FileNotFoundError
        monkeypatch.setattr(subprocess, "run", raise_fnf)
        result = CliRunner().invoke(cli, ["auth", "save", "alice"])
        assert result.exit_code == 1
        assert json.loads(result.output)["error"] == "clipboard_unavailable"


class TestAuthSaveEnvVar:
    def _invoke(self, isolated, monkeypatch, token, owner="alice"):
        monkeypatch.setenv("TEST_PAT", token)
        with rsps.RequestsMock() as m:
            m.add(rsps.GET, f"https://api.github.com/users/{owner}/repos",
                  json=[{"private": True}], status=200)
            return CliRunner().invoke(cli, ["auth", "save", owner, "--env-var=TEST_PAT"])

    def test_save_with_private_repos(self, isolated, monkeypatch):
        result = self._invoke(isolated, monkeypatch, "github_pat_abc")
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["success"] is True
        assert payload["verified"] is True
        secrets_file = isolated / "ghool" / "secrets.toml"
        assert secrets_file.exists()
        assert oct(stat.S_IMODE(secrets_file.stat().st_mode)) == oct(0o600)
        assert "github_pat_abc" in secrets_file.read_text()

    def test_save_with_only_public_repos_warns(self, isolated, monkeypatch):
        monkeypatch.setenv("TEST_PAT", "github_pat_abc")
        with rsps.RequestsMock() as m:
            m.add(rsps.GET, "https://api.github.com/users/alice/repos",
                  json=[{"private": False}], status=200)
            result = CliRunner().invoke(cli, ["auth", "save", "alice", "--env-var=TEST_PAT"])
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["verified"] is False
        assert "warning" in payload

    def test_reject_401(self, isolated, monkeypatch):
        monkeypatch.setenv("TEST_PAT", "github_pat_bad")
        with rsps.RequestsMock() as m:
            m.add(rsps.GET, "https://api.github.com/users/alice/repos",
                  json={"message": "Bad credentials"}, status=401)
            result = CliRunner().invoke(cli, ["auth", "save", "alice", "--env-var=TEST_PAT"])
        assert result.exit_code == 1
        assert json.loads(result.stdout)["error"] == "token_rejected"
        assert not (isolated / "ghool" / "secrets.toml").exists()

    def test_env_var_not_set(self, isolated):
        result = CliRunner().invoke(cli, ["auth", "save", "alice", "--env-var=MISSING_VAR"])
        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert payload["error"] == "env_var_not_set"
        assert payload["var_name"] == "MISSING_VAR"

    def test_env_var_not_a_token(self, isolated, monkeypatch):
        monkeypatch.setenv("TEST_PAT", "not-a-token")
        result = CliRunner().invoke(cli, ["auth", "save", "alice", "--env-var=TEST_PAT"])
        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert payload["error"] == "env_var_not_a_token"
        assert payload["value_preview"] == "not-…"
        assert "not-a-token" not in result.output

    def test_preserves_existing_tokens(self, isolated, monkeypatch):
        _write_token(isolated, "bob", "tok_bob")
        self._invoke(isolated, monkeypatch, "github_pat_alice")
        content = (isolated / "ghool" / "secrets.toml").read_text()
        assert "tok_bob" in content
        assert "github_pat_alice" in content

    def test_overwrites_existing_owner(self, isolated, monkeypatch):
        _write_token(isolated, "alice", "github_pat_oldtoken")
        self._invoke(isolated, monkeypatch, "github_pat_newtoken")
        secrets_file = isolated / "ghool" / "secrets.toml"
        content = secrets_file.read_text()
        assert "github_pat_newtoken" in content
        assert "github_pat_oldtoken" not in content
        # chmod 600 must be re-applied on the update path too.
        assert oct(stat.S_IMODE(secrets_file.stat().st_mode)) == oct(0o600)


class TestWithKey:
    def test_runs_gh_with_token(self, isolated, monkeypatch):
        _write_token(isolated, "alice", "github_pat_abc")
        calls = []
        monkeypatch.setattr(subprocess, "run",
            lambda args, env=None: calls.append((args, env)) or SimpleNamespace(returncode=0))
        result = CliRunner().invoke(cli, ["with-key", "alice", "gh", "pr", "list"])
        assert result.exit_code == 0
        assert calls[0][0] == ["gh", "pr", "list"]
        assert calls[0][1]["GH_TOKEN"] == "github_pat_abc"

    def test_passthrough_exit_code(self, isolated, monkeypatch):
        _write_token(isolated, "alice", "github_pat_abc")
        monkeypatch.setattr(subprocess, "run",
            lambda *a, **kw: SimpleNamespace(returncode=2))
        result = CliRunner().invoke(cli, ["with-key", "alice", "gh", "pr", "list"])
        assert result.exit_code == 2

    def test_missing_token(self, isolated):
        result = CliRunner().invoke(cli, ["with-key", "alice", "gh", "pr", "list"])
        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert payload["error"] == "missing_token"
        assert payload["owner"] == "alice"

    def test_rejects_non_gh_command(self, isolated):
        _write_token(isolated, "alice", "github_pat_abc")
        result = CliRunner().invoke(cli, ["with-key", "alice", "curl", "https://example.com"])
        assert result.exit_code == 1
        assert json.loads(result.output)["error"] == "not_gh_command"

    def test_rejects_empty_args(self, isolated):
        _write_token(isolated, "alice", "github_pat_abc")
        result = CliRunner().invoke(cli, ["with-key", "alice"])
        assert result.exit_code == 1
        assert json.loads(result.output)["error"] == "not_gh_command"

    def test_token_not_in_output(self, isolated, monkeypatch):
        _write_token(isolated, "alice", "github_pat_supersecret")
        monkeypatch.setattr(subprocess, "run",
            lambda *a, **kw: SimpleNamespace(returncode=0))
        result = CliRunner().invoke(cli, ["with-key", "alice", "gh", "pr", "list"])
        assert "github_pat_supersecret" not in result.output

    def test_strips_gh_and_github_env_vars(self, isolated, monkeypatch):
        _write_token(isolated, "alice", "github_pat_abc")
        monkeypatch.setenv("GH_REPO", "alice/wrong-repo")
        monkeypatch.setenv("GH_HOST", "github.example.com")
        monkeypatch.setenv("GITHUB_TOKEN", "github_pat_other")
        calls = []
        monkeypatch.setattr(subprocess, "run",
            lambda args, env=None: calls.append((args, env)) or SimpleNamespace(returncode=0))
        CliRunner().invoke(cli, ["with-key", "alice", "gh", "pr", "list"])
        env = calls[0][1]
        assert "GH_REPO" not in env
        assert "GH_HOST" not in env
        assert "GITHUB_TOKEN" not in env

    def test_preserves_non_gh_env_vars(self, isolated, monkeypatch):
        _write_token(isolated, "alice", "github_pat_abc")
        monkeypatch.setenv("MY_VAR", "my_value")
        calls = []
        monkeypatch.setattr(subprocess, "run",
            lambda args, env=None: calls.append((args, env)) or SimpleNamespace(returncode=0))
        CliRunner().invoke(cli, ["with-key", "alice", "gh", "pr", "list"])
        assert calls[0][1].get("MY_VAR") == "my_value"



class TestOwnerValidation:
    def test_setup_rejects_invalid_owner(self, isolated):
        result = CliRunner().invoke(cli, ["auth", "setup", 'bad"owner'])
        assert result.exit_code == 1
        assert json.loads(result.output)["error"] == "invalid_owner"

    def test_save_rejects_invalid_owner(self, isolated):
        # Owner is validated before any clipboard/network/file I/O.
        result = CliRunner().invoke(cli, ["auth", "save", 'bad"owner'])
        assert result.exit_code == 1
        assert json.loads(result.output)["error"] == "invalid_owner"
        assert not (isolated / "ghool" / "secrets.toml").exists()

    def test_with_key_rejects_invalid_owner(self, isolated):
        result = CliRunner().invoke(cli, ["with-key", 'bad"owner', "gh", "pr", "list"])
        assert result.exit_code == 1
        assert json.loads(result.output)["error"] == "invalid_owner"


class TestSkill:
    def test_has_yaml_frontmatter(self, isolated):
        result = CliRunner().invoke(cli, ["skill"])
        assert result.exit_code == 0
        lines = result.output.split("\n")
        assert lines[0] == "---"
        closing = lines.index("---", 1)
        assert closing > 1

    def test_contains_usage_pattern(self, isolated):
        result = CliRunner().invoke(cli, ["skill"])
        assert "ghool with-key OWNER gh" in result.output

    def test_documents_all_commands(self, isolated):
        # Derive command names from the live Click tree so adding/renaming a
        # command without documenting it in skill.md fails the test.
        out = CliRunner().invoke(cli, ["skill"]).output

        def leaves(group, prefix=""):
            for name, cmd in group.commands.items():
                path = f"{prefix} {name}".strip()
                if getattr(cmd, "commands", None):
                    yield from leaves(cmd, path)
                else:
                    yield path

        for cmd in leaves(cli):
            assert cmd in out, f"{cmd!r} not documented in skill.md"
