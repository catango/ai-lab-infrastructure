#!/usr/bin/env bash
# The lab half of the PA-28 job (CR-57 PA-A8, PA-A11, PA-A13, PA-A16, PA-A18, PA-A25, PA-A26, PA-A29, PA-A31, PA-A32; design C-4, C-5):
# lab setup in a disposable Debian 13 container with two accounts and one key each. The CI job `host-profiles` calls one subcommand
# per step: prepare SOURCE (accounts, keys, three clones of SOURCE with a local bare origin at its HEAD: one with an unpushed local v*
# test tag, one without a tag, one whose tag origin/main does not contain), refusals, unconfirmed (the sshd step without the second
# login), first-run, second-run, dry-run, verify (what the AI user cannot change, sshd settings in force), merge (foreign managed files
# merged, never replaced), token-step (the tests/lab token step fixtures against the installed step, as the AI user), lab-check (the
# installed lab check as the AI user: the gap lab setup still leaves, a complete lab, failures a container can show, the pre-disposal
# mode; the tree hash is unchanged). A real sshd restart, `sshd -T` of a running daemon, and the unattended-upgrade units are PA-A33.
# The operator half of the PA-28 job is pa28-operator.sh in a second container: the two profiles own the same sshd drop-in.
# The script changes /etc, so it runs only as root on a disposable host.
set -euo pipefail

if [[ ${AI_LAB_ALLOW_SYSTEM_CHANGES:-} != 1 || $(id -u) -ne 0 ]]; then
  echo "refusing to run: set AI_LAB_ALLOW_SYSTEM_CHANGES=1 and run as root on a disposable host" >&2
  exit 2
fi

readonly WORK=/var/tmp/pa28
readonly AI=ci-ai ADMIN=ci-admin OTHER=ci-other
readonly KEYS=/etc/ssh/authorized_keys
readonly DROPIN=/etc/ssh/sshd_config.d/00-ai-lab.conf
readonly LAB=$WORK/lab UNTAGGED=$WORK/untagged AHEAD=$WORK/ahead
readonly TEST_ID=4242 # a test value of github.machine_user_id (LC-8), used only when the head of the pull request leaves it empty
# shellcheck disable=SC2034 # read by tree_list in pa28-common.sh
TREE_ROOTS=(/etc /opt/ai-lab /usr/local /home)

# shellcheck source=pa28-common.sh source-path=SCRIPTDIR
. "$(dirname "${BASH_SOURCE[0]}")/pa28-common.sh"

# The same for the two managed accounts' home directories only: lab setup writes nothing into a user's home (PA-16).
home_hash() {
  {
    find "/home/$AI" "/home/$ADMIN" -printf '%p %y %m %U %G %s %l\n'
    find "/home/$AI" "/home/$ADMIN" -type f -print0 | xargs -0 -r sha256sum
  } | LC_ALL=C sort | sha256sum | cut -d' ' -f1
}

playbook() { # playbook CLONE ARGUMENT...
  local clone=$1
  shift
  (cd "$clone" && ANSIBLE_CONFIG="$clone/ansible/ansible.cfg" ANSIBLE_NOCOLOR=1 \
    ansible-playbook -i ansible/inventory/localhost.yml ansible/lab.yml -e "lab_ai_user=$AI" -e "lab_admin_user=$ADMIN" "$@")
}

