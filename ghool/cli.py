import json
import os
import subprocess
import sys
import webbrowser
from pathlib import Path

import click

from ghool import core, paths, smoketest


@click.group()
def cli():
    """ghool — route fine-grained GitHub PATs to gh commands by repo owner.

    Primary usage pattern:

        ghool with-key OWNER gh COMMAND

    Run any subcommand with --help for details on inputs, outputs, and errors.
    """


@cli.group("auth")
def cmd_auth():
    """Manage stored GitHub PATs."""


@cmd_auth.command("setup")
@click.argument("owner")
def cmd_auth_setup(owner):
    """Open browser to create a fine-grained GitHub PAT for OWNER.

    OWNER is the GitHub username or org name to create the PAT for.

    Opens github.com/settings/personal-access-tokens/new in the default browser
    and prints JSON instructions to stdout.

    On success (exit 0): JSON to stdout.
      {action, owner, browser_url, instructions, note, next_step}

    After creating the token in the browser, run: ghool auth save OWNER
    """
    payload = core.build_auth_setup_payload(owner)
    click.echo(json.dumps(payload, indent=2))
    webbrowser.open(payload["browser_url"])


@cmd_auth.command("save")
@click.argument("owner")
@click.option("--env-var", default=None, metavar="VAR",
              help="Read token from this environment variable instead of the clipboard.")
def cmd_auth_save(owner, env_var):
    """Validate a PAT and store it for OWNER.

    OWNER is the GitHub username or org the token is scoped to.

    By default, reads the token from the clipboard via pbpaste (macOS only).
    Use --env-var=VAR to read from an environment variable instead — this works
    on any platform and keeps the token out of the command line and shell history.

    Example (non-interactive/scripted):
        MY_PAT=github_pat_... ghool auth save OWNER --env-var=MY_PAT

    Smoke-tests the token by listing OWNER's repos via the GitHub API, then:
    - Saves and exits 0 if private repos are visible (token verified).
    - Saves with a warning and exits 0 if only public repos are visible.
    - Rejects and exits 1 if the token is invalid (401/403/404).

    Saves to ~/.config/ghool/secrets.toml (chmod 600).

    On verified success (exit 0): JSON {success: true, owner, verified: true, message}
    On unverified success (exit 0): JSON {success: true, owner, verified: false, warning}
    On rejection (exit 1): JSON {error, status_code, message} — nothing saved.
    On network error (exit 1): JSON {error: "network_error", message}
    On input errors (exit 1): JSON {error, message}
    """
    if env_var is not None:
        token = os.environ.get(env_var)
        if token is None:
            click.echo(json.dumps({
                "error": "env_var_not_set",
                "var_name": env_var,
                "message": f"Environment variable {env_var!r} is not set.",
            }))
            sys.exit(1)
        if not core.is_github_pat(token):
            preview = (token[:40] + "...") if len(token) > 40 else token
            click.echo(json.dumps({
                "error": "env_var_not_a_token",
                "var_name": env_var,
                "value_preview": preview,
                "message": f"{env_var!r} does not contain a GitHub PAT (expected github_pat_... or ghp_...).",
            }))
            sys.exit(1)
        click.echo(f"Read token from ${env_var}: {token[:20]}...", err=True)
    else:
        try:
            proc = subprocess.run(["pbpaste"], capture_output=True, text=True, check=True)
        except FileNotFoundError:
            click.echo(json.dumps({
                "error": "clipboard_unavailable",
                "message": "pbpaste not found — clipboard reading is macOS only. Use --env-var=VAR to read from an environment variable.",
            }))
            sys.exit(1)
        token = proc.stdout.strip()
        if not core.is_github_pat(token):
            preview = (token[:40] + "...") if len(token) > 40 else token
            click.echo(json.dumps({
                "error": "clipboard_not_a_token",
                "clipboard_preview": preview,
                "message": "Clipboard does not contain a GitHub PAT (expected github_pat_... or ghp_...). Copy the token from GitHub and run this command again.",
                "suggested_action": f"Ask the user to copy their GitHub PAT to the clipboard, then run: ghool auth save {owner}",
            }))
            sys.exit(1)
        click.echo(f"Read token from clipboard: {token[:20]}...", err=True)

    try:
        status, repos = smoketest.list_repos(owner, token)
    except smoketest.NetworkError as exc:
        click.echo(json.dumps({"error": "network_error", "message": str(exc)}))
        sys.exit(1)

    result = core.classify_smoke_test(owner, status, repos)
    if isinstance(result, core.Invalid):
        click.echo(json.dumps(result.to_json()))
        sys.exit(1)

    secrets = paths.read_secrets()
    secrets[owner] = token
    paths.write_secrets(secrets)
    click.echo(json.dumps(result.to_json()))


@cli.command("with-key", context_settings=dict(allow_extra_args=True, ignore_unknown_options=True))
@click.argument("owner")
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def cmd_with_key(owner, args):
    """Run a gh command using the stored PAT for OWNER.

    OWNER is the GitHub username or org name the token was saved under.
    The remaining arguments must begin with 'gh'.

    This is the recommended way for agents to invoke gh — the token is
    injected automatically and never appears on the command line.

    Only 'gh' is accepted as the command; other programs are rejected.

    Examples:
        ghool with-key alice gh pr list --repo alice/my-repo
        ghool with-key acme-corp gh api repos/acme-corp/internal-tool/issues

    On missing token (exit 1): JSON to stdout.
      {error, owner, message, suggested_command}
    On disallowed command (exit 1): JSON to stdout.
      {error, message}
    On success: gh output flows through directly; exit code matches gh's.
    """
    if not args or args[0] != "gh":
        click.echo(json.dumps({
            "error": "not_gh_command",
            "message": (
                "ghool with-key only runs gh. "
                "Usage: ghool with-key OWNER gh ARGS"
            ),
        }))
        sys.exit(1)

    secrets = paths.read_secrets()
    result = core.lookup_token(owner, secrets)
    if isinstance(result, core.MissingToken):
        click.echo(json.dumps(result.to_json()))
        sys.exit(1)

    # Strip GH_* and GITHUB_* to prevent stray env vars (e.g. GH_REPO, GH_HOST)
    # from silently misdirecting commands to the wrong repo or host.
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("GH_", "GITHUB_"))}
    env["GH_TOKEN"] = result
    proc = subprocess.run(list(args), env=env)
    sys.exit(proc.returncode)


@cli.command("skill")
def cmd_skill():
    """Print the ghool Claude skill file to stdout.

    Outputs a Claude-compatible skill file (YAML frontmatter + markdown body)
    describing how LLM agents should use ghool. Suitable for:

        ghool skill > ~/.claude/skills/ghool/SKILL.md

    On success (exit 0): skill file content on stdout.
    """
    skill_path = Path(__file__).parent / "skill.md"
    click.echo(skill_path.read_text(), nl=False)
