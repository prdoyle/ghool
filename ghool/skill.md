---
name: ghool-usage
description: "Use instead of bare gh commands when querying GitHub repos — supplies the right fine-grained PAT per owner so private repos and forks are never silently omitted from results."
---

# Using ghool

ghool stores fine-grained GitHub PATs by owner name and prints them on demand,
so you can run `gh` commands against private repos without granting overly broad
OAuth scopes. Each PAT is scoped to a single resource owner (personal account or
one org); ghool dispatches the right token for each call.

## Token routing pattern

    TOKEN=$(ghool secret-token OWNER) && GH_TOKEN=$TOKEN gh COMMAND

Examples:

    TOKEN=$(ghool secret-token alice) && GH_TOKEN=$TOKEN gh api repos/alice/private-fork/events?per_page=100
    TOKEN=$(ghool secret-token acme-corp) && GH_TOKEN=$TOKEN gh api repos/acme-corp/internal-tool/contents/README.md

## Commands

- `ghool secret-token OWNER` — prints the stored PAT for OWNER. Use only via
  `$(...)` capture; never run bare as it prints a secret to stdout.
- `ghool auth setup OWNER` — opens the browser to create a fine-grained PAT for
  OWNER; prints JSON with required permissions and the next command to run.
- `ghool auth save OWNER` — reads the PAT from the clipboard (macOS only),
  validates it, and stores it. Preferred for interactive use.
- `ghool auth save OWNER --env-var=VAR` — reads the PAT from environment
  variable VAR instead of the clipboard. Use this in non-interactive or scripted
  contexts: `MY_PAT=github_pat_... ghool auth save OWNER --env-var=MY_PAT`.
  Prints JSON success/warning/error.
- `ghool skill` — prints this file.

## Smoke-test behaviour of `auth save`

- Private repos visible → saves with `{verified: true}` (high confidence).
- Only public repos visible → saves with `{verified: false, warning: ...}`.
- 401/403/404 → rejects, nothing written, exits 1.

## Recovery from missing-token errors

If `ghool secret-token OWNER` exits 1 with `{"error": "missing_token", ...}`:

1. Run `ghool auth setup OWNER` — opens the browser and prints JSON.
2. Show the `instructions`, `note`, and `next_step` fields from that JSON verbatim
   to the user. Do not paraphrase them. Then wait for the user to act.
3. Once the user indicates they have saved a token, run `ghool auth save OWNER`
   (or `MY_PAT=<token> ghool auth save OWNER --env-var=MY_PAT` if non-interactive).
