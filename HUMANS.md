# ghool — Human Setup Guide

GitHub fine-grained PATs are scoped to a single resource owner — one personal
account or one org. If you need access to repos under both (e.g. `myname` and
`acme-corp`), you need one PAT each. ghool stores them by owner name and supplies
the right one to `gh` on demand.

## Install

```bash
/path/to/ghool/install.sh
```

The script can be run from any directory.

## Save a token

**Step 1** — Open the GitHub token creation page for an owner:

```bash
ghool auth setup OWNER
```

**Step 2** — In the browser: set resource owner to OWNER, grant **Contents**
and **Metadata** (both read-only), choose which repos to scope it to, then
generate and copy the token.

**Step 3** — Copy the token to your clipboard, then save it:

```bash
ghool auth save OWNER
```

Repeat for each owner. Tokens are saved to `~/.config/ghool/secrets.toml`
(mode 600).

## Use a token

```bash
GH_TOKEN=$(ghool secret-token OWNER) gh COMMAND
```

Examples:

```bash
GH_TOKEN=$(ghool secret-token alice) gh repo list alice --limit 50
GH_TOKEN=$(ghool secret-token acme-corp) gh pr list --repo acme-corp/website
```

## Install the Claude skill

```bash
mkdir -p ~/.claude/skills/ghool
ghool skill > ~/.claude/skills/ghool/SKILL.md
```

## Run tests

```bash
pytest
```
