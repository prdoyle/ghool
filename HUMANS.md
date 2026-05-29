# ghool — Human Setup Guide

GitHub fine-grained PATs are scoped to a single resource owner — one personal
account or one org. If you need access to repos under both (e.g. `myname` and
`acme-corp`), you need one PAT each. ghool stores them by owner name and supplies
the right one to `gh` on demand.

**Not sure where you're at?** Run `./install.sh --status` to see what's done
and what remains.

## Install

```bash
/path/to/ghool/install.sh
```

The script is safe to re-run — it skips steps that are already complete. It
also installs the Claude skill so LLM agents know how to use ghool.

## Save a token

**Step 1** — Open the GitHub token creation page for an owner:

```bash
ghool auth setup OWNER
```

**Step 2** — In the browser: set resource owner to OWNER,
grant the permissions recommended in the output from Step 1,
choose which repos to scope it to, then generate and copy the token.
Read-only access is usually sufficient.
**Don't grant any permissions you're uncomfortable granting!**

**Step 3** — Copy the token to your clipboard, then save it:

```bash
ghool auth save OWNER
```

This command reads the token out of the clipboard.

Repeat for each owner. Tokens are saved to `~/.config/ghool/secrets.toml`
(mode 600).

## Use a token

```bash
ghool with-key OWNER gh COMMAND
```

Examples:

```bash
ghool with-key alice gh repo list alice --limit 50
ghool with-key acme-corp gh pr list --repo acme-corp/website
```

## Claude Code setup

`install.sh` automatically adds `Bash(ghool with-key *)` to your
`~/.claude/settings.json`, so LLM agents can run `ghool with-key` without a
permission prompt on every call. Run `./install.sh --status` to confirm.

The fine-grained PAT is the security boundary: it can only reach the repos and
actions it was granted, regardless of what `gh` command is run.

## Run tests

```bash
pytest
```