prepare() {
  local source=${1:?usage: prepare SOURCE}
  mkdir -p "$WORK" /run/sshd
  ssh-keygen -A >/dev/null
  git config --global --add safe.directory "$source"
  local user name
  for user in "$AI" "$ADMIN" "$OTHER"; do
    useradd --create-home --shell /bin/bash "$user"
  done
  for name in ai admin other; do
    ssh-keygen -q -t ed25519 -N '' -C "pa28-$name" -f "$WORK/key-$name"
  done
  provision "$AI" ai
  provision "$ADMIN" admin
  provider_dropin
  git init -q --bare --initial-branch=main "$WORK/origin.git"
  git -C "$source" push -q "$WORK/origin.git" HEAD:refs/heads/main
  # github.machine_user_id (LC-8) may be empty at the head of the pull request: the approver sets it, and lab setup refuses while it is
  # empty (the refusals step shows that). The fixtures then set a test value in one commit on top of the head, before the clones are
  # taken; the clones differ from the head by that one line of config/project.yaml and nothing else.
  if ! grep -Eq '^  machine_user_id: *[1-9][0-9]*' "$source/config/project.yaml"; then
    git clone -q "$WORK/origin.git" "$WORK/seed"
    sed -i -E "s/^  machine_user_id:.*/  machine_user_id: $TEST_ID/" "$WORK/seed/config/project.yaml"
    git -C "$WORK/seed" -c user.name=ci -c user.email=noreply commit -q -am "fixture: a test value of machine_user_id"
    git -C "$WORK/seed" push -q origin HEAD:refs/heads/main
  fi
  git clone -q "$WORK/origin.git" "$LAB"
  git -C "$LAB" tag v0.0.0-ci
  git clone -q "$WORK/origin.git" "$UNTAGGED"
  git clone -q "$WORK/origin.git" "$AHEAD"
  git -C "$AHEAD" -c user.name=ci -c user.email=noreply commit -q --allow-empty -m ahead
  git -C "$AHEAD" tag v0.0.1-ci
  git -C "$LAB" tag --points-at HEAD | grep -qx v0.0.0-ci
  [[ -z $(git -C "$LAB" diff --name-only "$(git -C "$source" rev-parse HEAD)" HEAD -- . ':!config/project.yaml') ]] ||
    fail "the lab clone is not the head of the pull request (only config/project.yaml may differ, by the test id)"
  ! git -C "$WORK/origin.git" tag --list | grep -q . || fail "the test tag must stay unpushed"
  ok "prepared: three clones, a local bare origin at the head, an unpushed test tag"
}

# fixture NAME MESSAGE SETUP RESTORE: put the machine in a bad state, expect the refusal, put it back.
fixture() {
  local name=$1 message=$2 setup=$3 restore=$4
  "$setup"
  refused "$name" "$LAB" "$message" -e lab_apply=true -e ssh_second_login_confirmed=true
  "$restore"
}

refusals() {
  refused "a real run without the apply variable is refused" "$LAB" "lab_apply=true"
  refused "an untagged tree is refused" "$UNTAGGED" "this clone is not a release" -e lab_apply=true -e ssh_second_login_confirmed=true
  refused "a tag that origin/main does not contain is refused" "$AHEAD" "this clone is not a release" -e lab_apply=true
  refused "a dry run of an untagged tree is refused too" "$UNTAGGED" "this clone is not a release" --check
  printf 'github:\n  machine_login: ci-bot\n  machine_user_id:\n' >"$WORK/empty-id.yaml"
  printf 'github:\n  machine_login: ci-bot\n  machine_user_id: guess\n' >"$WORK/text-id.yaml"
  refused "an empty github.machine_user_id is refused (LC-8)" "$LAB" "numeric GitHub id" -e lab_apply=true -e "git_identity_project_config=$WORK/empty-id.yaml"
  refused "a github.machine_user_id that is not a number is refused (LC-8)" "$LAB" "numeric GitHub id" -e lab_apply=true -e "git_identity_project_config=$WORK/text-id.yaml"
  key_rule_fixtures
}

unconfirmed() {
  playbook "$LAB" -e lab_apply=true --tags ssh_hardening | tee "$WORK/unconfirmed.txt"
  grep -q 'sshd was NOT switched' "$WORK/unconfirmed.txt" || fail "the refusal to switch sshd is not reported"
  [[ ! -e $DROPIN ]] || fail "sshd was switched without the second login"
  [[ $(stat -c '%U:%G %a' "$KEYS/$AI") == 'root:root 644' ]] || fail "the AI user's key is not a root-owned file"
  [[ $(stat -c '%U:%G %a' "$KEYS/$ADMIN") == 'root:root 644' ]] || fail "the admin's key is not a root-owned file"
  grep -q '^restrict,pty ssh-ed25519 ' "$KEYS/$AI" || fail "the AI user's key lacks restrict,pty (LC-11)"
  grep -q '^ssh-ed25519 ' "$KEYS/$ADMIN" || fail "the admin's key must carry no forced options"
  ! /usr/sbin/sshd -T | grep -qx "authorizedkeysfile $KEYS/%u" || fail "sshd already reads the root-owned location"
  ok "sshd is not switched without the confirmed second login; the keys are in the root-owned location"
}

