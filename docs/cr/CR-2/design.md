# CR-2 Design: Stage 1 workspace foundation

| Field | Value |
|---|---|
| CR | issue #2 (Class 3) |
| Governing records | ADR-001 (sections 2, 4a, 5), ADR-003 (sections 2-8), baseline v0.1 (sections 3, 6, 7) |
| New record | [ADR-005](../../adr/ADR-005-toolchain.md) (Proposed) |
| Scope | Design only. No scripts, Ansible roles, or workflows are added by this PR. |

## 1. Goal and scope

Stage 1 exit criteria (baseline section 6): the workspace is restorable (AC1-7) and CI is green on a test PR.
This design covers five deliverables and the ADR that records the toolchain decision:

| Part | Deliverable | Section |
|---|---|---|
| a | Toolchain manifest, install engine, Ansible layout with `builder` and `lab` profiles | 3 |
| b | `workspace/restore.sh` and `workspace/verify.sh` | 4 |
| c | `scripts/quality-gate.sh` | 5 |
| d | `scripts/pr-contract` (rules PC-1 to PC-7) | 6 |
| e | CI skeleton and the check names to require later | 7 |

Out of scope: `lab` profile content (Stage 3), `labctl`, OCI stacks, backup, the software template, repository settings and rulesets.

## 2. Decisions in this design

| ID | Decision | Rationale |
|---|---|---|
| S1-1 | One install engine, `scripts/toolchain` (Python 3, standard library only), used by Ansible, CI, and verification. | One implementation of download, verify, and extract, so amd64, arm64, Ansible, and CI cannot drift. Testable without root. |
| S1-2 | The manifest is TOML (`toolchain/manifest.toml`). | `tomllib` is in the standard library of both Debian 13 (Python 3.13) and Ubuntu 24.04 (Python 3.12). It allows comments and needs no YAML library. |
| S1-3 | Checksums are mandatory for every download, for both architectures. Signatures are verified additionally where upstream publishes them. | CLAUDE.md supply-chain rule; ADR-001 section 5 (manifest as the allowlist). |
| S1-4 | Ansible installs system packages and configuration, then calls the install engine. It does not download tools itself. | See S1-1. |
| S1-5 | `pr-contract` is Python 3 (standard library), fetches PR data from the API itself, and runs from the base branch checkout. | PR text never reaches a shell; the PR cannot alter the checker that judges it (section 6). |
| S1-6 | The quality gate is a dispatcher plus small check scripts with one result contract. | Small, focused files; concise output; same entry point locally and in CI. |
| S1-7 | CI has no path filters on jobs that will become required checks. | A skipped required check blocks merging forever. |

## 3. Toolchain manifest and Ansible layout (part a)

### 3.1 Repository layout

```text
toolchain/
  manifest.toml              # tools, versions, per-arch URLs and checksums, install source
  python/
    builder.lock             # hash-locked pip requirements (universal resolution, both arches)
scripts/
  toolchain                  # install engine: check | list | install | verify
ansible/
  ansible.cfg
  inventory/localhost.yml
  group_vars/all.yml         # prefix, manifest path, arch map
  builder.yml                # profile playbook: Debian 13, x86-64 (fully specified)
  lab.yml                    # profile playbook: Ubuntu 24.04, ARM64 (placeholder, Stage 3)
  roles/
    apt_base/                # system packages
    toolchain/               # calls scripts/toolchain install --profile
    python_tools/            # venv + hash-locked pip
    shell_env/               # PATH for the install prefix
    rootless_podman/         # builder only
    claude_managed_settings/ # optional, default off (section 3.6)
    verify/                  # calls scripts/toolchain verify
```

### 3.2 Manifest format

A tool is one table under `tools`. `source` selects one of three install sources.

| `source` | Meaning | Trust anchor |
|---|---|---|
| `download` | Release artifact fetched by URL, verified by SHA-256 | Checksum in the manifest, reviewed in a toolchain PR |
| `apt` | Package from the target release's signed archive | Distribution archive signature (see 3.5 and open question 1) |
| `pip` | Hash-locked Python packages in a venv | `--require-hashes` against `toolchain/python/builder.lock` |

Illustrative `download` entry (values are placeholders; real versions and checksums are chosen and verified during implementation):

