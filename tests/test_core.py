import pytest
from ghool import core


class TestLookupToken:
    def test_present(self):
        assert core.lookup_token("alice", {"alice": "tok_123"}) == "tok_123"

    def test_missing(self):
        result = core.lookup_token("alice", {})
        assert isinstance(result, core.MissingToken)
        assert result.owner == "alice"

    def test_missing_other_owner_present(self):
        result = core.lookup_token("alice", {"bob": "tok_bob"})
        assert isinstance(result, core.MissingToken)

    def test_missing_to_json(self):
        payload = core.MissingToken("alice").to_json()
        assert payload["error"] == "missing_token"
        assert payload["owner"] == "alice"
        assert "ghool auth setup alice" in payload["suggested_command"]


class TestClassifySmokeTest:
    def test_one_private_repo(self):
        repos = [{"private": True, "name": "r1"}, {"private": False, "name": "r2"}]
        result = core.classify_smoke_test("alice", 200, repos)
        assert isinstance(result, core.ConfidentValid)
        assert result.private_count == 1

    def test_multiple_private(self):
        repos = [{"private": True}, {"private": True}, {"private": False}]
        result = core.classify_smoke_test("alice", 200, repos)
        assert isinstance(result, core.ConfidentValid)
        assert result.private_count == 2

    def test_all_public(self):
        repos = [{"private": False, "name": "r1"}]
        result = core.classify_smoke_test("alice", 200, repos)
        assert isinstance(result, core.WarningNoPrivateRepos)
        assert result.owner == "alice"

    def test_empty_list(self):
        result = core.classify_smoke_test("alice", 200, [])
        assert isinstance(result, core.WarningNoPrivateRepos)

    def test_401(self):
        result = core.classify_smoke_test("alice", 401, [])
        assert isinstance(result, core.Invalid)
        assert result.status_code == 401

    def test_403(self):
        result = core.classify_smoke_test("alice", 403, [])
        assert isinstance(result, core.Invalid)
        assert result.status_code == 403

    def test_404(self):
        result = core.classify_smoke_test("alice", 404, [])
        assert isinstance(result, core.Invalid)
        assert result.status_code == 404

    def test_500(self):
        result = core.classify_smoke_test("alice", 500, [])
        assert isinstance(result, core.Invalid)
        assert result.status_code == 500

    def test_confident_to_json(self):
        payload = core.ConfidentValid("alice", 3).to_json()
        assert payload["success"] is True
        assert payload["verified"] is True

    def test_warning_to_json(self):
        payload = core.WarningNoPrivateRepos("alice").to_json()
        assert payload["success"] is True
        assert payload["verified"] is False
        assert "warning" in payload

    def test_invalid_to_json(self):
        payload = core.Invalid(401, "bad token").to_json()
        assert payload["error"] == "token_rejected"
        assert payload["status_code"] == 401


class TestSecretsRoundTrip:
    def test_roundtrip(self):
        tokens = {"alice": "tok_abc", "bob": "tok_xyz"}
        text = core.format_secrets_toml(tokens)
        assert "KEEP THIS FILE PRIVATE" in text
        assert core.parse_secrets_toml(text) == tokens

    def test_empty(self):
        assert core.parse_secrets_toml(core.format_secrets_toml({})) == {}

    def test_sorted_output(self):
        text = core.format_secrets_toml({"zebra": "z", "apple": "a"})
        assert text.index("apple") < text.index("zebra")

    def test_parse_empty_string(self):
        assert core.parse_secrets_toml("") == {}

    def test_parse_missing_tokens_section(self):
        assert core.parse_secrets_toml("[other]\nfoo = 1\n") == {}


class TestIsGithubPat:
    def test_fine_grained_pat(self):
        assert core.is_github_pat("github_pat_abc123") is True

    def test_classic_pat(self):
        assert core.is_github_pat("ghp_abc123") is True

    def test_random_string(self):
        assert core.is_github_pat("not_a_token") is False

    def test_empty_string(self):
        assert core.is_github_pat("") is False

    def test_partial_prefix(self):
        assert core.is_github_pat("github_pat") is False

    def test_prefix_only_no_body(self):
        assert core.is_github_pat("github_pat_") is False

    def test_body_with_invalid_char(self):
        # A value that passes must be safe to write to secrets.toml.
        assert core.is_github_pat('github_pat_has"quote') is False
        assert core.is_github_pat("ghp_has-hyphen") is False


class TestBuildAuthSetupPayload:
    def test_shape(self):
        payload = core.build_auth_setup_payload("alice")
        assert payload["owner"] == "alice"
        assert "github.com" in payload["browser_url"]
        assert "ghool auth save alice" in payload["next_step"]
        assert "instructions" in payload
        assert "note" in payload


class TestValidateOwner:
    @pytest.mark.parametrize("owner", ["alice", "acme-corp", "a", "a1-b2-c3", "A" * 39])
    def test_valid(self, owner):
        assert core.validate_owner(owner) is None

    @pytest.mark.parametrize("owner", [
        "",
        "-bad",
        "bad-",
        'bad"name',
        "a\\b",
        "has space",
        "with\nnewline",
        "A" * 40,
    ])
    def test_invalid(self, owner):
        result = core.validate_owner(owner)
        assert isinstance(result, core.InvalidOwner)
        assert result.owner == owner

    def test_invalid_to_json(self):
        payload = core.InvalidOwner('bad"name').to_json()
        assert payload["error"] == "invalid_owner"
        assert payload["owner"] == 'bad"name'
        assert "message" in payload


class TestSafePreview:
    def test_fine_grained_pat(self):
        token = "github_pat_" + "A" * 82
        preview = core.safe_preview(token)
        assert preview == "github_pat_AAAA…"
        assert token not in preview  # full token never exposed

    def test_classic_pat(self):
        token = "ghp_" + "B" * 36
        assert core.safe_preview(token) == "ghp_BBBB…"

    def test_non_token_shows_first_four(self):
        assert core.safe_preview("some random text") == "some…"

    def test_random_body_mostly_hidden(self):
        token = "github_pat_" + "0123456789abcdef"
        # Only the first 4 body chars appear; the rest is elided.
        assert core.safe_preview(token) == "github_pat_0123…"
        assert "456789abcdef" not in core.safe_preview(token)
