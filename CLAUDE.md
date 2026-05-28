# ghool

ghool is a GitHub PAT key management tool for LLM agent use. It stores
fine-grained GitHub PATs by owner name and prints them on demand for use with
`GH_TOKEN`. It is a key-management layer, not a `gh` replacement — the PAT
itself is the security boundary.

Primary usage pattern:

    ghool with-key OWNER gh COMMAND

## Architecture

Four source modules, each with a single responsibility:

- `core.py` — pure functions (no I/O, no globals). All decision logic lives here.
- `paths.py` — filesystem I/O: read/write `secrets.toml`.
- `smoketest.py` — HTTP I/O: the one GitHub API call used by `auth save`. This
  is the only file in the package that makes network requests.
- `cli.py` — Click commands. Thin glue: read from `paths`/`smoketest`, call
  `core`, write to stdout. Minimal branching; no decision logic of its own.

New decision logic goes in `core.py` with unit tests in `tests/test_core.py`.
New commands get a function in `cli.py` plus tests in `tests/test_cli.py`.

## Mandatory: update `skill.md` on any CLI change

Any change that alters command surface, output JSON shape, or recovery flow
MUST also update `ghool/skill.md`. The skill test verifies the file parses as
YAML-frontmatter markdown; correctness of content is the engineer's
responsibility.

## Testing

    pip install -e ".[dev]"
    .venv/bin/pytest

- `tests/test_core.py` — unit tests for every function in `core.py`
- `tests/test_cli.py` — integration tests using Click `CliRunner`, `tmp_path`,
  and `responses` (mocked HTTP; no real network)

## Dependencies

Runtime: `click`, `requests`. Keep it at two. Dev: `pytest`, `responses`.
Resist adding runtime deps.

## Security

- Secrets file written with `chmod 600` on every save.
- Never log token values anywhere.
- Never include token values in any error payload printed to stdout.

## Examples and documentation

Use only fictional, generic names in all examples — owner names, repo names,
org names, etc. Never use real GitHub usernames, real org names, or real repo
names (even well-known public ones). Prefer placeholder names like `alice`,
`acme-corp`, `my-repo`.