```toml
schema_version = 1

[tools.shellcheck]
version     = "<x.y.z>"                 # exact; no ranges, no "latest"
profiles    = ["builder", "lab"]
source      = "download"
format      = "tar.xz"                  # binary | tar.gz | tar.xz | zip
strip       = 1                         # leading path components removed on extract
binaries    = ["shellcheck"]            # paths after strip; linked into <prefix>/bin
smoke       = ["shellcheck", "--version"]
smoke_match = "<x.y.z>"                 # substring that must appear in the output
max_bytes   = 52428800                  # optional download cap; default 512 MiB

[tools.shellcheck.artifacts.amd64]
url    = "https://<host>/<path>/v<x.y.z>/<linux-x86_64-artifact>"
sha256 = "<64 lowercase hex characters>"

[tools.shellcheck.artifacts.arm64]
url    = "https://<host>/<path>/v<x.y.z>/<linux-aarch64-artifact>"
sha256 = "<64 lowercase hex characters>"
# optional, in addition to the checksum:
# signature = { type = "cosign" | "minisign" | "gpg", url = "...", key = "<fingerprint or key file>" }
```

Illustrative `apt` and `pip` entries:

```toml
[tools.git]
version_min = "<epoch:upstream>"        # see open question 1
profiles    = ["builder", "lab"]
source      = "apt"
package     = "git"
smoke       = ["git", "--version"]

[tools.python-lint]
profiles = ["builder"]
source   = "pip"
lockfile = "toolchain/python/builder.lock"
binaries = ["yamllint", "pymarkdown"]   # linked from the venv into <prefix>/bin
```

Rules enforced by `scripts/toolchain check` (static, no network):

1. Every `download` tool has both `amd64` and `arm64` artifacts, regardless of profile.
2. `sha256` is 64 lowercase hex characters. URLs are `https`. No `latest`, no version ranges, no `http`, no shell metacharacters in any field.
3. `profiles` is a non-empty subset of `builder`, `lab`. `binaries` names are unique across tools.
4. `smoke` is an argument array (never a shell string). `smoke_match` is required for `download` and `pip`.
5. The version string appears in each artifact URL (catches a version bump that forgot a URL).
6. `schema_version` is known. Unknown keys are errors.

The online counterpart (`scripts/toolchain verify --download`) downloads every artifact for the runner's architecture and compares checksums. It runs in CI on both architectures (section 7).

### 3.3 Install engine (`scripts/toolchain`)

| Subcommand | Behavior |
|---|---|
| `check` | Static manifest validation (above). Exit 0 or 1. |
| `list --profile P [--arch A]` | Print tool, version, source. |
| `install --profile P --prefix DIR [--arch A] [--only TOOL] [--dry-run]` | Fetch, verify, extract, link. Architecture defaults to the host (`x86_64` maps to `amd64`, `aarch64` to `arm64`; anything else is an error). |
| `verify --profile P --prefix DIR [--download]` | Run every `smoke` command and compare to `smoke_match`. With `--download`, also re-verify upstream checksums. |

Install semantics:

- Layout: `<prefix>/tools/<name>/<version>/`, symlinks in `<prefix>/bin`, venv in `<prefix>/venv`. Production prefix is `/opt/ai-lab`; CI uses a temporary prefix.
- Download into a private staging directory (mode 0700) under the prefix. Stream the file through SHA-256 and compare before anything is extracted. A mismatch deletes the staging directory and exits non-zero. TLS verification is never disabled. Redirects must stay on `https`. A size cap applies.
- Extraction is done in Python (`tarfile` with the `data` filter, `zipfile` with explicit member checks). Absolute paths, `..` components, links that leave the destination, device files, and setuid bits are rejected.
- Install is atomic: extract into staging, then rename into `<version>/`, then replace symlinks with rename. A partial install is never visible.
- Idempotent: a stamp file records the verified checksum. When the stamp matches the manifest and the smoke command passes, the tool is skipped.
- `--dry-run` performs no download and writes nothing. It prints the plan (tool, version, URL, destination, action: install, upgrade, or skip) and exits 0.
- Output is one line per tool plus a summary. Failures print the tool, the step, and the first error only.
- Exit codes: 0 success, 1 verification or install failure, 2 usage or manifest error.

### 3.4 Ansible layout and profiles