first_run() {
  # Symbolic links the AI user could plant (PA-A11): lab setup follows none of them and writes into no home directory.
  ln -s /etc/claude-code "/home/$AI/.claude"
  ln -s "$KEYS" "/home/$AI/keys"
  ln -s /opt/ai-lab "/home/$ADMIN/tools"
  local before after
  before=$(home_hash)
  playbook "$LAB" -e lab_apply=true -e ssh_second_login_confirmed=true | tee "$WORK/first-apply.txt"
  after=$(home_hash)
  [[ $before == "$after" ]] || fail "lab setup wrote into a user's home directory"
  [[ $(readlink "/home/$AI/.claude") == /etc/claude-code ]] || fail "a planted link was changed"
  ok "first run: home directories unchanged, planted links not followed"
}

second_run() {
  playbook "$LAB" -e lab_apply=true -e ssh_second_login_confirmed=true | tee "$WORK/second-apply.txt"
  grep -Eq 'changed=0 +unreachable=0 +failed=0' "$WORK/second-apply.txt" || fail "the second run changed something"
  ok "second run: zero changes"
}

dry_run() {
  local before after
  before=$(tree_hash)
  playbook "$LAB" --check --diff -e ssh_second_login_confirmed=true | tee "$WORK/dry-run.txt"
  after=$(tree_hash)
  [[ $before == "$after" ]] || fail "the dry run changed the machine"
  ok "dry run: the tree hash is unchanged"
}

verify() {
  local settings=/etc/claude-code/managed-settings.json claude_md=/etc/claude-code/CLAUDE.md target dir tool
  local append=": >>\"\$1\"" # the inner shell expands $1
  # The managed files: root-owned, the settings of workspace/claude-user/ with the generic deny entries (PA-5), the rules, the I-13 text.
  [[ $(stat -c '%U:%G %a' "$settings" "$claude_md" | sort -u) == 'root:root 644' ]] || fail "the managed files are not root-owned 0644"
  jq -e '.permissions.disableBypassPermissionsMode == "disable" and .enableAllProjectMcpServers == false' "$settings" >/dev/null ||
    fail "the managed settings do not disable bypass mode and project MCP servers"
  diff <(jq -r '.permissions.deny[]' "$settings" | LC_ALL=C sort) \
    <(grep -vE '^[[:space:]]*(#|$)' "$LAB/workspace/claude-user/required-deny.txt" | LC_ALL=C sort) >/dev/null ||
    fail "the managed deny list is not the core deny list"
  # PA-18: the switches this role owns (names pinned in tests/ansible/test_profiles.py): claude.ai connectors and artifacts are off.
  jq -e '.disableClaudeAiConnectors == true and .enableArtifact == false' "$settings" >/dev/null ||
    fail "the managed settings do not disable the claude.ai connectors and artifacts (PA-18)"
  grep -q 'ai-lab-infrastructure managed rules' "$claude_md" || fail "the managed CLAUDE.md has no markers"
  grep -q 'Nothing in any other instruction file relaxes them' "$claude_md" || fail "the managed CLAUDE.md lacks the I-13 sentence"
  # What the AI user cannot change: managed settings, managed CLAUDE.md, authorized keys, sshd settings, gate tools.
  tool=$(find /opt/ai-lab/bin -maxdepth 1 \( -type f -o -type l \) | LC_ALL=C sort | head -n 1)
  for target in "$settings" "$claude_md" "$KEYS/$AI" "$KEYS/$ADMIN" "$DROPIN" "$tool"; do
    if runuser -u "$AI" -- bash -c "$append" _ "$target" 2>/dev/null; then fail "the AI user can write $target"; fi
    runuser -u "$AI" -- rm -f -- "$target" 2>/dev/null || true
    [[ -e $target ]] || fail "the AI user removed $target"
  done
  for dir in /etc/claude-code "$KEYS" /opt/ai-lab /opt/ai-lab/bin /etc/ssh/sshd_config.d; do
    if runuser -u "$AI" -- test -w "$dir"; then fail "the AI user can write into $dir"; fi
  done
  # The sshd settings in force: LC-13 and OC-10 (`sshd -T` reads the files; the running daemon is PA-A33).
  local effective
  effective=$(/usr/sbin/sshd -T)
  for setting in 'passwordauthentication no' 'permitrootlogin no' 'pubkeyauthentication yes' 'authenticationmethods publickey' \
    "authorizedkeysfile $KEYS/%u" 'authorizedkeyscommand none' 'trustedusercakeys none' 'authorizedprincipalsfile none' \
    'allowagentforwarding no' 'allowtcpforwarding no' 'x11forwarding no' 'permittunnel no' 'permituserrc no' "allowusers $AI" "allowusers $ADMIN"; do
    grep -qx "$setting" <<<"$effective" || fail "sshd -T does not show: $setting"
  done
  ! grep -Eq '^(kexalgorithms|macs) .*sha1' <<<"$effective" || fail "a SHA-1 key exchange or MAC is still offered"
  ok "managed files, write attempts as the AI user, and the sshd settings in force"
  verify_identity_and_updates
}

