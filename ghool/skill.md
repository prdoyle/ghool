---
name: ghool-usage
description: "Use instead of bare gh commands when querying GitHub repos — supplies the right fine-grained PAT per owner so private repos and forks are never silently omitted from results."
---

# Using ghool

ghool stores fine-grained GitHub PATs by owner name and runs `gh` commands with
the right token automatically, so private repos and forks are never silently
omitted. Each PAT is scoped to a single resource owner (personal account or one
org); ghool dispatches the right token for each call.

## Recommended usage pattern

    ghool with-key OWNER gh COMMAND

Examples:

    ghool with-key alice gh pr list --repo alice/my-repo
    ghool with-key alice gh api repos/alice/private-fork/events?per_page=100
    ghool with-key acme-corp gh api repos/acme-corp/internal-tool/contents/README.md

## Processing JSON output

Use `jq` to filter and extract fields from `gh` output — not Python. Piping
into Python requires an extra permission prompt every time; `jq` does not.

    ghool with-key alice gh pr list --repo alice/my-repo --json number,title | jq '.[] | .title'
    ghool with-key alice gh api repos/alice/my-repo/events?per_page=100 | jq '.[0].type'

## Commands

- `ghool with-key OWNER gh ARGS` — run a `gh` command with the stored PAT for
  OWNER injected as `GH_TOKEN`. Only `gh` is accepted; other programs are
  rejected. Exit code matches `gh`'s. Preferred for all agent use.
- `ghool auth list-keys` — lists all owners with stored PATs as JSON `{"owners": [...]}`.
- `ghool auth setup OWNER` — opens the browser to create a fine-grained PAT for
  OWNER; prints JSON with required permissions and the next command to run.
- `ghool auth save OWNER` — reads the PAT from the clipboard (macOS only),
  validates it, and stores it. Preferred for interactive use.
- `ghool auth save OWNER --env-var=VAR` — reads the PAT from environment
  variable VAR instead of the clipboard. Use this in non-interactive or scripted
  contexts: `MY_PAT=github_pat_... ghool auth save OWNER --env-var=MY_PAT`.
  Prints JSON success/warning/error.
- `ghool skill` — prints this file.

OWNER must be a valid GitHub owner name (letters, digits, and hyphens). Any
command rejects an invalid name with `{"error": "invalid_owner", ...}` and exit 1.

## Smoke-test behaviour of `auth save`

- Private repos visible → saves with `{verified: true}` (high confidence).
- Only public repos visible → saves with `{verified: false, warning: ...}`.
- 401/403/404 → rejects, nothing written, exits 1.

## Recovery from missing-token errors

If `ghool with-key OWNER gh ...` exits 1 with `{"error": "missing_token", ...}`:

1. Run `ghool auth setup OWNER` — opens the browser and prints JSON.
2. Show the `instructions`, `note`, and `next_step` fields from that JSON verbatim
   to the user. Do not paraphrase them. Then wait for the user to act.
3. Once the user indicates they have saved a token, run `ghool auth save OWNER`
   (or `MY_PAT=<token> ghool auth save OWNER --env-var=MY_PAT` if non-interactive).