- Local execution only: `ansible-playbook -i inventory/localhost.yml ansible/builder.yml` with `connection: local`. Nothing in this repo reaches the lab VM from the workspace (CLAUDE.md).
- A profile is a playbook that lists roles and sets `profile: builder` or `profile: lab`. Tool membership comes from the manifest `profiles` field, so adding a tool never edits a playbook.
- `builder.yml` pre-tasks assert Debian 13 and `x86_64` and fail with one clear message otherwise.
- `lab.yml` is a placeholder in Stage 1. It asserts Ubuntu 24.04 and `aarch64`, lists the roles it will use, and then fails with "lab profile is implemented in Stage 3". It must pass `ansible-playbook --syntax-check` so the structure is validated early.
- Roles are idempotent. The `toolchain` role maps the install engine's result to `changed` (stdout line `changed=<n>`), and runs it with `--dry-run` under Ansible check mode.
- Privilege: only `apt_base`, `shell_env`, `rootless_podman`, and writes under `/opt/ai-lab` use `become`. When Ansible already runs as root (the CI container), `become` is disabled.
- Test levels used by this CR (aligned with ADR-001 O-1 and D15):
  - L1, static, on any host: `scripts/toolchain check`, `ansible-playbook --syntax-check` for both profiles, the quality gate.
  - L2, executed on GitHub runners: install and smoke for amd64 (`ubuntu-24.04`) and arm64 (`ubuntu-24.04-arm`); full `builder` profile apply inside a pinned `debian:13` container.
  - L3, on the real host: `workspace/restore.sh` on the workspace (AC1-7). The lab VM follows in Stage 3.

### 3.5 Builder profile content (proposed)

| Group | Contents | Source |
|---|---|---|
| Repository tooling | `gh`, `yq` (mikefarah), `rg`, `fd`, `jq` | `download` (`jq` may be `apt`) |
| Validation | `shellcheck`, `actionlint`, OpenTofu (`fmt`, `validate`), `yamllint`, a Markdown linter | `download`; `pip` for `yamllint` and the Markdown linter |
| Runtime | `python3`, `python3-venv`, `ansible-core`, `git`, `curl`, `ca-certificates`, `tmux` | `apt` |
| Containers | Rootless Podman, `uidmap`, `passt` | `apt` (O-10 proposal; open question 4) |

Notes:

- `fd` is installed from a release artifact so the binary is named `fd` (the Debian package installs `fdfind`). CLAUDE.md and `.claude/settings.json` expect `fd`; it is not installed on the workspace today.
- Ansible is bootstrapped from the Debian archive (`apt install ansible-core`) by `restore.sh`, because Ansible must exist before it can apply a profile. This is the only tool that is not installed through the manifest. It is recorded as a minimum version in the manifest and checked by `verify`.
- Claude Code itself is not installed here. Claude Desktop deploys its engine under `~/.claude/remote/` (ADR-001 section 4a, step 6).
- OpenTofu is proposed because ADR-002 specifies HCL compatible with OpenTofu. `tofu apply`, `destroy`, and `import` stay denied by `.claude/settings.json`.

### 3.6 Guardrails on the workspace

ADR-001 section 5 allows managed settings on the workspace only if root is available and no corporate managed settings exist. Stage 1 does not write managed settings. It restores user-level settings and relies on the repository `.claude/settings.json` (RR-8, lower assurance). The role `claude_managed_settings` exists as an opt-in (`claude_managed_settings_enabled: false`) and refuses to run if `/etc/claude-code/managed-settings.json` already exists (merge, never replace). Whether to enable it is open question 5.

## 4. `workspace/restore.sh` (part b)

Implements ADR-001 section 4a. The target is a verified workspace within 15 minutes, with token T1 as the only manual input (AC1-7).

### 4.1 Files

```text
workspace/
  restore.sh        # orchestrator (this section)
  verify.sh         # workspace verification (also runnable alone)
  repos.txt         # one repository name per line, owner taken from config/project.yaml
  claude-user/      # user-level Claude Code configuration restored into ~/.claude/
  lib/              # small sourced helpers (log, config, preflight)
```

### 4.2 Interface

```text
workspace/restore.sh [--dry-run] [--reauth] [--skip-clone] [--help]
```

| Option | Effect |
|---|---|
| `--dry-run` | Read-only plan. No apt, no Ansible apply, no file writes, no token prompt, no clone. Prints each action as `[dry-run] <step>: <what would happen>`. When `ansible-core` is installed it also runs the playbook in check mode (`--check --diff`). |
| `--reauth` | Run the token step even if `gh` is already logged in. |
| `--skip-clone` | Skip step 5 clones (used to re-run only the verification). |

Exit codes: 0 restored and verified; 1 restore finished but verification failed; 2 usage or preflight error (nothing changed); 3 a restore step failed.