# LC-8 and LC-15 are applied by lab setup: the system-wide git identity (root-owned, nothing in a user's home) and the apt periodic
# settings of the unattended security updates. The units are PA-A33 (the container has no systemd).
verify_identity_and_updates() {
  local login email
  login=$(sed -n 's/^machine_login=//p' "$TOOLS/lab.conf")
  [[ $(stat -c '%U:%G %a' /etc/gitconfig) == 'root:root 644' ]] || fail "/etc/gitconfig is not root-owned 0644"
  [[ $(git config --system --get user.name) == "$login" ]] || fail "the system-wide git user.name is not the machine account"
  email=$(git config --system --get user.email)
  [[ $email =~ ^[1-9][0-9]*\+$login@users\.noreply\.github\.com$ ]] || fail "the system-wide git user.email is not the machine account's noreply address"
  [[ ! -e /home/$AI/.gitconfig && ! -e /home/$ADMIN/.gitconfig ]] || fail "lab setup wrote a git configuration into a user's home"
  if runuser -u "$AI" -- bash -c ': >>/etc/gitconfig' 2>/dev/null; then fail "the AI user can write /etc/gitconfig"; fi
  dpkg-query -W -f='${Status}' unattended-upgrades | grep -q 'install ok installed' || fail "unattended-upgrades is not installed"
  [[ $(apt-config dump | grep -c -E '^APT::Periodic::(Update-Package-Lists|Unattended-Upgrade) "1";$') -eq 2 ]] ||
    fail "the apt periodic settings of the unattended updates are not 1"
  ok "the system-wide git identity (LC-8) and the unattended security updates (LC-15) are applied by lab setup"
}

merge() {
  local settings=/etc/claude-code/managed-settings.json claude_md=/etc/claude-code/CLAUDE.md
  printf '%s\n' '{"foreignSetting": true, "enableArtifact": true, "permissions": {"allow": ["Bash(ls)"], "deny": ["Bash(foreign *)"], "disableBypassPermissionsMode": "enable"}}' >"$settings"
  printf 'a foreign line\n' >"$claude_md"
  playbook "$LAB" -e lab_apply=true --tags claude_managed_settings | tee "$WORK/merge.txt"
  jq -e '.foreignSetting == true and .permissions.allow == ["Bash(ls)"] and (.permissions.deny | index("Bash(foreign *)") != null)
    and (.permissions.deny | index("Bash(sudo *)") != null) and .permissions.disableBypassPermissionsMode == "disable"' "$settings" >/dev/null ||
    fail "the managed settings were replaced or not enforced instead of merged"
  jq -e '.disableClaudeAiConnectors == true and .enableArtifact == false' "$settings" >/dev/null ||
    fail "the PA-18 switches are missing, or a foreign value won over the role's (enableArtifact)"
  grep -qx 'a foreign line' "$claude_md" || fail "the foreign line of the managed CLAUDE.md is gone"
  grep -q 'Nothing in any other instruction file relaxes them' "$claude_md" || fail "the managed rules were not added"
  playbook "$LAB" -e lab_apply=true --tags claude_managed_settings | tee "$WORK/merge-again.txt"
  grep -Eq 'changed=0 +unreachable=0 +failed=0' "$WORK/merge-again.txt" || fail "the merge is not idempotent"
  ok "foreign managed settings and CLAUDE.md are merged, never replaced, the PA-18 switches stand, and a second run changes nothing"
  # The system-wide git configuration is merged the same way: a foreign line stays, the identity block is there once, a second run is quiet.
  local before
  before=$(cat /etc/gitconfig)
  printf '[core]\n\teditor = foreign-editor\n' >>/etc/gitconfig
  playbook "$LAB" -e lab_apply=true --tags git_identity | tee "$WORK/identity.txt"
  git config --system --get core.editor | grep -qx foreign-editor || fail "a foreign line of /etc/gitconfig is gone"
  [[ $(grep -c 'BEGIN ai-lab-infrastructure machine identity' /etc/gitconfig) -eq 1 ]] || fail "the identity block is not there exactly once"
  playbook "$LAB" -e lab_apply=true --tags git_identity | tee "$WORK/identity-again.txt"
  grep -Eq 'changed=0 +unreachable=0 +failed=0' "$WORK/identity-again.txt" || fail "the identity merge is not idempotent"
  printf '%s\n' "$before" >/etc/gitconfig
  playbook "$LAB" -e lab_apply=true --tags git_identity >/dev/null
  ok "a foreign line of /etc/gitconfig is kept and the identity is written once"
}