Script conventions: `set -euo pipefail`, ShellCheck-clean, refuses `set -x` (`[[ $- == *x* ]]` aborts), no `eval`, all expansions quoted.

### 4.3 Preflight (before any change)

1. Debian 13 on `x86_64`, not root (the script calls `sudo` only for the steps that need it).
2. Not inside a Claude Code session: abort if the shell shows Claude Code session markers, and abort when stdin is not a terminal. Claude Code's shell has no TTY, so the token prompt cannot be reached from a Claude session (AC1-8). Marker names are verified during implementation.
3. Running from a clone of this repository (the script locates the repo root relative to its own path).
4. Network reachability of the Debian archive and the GitHub hosts (a HEAD request, no credentials).

### 4.4 Steps (same order as ADR-001 section 4a, steps 3 to 5)

| # | Step | Actions | Idempotence |
|---|---|---|---|
| 1 | System and toolchain | `sudo -v` (the sudo prompt belongs to `sudo`; the script never reads a password). Install `ansible-core` from apt if absent. Run `ansible-playbook ansible/builder.yml`. | Ansible and the install engine skip what is present and verified. |
| 2 | Claude user config | Copy files from `workspace/claude-user/` into `~/.claude/` using an allowlist of paths (settings, user instructions, rules). Never delete anything and never touch `~/.claude/remote/`, session state, or any credential file. A differing existing file is backed up as `<name>.bak.<timestamp>`. | Compare content; copy only on difference. |
| 3 | Git identity | Set `user.name` to `machine_login` from `config/project.yaml`. Set `user.email` to the machine account's noreply address, built at run time from the public profile lookup for that login. No email address is stored in the repository. | `git config --global` is repeatable. |
| 4 | Token T1 | See 4.5. | Skipped when `gh auth status` succeeds, unless `--reauth`. |
| 5 | Repositories | `gh auth setup-git`. For each name in `repos.txt`, clone into `~/work/<name>` when absent, otherwise `git fetch`. For each open PR authored by `machine_login`, create a local tracking branch for its head (no checkout switching). Print the list. | Existing clones are fetched, never reset. A dirty working tree is reported, not touched. |
| 6 | Verification | Run `workspace/verify.sh` (4.6). | Read-only. |

Each step prints elapsed time. The summary line reports total time against the 15-minute target.

### 4.5 Token prompt (step 4)

- The token is read only from an interactive terminal: `IFS= read -rs -p 'Token T1: ' token` with the prompt on stderr. Nothing is echoed. There is no argument, environment variable, or file input path for the token.
- It is passed to `gh auth login --hostname github.com --with-token` on stdin through a here-string. `read` and here-strings are shell builtins, so the token never appears in `argv` or in the process list. It is never written to a log, never stored in shell history (the script is not interactive and `HISTFILE` is unset), and `token` is unset immediately afterward.
- Immediately after login the script checks, through the API response headers only: the classic-token scope header contains `repo` and `workflow`; the authenticated login equals `machine_login`. `read:org` is reported as a warning if missing, pending the "verify" note in ADR-001 section 2. The script does not call `gh auth token`.
- Where the system has no keyring, `gh` may store the token in `~/.config/gh/`. The home directory is ephemeral by design (D16). Behavior is verified during implementation (open question 6).
- Dry-run never reaches this step.

### 4.6 Verification (`workspace/verify.sh`)

Read-only. One line per check: `PASS`/`FAIL`/`WARN <id>: <detail>`. Exit 0 if no `FAIL`, else 1. It never prints a token or an environment variable value.

| ID | Check |
|---|---|
| V-1 | Every `builder` tool: smoke command output matches the manifest version (`scripts/toolchain verify`). |
| V-2 | Guardrails: for each repository in `~/work/`, `.claude/settings.json` contains every deny rule in the canonical list (`workspace/claude-user/required-deny.txt`), `disableBypassPermissionsMode` is set, `enableAllProjectMcpServers` is false, and no `.mcp.json` exists. Static check only; the behavioral probe is a documented manual step (open question 3). |
| V-3 | Token: login equals `machine_login`; scopes include `repo` and `workflow`; expiry header is reported with a warning under 14 days. |
| V-4 | No OCI credentials (AC1-3): no `~/.oci/`, no `oci` binary on `PATH`, no variable whose name starts with `OCI_` (names only), no key file referenced by an OCI config. |
| V-5 | Git identity: `user.name` equals `machine_login`; `user.email` ends with the noreply domain. |
| V-6 | Clones: each repository in `repos.txt` exists with `origin` pointing at the expected repository. |