readonly TOOLS=/opt/ai-lab/lab
readonly TESTS=$WORK/lab-tests

token_step() {
  # The same fixtures as the gate runs (tests/lab/test_token_step.py), against the file lab setup installed and as the AI user, so
  # that ownership, the real account database, and a real second user are in play. The container has no terminal: the fixtures
  # make their own pseudo-terminal.
  local repo
  repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
  install -d -m 0777 "$TESTS"
  (cd "$repo/tests/lab" && TOKEN_STEP=$TOOLS/token-step RUN_AS=$AI LAB_TEST_TMP=$TESTS python3 -I -B -m unittest discover -v -s . -p 'test_token_step.py') ||
    fail "the token step fixtures failed"
  ok "token step: refusals before any input, clean environment, no startup file, here-string only (installed file, as the AI user)"
}

# lab_run ARGUMENT...: the installed lab check as the AI user; its output goes to $WORK/lab-check.txt, its status to $LAB_RC.
lab_run() {
  LAB_RC=0
  runuser -u "$AI" -- "$TOOLS/lab-check" "$@" >"$WORK/lab-check.txt" 2>&1 || LAB_RC=$?
}
lab_run_env() { # lab_run_env NAME=VALUE ARGUMENT...
  local assignment=$1
  shift
  LAB_RC=0
  runuser -u "$AI" -- env "$assignment" "$TOOLS/lab-check" "$@" >"$WORK/lab-check.txt" 2>&1 || LAB_RC=$?
}
failing_items() { sed -n -E 's/^FAIL ([A-Z0-9-]+):.*/\1/p' "$WORK/lab-check.txt" | sort | tr '\n' ' '; }
expect_failing() { # expect_failing NAME ITEMS: exactly these items fail (space separated, sorted)
  local got
  got=$(failing_items)
  if [[ $got != "$2 " && -n $2 ]] || [[ -z $2 && -n $got ]]; then
    cat "$WORK/lab-check.txt"
    fail "$1: the lab check fails '${got% }', expected '$2'"
  fi
  if [[ -z $2 && $LAB_RC -ne 0 ]] || [[ -n $2 && $LAB_RC -ne 1 ]]; then fail "$1: exit status $LAB_RC"; fi
  ok "$1"
}

# The one thing lab setup leaves to the user is T1 (LC-7): a stand-in gh answers as a lab on which the token step has run, so the rest
# of the check is shown on a complete lab. Lab setup applies the git identity (LC-8) and the unattended updates (LC-15) itself.
complete_lab() {
  LAB_GH=$WORK/stub-gh
  cat >"$LAB_GH" <<'STUB'
#!/bin/sh
case "$1 $2" in
  "auth status") exit 0 ;;
  "api -i")
    printf 'HTTP/2.0 200 OK\r\nX-Oauth-Scopes: repo, workflow\r\n\r\n{"login":"%s","id":42}\n' "$(sed -n 's/^machine_login=//p' /opt/ai-lab/lab/lab.conf)"
    ;;
  *) exit 1 ;;
esac
STUB
  chmod 0755 "$LAB_GH"
}

# as_ai COMMAND...: a command as the AI user; the command strings below are for that user's shell, so $HOME and ~ are its own.
as_ai() { runuser -u "$AI" -- "$@"; }