Verification ends with: `verify: <n> passed, <n> failed, <n> warnings`.

### 4.7 Bootstrap and release tag

ADR-001 step 2 clones the latest release tag anonymously. Creating tags is the user's action (CLAUDE.md). The first tag is needed before the first real reset test (open question 7). `restore.sh` run from the tag clone applies the profile from that tag; the working clone in `~/work/` is `main` and may be ahead of it.

## 5. `scripts/quality-gate.sh` (part c)

### 5.1 Interface

```text
scripts/quality-gate.sh [--list] [--only ID[,ID...]] [--skip ID[,ID...]] [--base REF] [--strict] [--verbose]
```

| Option | Effect |
|---|---|
| `--list` | Print check IDs and the tool each needs. |
| `--only`, `--skip` | Select checks. |
| `--base REF` | Limit file-based checks to files changed relative to `REF`. Default: all tracked files. |
| `--strict` | A missing tool or a failing check is an error. CI always passes `--strict`. |
| `--verbose` | Print every finding instead of the first 20 per check. |

Exit codes: 0 all selected checks passed (skips allowed when not strict); 1 at least one check failed; 2 usage error; 3 `--strict` and a required tool is missing. Never writes to the repository. Needs no network and no credentials.

### 5.2 Check contract

Each check is an executable `scripts/checks/<id>.sh` that receives the file list on stdin (newline-separated) and:

- prints one finding per line as `path:line: message` on stdout;
- exits 0 (clean), 1 (findings), 77 (nothing applicable), or 78 (required tool missing).

The dispatcher turns these into `PASS`, `FAIL`, `SKIP (no files)`, or `SKIP (tool missing: <name>)`. Adding a check means adding one file.

### 5.3 Checks

| ID | What it checks | Tool |
|---|---|---|
| `shellcheck` | All shell scripts (`*.sh` and files with a bash shebang) | `shellcheck` |
| `bash-hygiene` | Bash scripts start with `set -euo pipefail` (within the first 15 lines) and are executable | none |
| `yaml` | YAML files lint cleanly | `yamllint` |
| `markdown` | Markdown files lint cleanly | Markdown linter from the manifest |
| `links` | Relative Markdown links resolve to existing files | none |
| `actionlint` | Workflow syntax and expression errors | `actionlint` |
| `workflow-policy` | Every `uses:` is a full 40-character SHA with a version comment (local `./` allowed); no `pull_request_target`; every workflow has a top-level `permissions:`; no `${{ github.event.* }}` or `${{ github.head_ref }}` inside `run:` blocks; no `curl` or `wget` piped to a shell | none |
| `no-claude-in-workflows` | No workflow references Claude, `anthropic`, or a Claude credential (AC3-6) | none |
| `public-repo-hygiene` | No resource identifiers (`ocid1.` prefix), IPv4 addresses (documentation ranges `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24` and `0.0.0.0/0` allowed), email addresses (except `noreply` forms), key fingerprints, private-key headers, or token prefixes (`ghp_`, `github_pat_`) | none |
| `toolchain` | `scripts/toolchain check` | Python 3 |
| `ansible` | `ansible-playbook --syntax-check` for `builder.yml` and `lab.yml` | `ansible-core` |
| `python` | `py_compile` on `scripts/` Python files and `python3 -I -m unittest discover` over `tests/` (includes the `pr-contract` fixtures) | Python 3 |
| `terraform` | `tofu fmt -check` and `tofu validate` when `*.tf` files exist | `tofu` |

### 5.4 Output (concise failures)

```text
FAIL shellcheck (2)
  scripts/foo.sh:14: SC2086 Double quote to prevent globbing
  scripts/foo.sh:20: SC2154 bar is referenced but not assigned
PASS yaml
SKIP terraform (no files)
SKIP markdown (tool missing: pymarkdown)
quality-gate: 1 failed, 8 passed, 2 skipped
```

- At most 20 findings per check, then `... N more (use --verbose)`.
- Under GitHub Actions the same summary is appended to `$GITHUB_STEP_SUMMARY` as a Markdown table, so Claude reads the result through `gh` and not through raw logs (ADR-003 section 7).
- Findings contain paths and the tool's message only. File content is not echoed (the repository is public, but findings can end up in PR comments).

## 6. `scripts/pr-contract` (part d)

### 6.1 Implementation approach