lab_check() {
  local before after homes_before homes_after
  [[ $(stat -c '%U:%G %a' "$TOOLS/lab-check" "$TOOLS/token-step" | sort -u) == 'root:root 755' ]] || fail "the installed tools are not root-owned 0755"
  [[ $(readlink /usr/local/bin/lab-check) == "$TOOLS/lab-check" && $(readlink /usr/local/bin/token-step) == "$TOOLS/token-step" ]] ||
    fail "the commands are not links to the root-owned files"
  grep -qx "ai_user=$AI" "$TOOLS/lab.conf" || fail "lab.conf does not name the AI user"

  # 1. Read-only: the tree and the homes are the same after a run.
  before=$(tree_hash)
  homes_before=$(home_hash)
  tree_list >"$WORK/tree-before.txt"
  # 2. On the lab that lab setup leaves only LC-7 fails: T1 is entered by the user in the token step. LC-8 and LC-15 pass because lab
  #    setup applies the git identity and the unattended updates (the units are PA-A33).
  lab_run
  cat "$WORK/lab-check.txt"
  expect_failing "a lab as lab setup leaves it: only LC-7 (no token entered yet) fails" "LC-7"
  grep -q '^PASS LC-8:' "$WORK/lab-check.txt" || fail "LC-8 does not pass on the lab that lab setup leaves"
  grep -q '^PASS LC-15:' "$WORK/lab-check.txt" || fail "LC-15 does not pass on the lab that lab setup leaves"
  grep -q '^WARN LC-13: .*inert authorized_keys' "$WORK/lab-check.txt" || fail "the inert authorized_keys file in the AI user's home is not a warning"
  grep -q '^PASS LC-13:' "$WORK/lab-check.txt" || fail "LC-13 does not pass beside a provider drop-in that the AI user cannot read"
  grep -q '^WARN LC-13: sshd_config.d/60-provider.conf cannot be read by this account' "$WORK/lab-check.txt" ||
    fail "the drop-in that the AI user cannot read is not a warning"

  # 3. A complete lab passes (a stand-in gh stands in for the token step).
  complete_lab
  lab_run --gh "$LAB_GH"
  cat "$WORK/lab-check.txt"
  expect_failing "a complete lab passes every item" ""
  # 4. A sudo that asks for a password (as for an account with no rule) is a warning, not a failure (LC-2).
  sudo_stub on
  lab_run --gh "$LAB_GH"
  sudo_stub off
  grep -q '^WARN LC-2: sudo asks this account for a password' "$WORK/lab-check.txt" || fail "a sudo password prompt is not a warning for LC-2"
  expect_failing "a password prompt of sudo does not fail the lab check" ""
  lab_run --pre-disposal
  [[ $LAB_RC -eq 0 ]] || fail "the pre-disposal mode lists unsaved work on a lab with no repository"

  # 4. One fixture per failure that a container can show.
  lab_run_env SSH_AUTH_SOCK=/tmp/agent.fixture --gh "$LAB_GH"
  expect_failing "an agent socket fails LC-6" "LC-6"
  install -m 0600 -o "$AI" -g "$AI" "$WORK/key-ai" "/home/$AI/.ssh/id_ed25519"
  lab_run --gh "$LAB_GH"
  rm -f "/home/$AI/.ssh/id_ed25519"
  expect_failing "a private key in the AI user's ~/.ssh fails LC-6" "LC-6"
  # shellcheck disable=SC2016 # the at sign is passed as an argument so that no line looks like an email address to the hygiene check
  as_ai bash -c 'mkdir -p ~/work/ssh-remote && git -C ~/work/ssh-remote init -q && git -C ~/work/ssh-remote remote add origin "git$1host.invalid:o/n.git"' _ @
  lab_run --gh "$LAB_GH"
  rm -rf "/home/$AI/work/ssh-remote"
  expect_failing "an SSH remote in a clone fails LC-6" "LC-6"
  install -d -m 0700 -o "$AI" -g "$AI" "/home/$AI/.aws"
  lab_run --gh "$LAB_GH"
  rmdir "/home/$AI/.aws"
  expect_failing "a credential directory by name fails LC-10" "LC-10"
  cp "/etc/ssh/authorized_keys/$AI" "$WORK/ai-key-file"
  install -m 0644 "$KEYS/$ADMIN" "$KEYS/$AI"
  lab_run --gh "$LAB_GH"
  install -m 0644 "$WORK/ai-key-file" "$KEYS/$AI"
  expect_failing "one key on two accounts fails LC-11 and LC-12" "LC-11 LC-12"
  printf 'ClientAliveInterval 5\n' >/etc/ssh/sshd_config.d/50-stray.conf
  lab_run --gh "$LAB_GH"
  rm -f /etc/ssh/sshd_config.d/50-stray.conf
  expect_failing "a stray sshd option fails LC-13" "LC-13"
  grep -q 'outside LC-13\|changed after lab setup' "$WORK/lab-check.txt" || fail "the LC-13 failure does not name the cause"
  # shellcheck disable=SC2016
  as_ai bash -c 'mkdir -p ~/work/project/docs && git -C ~/work/project init -q && printf "## Credential paths\n\n- \`~/.config/svc/one\` - a test credential\n- \`~/.config/svc/two\` - another\n" >~/work/project/docs/PROJECT.md && mkdir -p ~/.config/svc && : >~/.config/svc/one && chmod 0644 ~/.config/svc/one'
  lab_run --gh "$LAB_GH"
  expect_failing "a credential file with mode 0644 and a path no deny rule covers fail PA-43" "PA-43"
  mentions "$WORK/lab-check.txt" 'one is not mode 0600' 'two is not covered' || fail "PA-43 does not name both causes"

  # 5. The pre-disposal mode: one dirty and one unpushed repository are listed, a saved one is not, and nothing changes.
  as_ai bash -c 'rm -rf ~/work/project ~/.config/svc'
  # shellcheck disable=SC2016
  as_ai bash -c 'for name in dirty unpushed saved; do mkdir -p ~/work/$name && git -C ~/work/$name init -q -b main && git -C ~/work/$name -c user.name=ci -c user.email=noreply commit -q --allow-empty -m first; done
    git -C ~/work/saved update-ref refs/remotes/origin/main HEAD
    git -C ~/work/unpushed update-ref refs/remotes/origin/main HEAD
    git -C ~/work/unpushed -c user.name=ci -c user.email=noreply commit -q --allow-empty -m second
    : >~/work/dirty/notes.txt'
  local state
  # shellcheck disable=SC2016
  state=$(as_ai bash -c 'cd ~/work && find . -type f -print0 | sort -z | xargs -0 sha256sum; find . | sort | xargs stat -c "%n %a %Y"' | sha256sum)
  lab_run --pre-disposal
  [[ $LAB_RC -eq 1 ]] || fail "the pre-disposal mode did not report unsaved work"
  cat "$WORK/lab-check.txt"
  mentions "$WORK/lab-check.txt" 'UNSAVED dirty: ' 'UNSAVED unpushed: ' || fail "the pre-disposal mode does not list both repositories"
  ! grep -q '^UNSAVED saved' "$WORK/lab-check.txt" || fail "the pre-disposal mode lists a saved repository"
  # shellcheck disable=SC2016
  [[ $state == "$(as_ai bash -c 'cd ~/work && find . -type f -print0 | sort -z | xargs -0 sha256sum; find . | sort | xargs stat -c "%n %a %Y"' | sha256sum)" ]] ||
    fail "the pre-disposal mode changed a repository"
  as_ai bash -c 'rm -rf ~/work'
  rmdir "/home/$AI/.config" 2>/dev/null || true
  rm -f "$WORK/ai-key-file"
  after=$(tree_hash)
  homes_after=$(home_hash)
  if [[ $before != "$after" ]]; then
    tree_list | diff "$WORK/tree-before.txt" - || true
    fail "the lab check or its fixtures left the machine changed"
  fi
  [[ $homes_before == "$homes_after" ]] || fail "the home directories changed"
  ok "lab check: only LC-7 fails before the token step, a complete lab, six failures a container can show, the pre-disposal mode; the tree hash is unchanged"
}

case ${1:-} in
  prepare) prepare "${2:-}" ;;
  refusals) refusals ;;
  unconfirmed) unconfirmed ;;
  first-run) first_run ;;
  second-run) second_run ;;
  dry-run) dry_run ;;
  verify) verify ;;
  merge) merge ;;
  token-step) token_step ;;
  lab-check) lab_check ;;
  *)
    echo "usage: pa28-lab.sh prepare SOURCE | refusals | unconfirmed | first-run | second-run | dry-run | verify | merge | token-step | lab-check" >&2
    exit 2
    ;;
esac