- Python 3, standard library only, one executable file plus a small module directory. Data comes from the GitHub REST API through `urllib`, using the read-only `GITHUB_TOKEN`.
- Inputs are `--repo <owner/name>` and `--pr <number>`. The workflow passes these two trusted values through `env:`. The script fetches the title, body, head ref, base ref, author, and changed files itself, so it always sees the latest PR text (a re-run of a workflow does not refresh the event payload) and PR text never passes through a workflow expression or a shell.
- The workflow runs the script from a checkout of the **base** commit, so a PR cannot change the checker that evaluates it. The PR's own copy of the script is tested by the quality gate (`python` check), not trusted by CI. The first PR that introduces the script has no base copy; the workflow reports "skipped: bootstrap" for that PR only (implementation plan).
- Templates are read from the base checkout (`.github/PULL_REQUEST_TEMPLATE/<type>.md`). Required sections are derived from the template's `## ` headings, so the rule cannot drift from the templates.
- Exit codes: 0 pass; 1 rule violations; 2 usage or input error; 3 API or transient error. Errors fail closed (non-zero). An API failure never counts as a pass.

### 6.2 Rule implementation

| Rule | Implementation |
|---|---|
| PC-1 | Parse the body with a line scanner that tracks code fences and strips HTML comments. For each `## ` heading in the matching template, the PR body must contain that exact heading (outside a fence) followed by non-whitespace content before the next `## ` heading. Text that only restates the template comment does not count. Checkbox state is ignored. |
| PC-2 | The branch prefix maps to a type: `design/CR-<n>-` is design, `impl/CR-<n>-` is implementation, `change/` is change, `infra/` is infra, `toolchain/` is toolchain, `dependabot/` is exempt (PC-7). The body must carry the template's machine-readable marker (`<!-- PR type: <type>`), and the marker type must equal the branch type. Unknown prefixes fail. For design and implementation PRs the `<n>` in the branch must match the issue the PR references. |
| PC-3 | Implementation PRs only. The body must contain `Implements: #<n>` and `Design: #<m>` (integers, 1 to 9 digits). Through the API: `<n>` is an issue and not a PR; `<m>` is a PR, `merged` is true, merged into the same base branch, its head ref matches `design/CR-<n>-*`, and its body's "Change request" section references `#<n>`. Failure messages name the missing or failing item only. |
| PC-4 | Design PRs: every changed path, including `previous_filename` of renames, starts with `docs/`. File list is paginated; at 3000 files (the API cap) the check fails closed. |
| PC-5 | Implementation and change PRs: any change (added, modified, removed, renamed) to `docs/cr/*/design.md`, `docs/cr/*/acceptance-criteria.md`, or any path under `docs/adr/` fails. "Approved" is defined by what is on the base branch: a design PR's merge is the approval (ADR-003 section 2), so an existing file is approved. Adding such a file in an implementation PR also fails, because the design PR is the only way to introduce it. |
| PC-6 | If any changed path is under `.github/workflows/` or `.github/actions/`, the body must contain a non-empty `## Workflow change justification` section. |
| PC-7 | Applies when the author is `dependabot[bot]` and the head ref starts with `dependabot/`. PC-1 to PC-3 are skipped. Every changed path must be a dependency manifest or lockfile from an allowlist in the script, or a workflow file whose patch changes only `uses:` lines (and their trailing version comments). A missing patch (large diff) fails closed. |

### 6.3 Handling PR text as untrusted input

| Threat | Control |
|---|---|
| Shell or expression injection through title, body, or branch name | PR text is never placed in `run:` text, `${{ }}` expressions, `argv`, or a file path. The script receives only `--repo` and `--pr` and fetches the rest. The script runs no subprocess with PR-derived arguments and uses no `eval`, `exec`, or format-to-shell. The `workflow-policy` check rejects `github.event.pull_request.*` and `github.head_ref` inside `run:` blocks. |
| Parser confusion (headings in code fences, headings inside HTML comments, duplicate headings, CRLF) | Line-based state machine (fences, comments), first-heading-wins, normalized line endings, exact-match headings. Fixtures cover each case. |
| Resource exhaustion | Body capped at 65,536 characters (the GitHub limit; larger is a failure), line count and file count capped, regular expressions are anchored and applied with `fullmatch` to length-limited strings, no nested quantifiers. API calls have timeouts and a page cap. |
| Workflow-command injection through logs (`::set-output`, `::add-mask`, `::error`) | Anything derived from PR text that is printed (branch name, paths) is sanitized: control characters removed, line breaks and a leading `::` neutralized, length-limited. Messages are built from fixed templates plus sanitized values. |
| Markdown injection in the job summary | Values are written inside code spans after neutralizing backticks and HTML. |
| Number and path confusion in API calls | References are parsed as integers and the API path is built from the integer, never from matched text. The API host is fixed to the GitHub API over `https`. |
| Token exposure | Token read from the environment into one request header. Never printed, never put in an exception message. |
| Self-modifying checker | Script and templates come from the base checkout (6.1). Residual: a PR can still alter the workflow file itself (RR below). |
| Authority confusion | The check never treats labels, checkboxes, or `status:` lines as approval (ADR-003 section 5). |

Tests (`tests/pr-contract/`, run by the quality gate) use recorded API fixtures and an offline mode (`--fixtures DIR`). Required cases include each rule pass and fail, plus hostile bodies: `$(...)`, backticks, `${{ ... }}`, `::error::` lines, 1 MB text, RTL and zero-width characters, fake headings in fences and comments, duplicate headings, CRLF, and a title with newlines.

Residual risk RR-S1-1: `pull_request` workflows run the workflow file from the PR merge commit, so a PR can edit `pr-contract.yml`. PC-6 forces a justification for such changes, and the approver's review of the latest push remains the authority (ADR-003 section 5). `pr-contract` is a consistency check, not a security boundary.

## 7. CI skeleton (part e)

### 7.1 Workflows

| File | Trigger | Jobs (check names) |
|---|---|---|
| `.github/workflows/pr-contract.yml` | `pull_request`: `opened`, `edited`, `synchronize`, `reopened`, `ready_for_review`, `converted_to_draft` | `pr-contract` |
| `.github/workflows/ci.yml` | `pull_request`: `opened`, `synchronize`, `reopened`, `ready_for_review`; `push` to `main` | `quality-gate`, `toolchain-amd64`, `toolchain-arm64`, `builder-profile` |
| `.github/dependabot.yml` | Dependabot schedule | Version updates for `github-actions` (SHA pins) and the pip lock directory |

No `pull_request_target`, no `workflow_run`, no `schedule` that invokes anything but repository scripts, and no workflow that invokes Claude or holds a Claude credential (ADR-003 section 2, item 7; AC3-6). Draft PRs run CI too, because the checkpoint model expects CI on every push. Required jobs have no `paths:` filters.

### 7.2 Hardening rules for every workflow

- Top-level `permissions: {}`. Each job grants only what it needs, as below.
- Third-party Actions pinned to a full commit SHA with the release tag in a trailing comment. The only Action planned is `actions/checkout`, with `persist-credentials: false`. All other steps run repository scripts. SHAs are verified against the upstream tag at implementation time.
- Runner images pinned by label (`ubuntu-24.04`, `ubuntu-24.04-arm`), never `ubuntu-latest`. The container image `debian:13` is pinned by digest.
- `timeout-minutes` on every job. `concurrency` per PR with `cancel-in-progress: true` for pull requests.
- Untrusted expressions are never interpolated into `run:`; trusted values (repository, PR number) go through `env:`.
- No secrets are used in Stage 1. The only token is the ephemeral `GITHUB_TOKEN` with the permissions below.

### 7.3 Jobs

| Job (check name) | Runner | Permissions | Does |
|---|---|---|---|
| `pr-contract` | `ubuntu-24.04` | `contents: read`, `pull-requests: read`, `issues: read` | Checks out the base commit, runs `scripts/pr-contract --repo "$REPO" --pr "$PR_NUMBER"` |
| `quality-gate` | `ubuntu-24.04` | `contents: read` | Installs the `builder` toolchain into a temporary prefix with `scripts/toolchain install`, runs `scripts/quality-gate.sh --strict` |
| `toolchain-amd64` | `ubuntu-24.04` | `contents: read` | `scripts/toolchain verify --download` for amd64: download every artifact, compare checksums, extract, run smoke commands |
| `toolchain-arm64` | `ubuntu-24.04-arm` | `contents: read` | Same, for arm64. Exercises the ARM64 artifacts the lab VM will use, ahead of Stage 3 |
| `builder-profile` | `ubuntu-24.04`, container `debian:13@sha256:<digest>` | `contents: read` | Applies `ansible/builder.yml` in the container, runs `scripts/toolchain verify`. Evidence for the builder profile without touching the workspace |

`toolchain-amd64` and `toolchain-arm64` are one matrix job with `name: toolchain-${{ matrix.arch }}`, which yields those two check names. `ubuntu-24.04-arm` availability and pricing for this public repository is confirmed during implementation.

### 7.4 Check names to require later

Required status checks are configured by the user in the ruleset (CLAUDE.md: Claude never changes settings). Proposed set and timing:

| Check | When to require |
|---|---|
| `pr-contract` | Immediately after the first implementation PR that introduces it merges (ADR-003 section 6: required on public repositories) |
| `quality-gate` | After one green run on a test PR |
| `toolchain-amd64`, `toolchain-arm64`, `builder-profile` | After one green run on a test PR (Stage 1 exit criterion) |

## 8. Risks

| ID | Risk | Mitigation |
|---|---|---|
| RR-S1-1 | PR can edit the `pr-contract` workflow (6.3) | PC-6 justification; approver review is the authority |
| RR-S1-2 | Upstream artifact is replaced after the checksum is recorded | Checksums are pinned in reviewed PRs; mismatch fails closed; signatures where available |
| RR-S1-3 | Debian archive packages are not exactly pinned | Signed archive; versions reported by `verify`; open question 1 |
| RR-S1-4 | Workspace guardrails are lower assurance than managed settings (RR-8) | Unchanged from ADR-001; repository rulesets; no OCI credentials on the workspace |
| RR-S1-5 | `gh` may store T1 in plaintext in the ephemeral home | Accepted in D16; verified during implementation |
| RR-S1-6 | The 15-minute target depends on download speed and apt mirrors | Time is reported per step; the target is measured in the AC1-7 test |

## 9. Open questions for the user

1. **APT pinning.** CLAUDE.md says to pin every version. Exact apt pins break whenever Debian publishes a security update. Proposal: `apt` tools use a minimum version, rely on the signed archive, and `verify` prints the installed version; every non-apt tool is exactly pinned. Approve this exception, or require exact apt pins (with the maintenance cost)?
2. **Manifest format.** TOML (stdlib parser on both OSes) or YAML (matches `config/project.yaml`, needs PyYAML or `yq` before the first install)?
3. **Guardrail test (AC1-5).** The ADR asks for a scripted test that denied commands are refused. This design verifies rule presence statically and keeps the behavioral probe manual (this session's step 1 is the model). Is that enough, or should `verify.sh` also start a headless Claude Code run (needs authentication and model usage)?
4. **Container runtime.** Include rootless Podman in `builder` now (O-10 proposal), or defer until a project needs it?
5. **Workspace managed settings.** Enable `claude_managed_settings` on the workspace if root is available and no corporate managed settings exist, or stay with user-level and repository settings only (RR-8)?
6. **Token storage.** If the workspace has no keyring, is `gh` writing T1 in plaintext into the ephemeral home acceptable (D16 suggests yes), or should the script abort in that case?
7. **Release tag.** `restore.sh` is bootstrapped from the latest release tag, and only you create tags. When should the first tag be cut (proposal: after the restore implementation PR merges, before the AC1-7 reset test)?
8. **Linters.** Which Markdown linter: `markdownlint-cli2` (needs Node and an npm lockfile) or a Python one such as `pymarkdownlnt` (hash-locked pip, one fewer ecosystem; proposed)? `terraform` or `tofu` for `fmt` and `validate` (OpenTofu proposed)?
9. **Dependabot.** May the implementation add `.github/dependabot.yml` for Actions SHA pins and the pip lock? It configures version updates only and changes no repository setting.
10. **`gh pr create --template`.** In this session the command fails without a terminal ("must provide `--title` and `--body`"), which affects ADR-003 verification item V3-1 and CLAUDE.md. Proposal: Claude Code seeds the body from the template file (marker line kept) and uses `--body-file`; a follow-up PR updates CLAUDE.md wording. Acceptable?
11. **Class 1 fixes to accepted ADRs.** PC-5 as designed blocks any change under `docs/adr/` in implementation and change PRs. Should a Class 1 typo fix to an accepted ADR through a `change/` PR be allowed, or must it always use a design PR?
12. **Labels.** The label `class:3` (ADR-003 section 3) does not exist in the repository, so issue #2 has no label. Do you want to create it (labels are repository configuration), or should I propose the exact `gh label create` command for you to run?
13. **Open PR branches on restore.** ADR-001 says the restore "checks out" open draft-PR branches. This design creates local tracking branches for all open PRs of the machine account and leaves the working tree on `main` (one working tree cannot hold several checkouts). Is that the intended behavior?
