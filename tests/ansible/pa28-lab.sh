#!/usr/bin/env bash
# The lab half of the PA-28 job (CR-57 PA-A8, PA-A11, PA-A13, PA-A16, PA-A18, PA-A25, PA-A26, PA-A29, PA-A31, PA-A32; design C-4, C-5):
# lab setup in a disposable Debian 13 container with two accounts and one key each. The CI job `host-profiles` calls one subcommand
# per step: prepare SOURCE (accounts, keys, three clones of SOURCE with a local bare origin at its HEAD: one with an unpushed local v*
# test tag, one without a tag, one whose tag origin/main does not contain), refusals, unconfirmed (the sshd step without the second
# login), first-run, second-run, dry-run, verify (what the AI user cannot change, sshd settings in force), merge (foreign managed files
# merged, never replaced), token-step (the tests/lab token step fixtures against the installed step, as the AI user), lab-check (the
# installed lab check as the AI user: the gap lab setup still leaves, a complete lab, failures a container can show, the pre-disposal
# mode; the tree hash is unchanged), deny-probe (plan PR 4a, PA-56: does the filesystem of /home take the immutable attribute here?),
# deny-layer (the user-level deny layer: with the attribute the write attempts of the AI user all fail and each root change makes LC-16
# fail; without it the fail-closed fixture runs and the job says `immutability not testable here`), project (plan PR 8, see below). A
# real sshd restart, `sshd -T` of a running daemon, and the unattended-upgrade units are PA-A33.
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
readonly LOADED=/etc/ssh/ai-lab-sshd-loaded.txt
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

# The same for the home of the AI user outside the two paths of the user-level layer (PA-A11, PA-A29: the layer is the one change a
# home-directory hash may show).
home_hash_outside_layer() {
  {
    find "/home/$AI" "/home/$ADMIN" -not -path "/home/$AI/.claude" -not -path "/home/$AI/.claude/*" -printf '%p %y %m %U %G %s %l\n'
    find "/home/$AI" "/home/$ADMIN" -not -path "/home/$AI/.claude/*" -type f -print0 | xargs -0 -r sha256sum
  } | LC_ALL=C sort | sha256sum | cut -d' ' -f1
}

# The layer mode of every run: `both` (the default of lab setup) when the probe step found the attribute usable here, `managed` when it
# did not (the fail-closed fixture then shows what `both` does). A fixture that needs a mode passes -e lab_deny_layer=... itself: the
# later -e wins.
deny_mode() {
  if [[ -s $WORK/deny-layer ]]; then cat "$WORK/deny-layer"; else echo both; fi
}

playbook() { # playbook CLONE ARGUMENT...
  local clone=$1
  shift
  (cd "$clone" && ANSIBLE_CONFIG="$clone/ansible/ansible.cfg" ANSIBLE_NOCOLOR=1 \
    ansible-playbook -i ansible/inventory/localhost.yml ansible/lab.yml -e "lab_ai_user=$AI" -e "lab_admin_user=$ADMIN" \
    -e "lab_deny_layer=$(deny_mode)" "$@")
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

# deny_probe: the probe step of the PA-28 job (PA-56, PA-A37). It tries `chattr +i` on a scratch file on the filesystem of /home and records
# the answer for every later step. It never fails the job and never skips silently: without the attribute it says so and the job summary
# repeats it.
deny_probe() {
  command -v chattr >/dev/null || fail "chattr is not installed (package e2fsprogs): the probe cannot run"
  local scratch=/home/.pa28-attribute-probe error
  : >"$scratch"
  if error=$(chattr +i "$scratch" 2>&1); then
    chattr -i "$scratch"
    rm -f "$scratch"
    echo both >"$WORK/deny-layer"
    printf 'immutable attribute: usable here (chattr +i works on the filesystem of /home), so the layer is tested for real\n' >"$WORK/attribute.txt"
  else
    rm -f "$scratch"
    echo managed >"$WORK/deny-layer"
    printf 'immutability not testable here: %s\nThe real attribute is proved only by the approver check PA-A38; the fail-closed fixture of PA-51 runs instead.\n' \
      "${error#chattr: }" >"$WORK/attribute.txt"
  fi
  cat "$WORK/attribute.txt"
  ok "attribute probe done (layer mode for the other steps: $(deny_mode))"
}

# refused_layer NAME MESSAGE: the layer role alone, mode both, with the probe skipped (its tag, used by these fixtures only): the module
# refuses, names the account and the path, and the machine is unchanged (the home hash included, planted link targets too).
refused_layer() {
  refused "$1" "$LAB" "$2" -e lab_apply=true -e lab_deny_layer=both --tags claude_user_deny --skip-tags claude_user_deny_probe
}

reset_layer_fixture() {
  chattr -i "/home/$AI/.claude/settings.json" 2>/dev/null || true
  rm -rf "/home/$AI/.claude" "$WORK/link-target"
  if [[ -L /home/$AI ]]; then
    rm -f "/home/$AI"
    mv "/home/$AI.real" "/home/$AI"
  fi
  chown "$AI:$AI" "/home/$AI"
}

deny_layer_refusals() {
  local claude=/home/$AI/.claude layer=/home/$AI/.claude/settings.json before
  # Mode managed writes nothing into any home (PA-A34), and the variable is checked (PA-52).
  before=$(home_hash)
  playbook "$LAB" -e lab_apply=true -e lab_deny_layer=managed --tags claude_user_deny >"$WORK/managed-only.txt" 2>&1 || {
    cat "$WORK/managed-only.txt"
    fail "mode managed failed"
  }
  [[ $before == "$(home_hash)" && ! -e $claude ]] || fail "mode managed wrote into a home directory"
  refused "an unknown lab_deny_layer is refused" "$LAB" "lab_deny_layer must be both, user, or managed" -e lab_apply=true -e lab_deny_layer=everything

  # PA-A35: the planted ~/.claude link of the old first-run fixture is now a refusal; link targets stay as they were.
  ln -s /etc/claude-code "$claude"
  refused_layer "a ~/.claude that is a link is refused" "account $AI: $claude is a link"
  [[ $(readlink "$claude") == /etc/claude-code ]] || fail "the planted ~/.claude link was changed"
  [[ ! -e /etc/claude-code/settings.json ]] || fail "lab setup followed the planted ~/.claude link"
  reset_layer_fixture

  install -d -m 0700 -o "$AI" -g "$AI" "$claude"
  printf 'target\n' >"$WORK/link-target"
  ln -s "$WORK/link-target" "$layer"
  refused_layer "a settings.json that is a link is refused" "account $AI: $layer is a link"
  [[ $(cat "$WORK/link-target") == target ]] || fail "the target of the planted settings.json link was changed"
  reset_layer_fixture

  install -d -m 0700 -o "$AI" -g "$AI" "$claude"
  install -m 0644 -o root -g root /dev/null "$layer"
  ln "$layer" "$claude/second-name"
  refused_layer "a hard-linked settings.json is refused" "account $AI: $layer is hard-linked"
  reset_layer_fixture

  install -d -m 0700 -o "$AI" -g "$AI" "$claude"
  mkdir "$layer"
  refused_layer "a directory in place of settings.json is refused" "account $AI: $layer is not a regular file"
  reset_layer_fixture

  install -d -m 0700 -o "$AI" -g "$AI" "$claude"
  mkfifo "$layer"
  refused_layer "a device or pipe in place of settings.json is refused" "account $AI: $layer is not a regular file"
  reset_layer_fixture

  install -d -m 0700 -o "$AI" -g "$AI" "$claude"
  printf '{"mine": true}\n' >"$layer"
  chown "$AI:$AI" "$layer"
  refused_layer "a settings.json that the AI user owns is refused and the move-aside command is printed (R2-O2)" \
    "mv ~/.claude/settings.json ~/.claude/settings.json.pre-lab"
  [[ $(cat "$layer") == '{"mine": true}' ]] || fail "the refusal changed the file of the AI user"
  reset_layer_fixture

  mv "/home/$AI" "/home/$AI.real"
  ln -s "/home/$AI.real" "/home/$AI"
  refused_layer "a home that is a link is refused" "account $AI: the home directory /home/$AI is a link"
  reset_layer_fixture

  chown root "/home/$AI"
  refused_layer "a home that the AI user does not own is refused" "account $AI: the home directory /home/$AI is not owned by it"
  reset_layer_fixture
  ok "the user-level layer: every refusal names the account and the path and changes nothing; mode managed writes nothing"
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
  deny_layer_refusals
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
  # Symbolic links the AI user could plant (PA-A11): lab setup follows none of them. The planted ~/.claude link is now a refusal
  # (deny_layer_refusals, PA-A35); the two links left here are not followed, and lab setup writes into no home directory beyond the
  # two paths of the user-level layer.
  ln -s "$KEYS" "/home/$AI/keys"
  ln -s /opt/ai-lab "/home/$ADMIN/tools"
  local before before_outside after after_outside
  before=$(home_hash)
  before_outside=$(home_hash_outside_layer)
  playbook "$LAB" -e lab_apply=true -e ssh_second_login_confirmed=true | tee "$WORK/first-apply.txt"
  after=$(home_hash)
  after_outside=$(home_hash_outside_layer)
  [[ $before_outside == "$after_outside" ]] || fail "lab setup wrote into a user's home directory outside the two paths of the layer"
  [[ $(readlink "/home/$AI/keys") == "$KEYS" && $(readlink "/home/$ADMIN/tools") == /opt/ai-lab ]] || fail "a planted link was changed"
  [[ ! -e /home/$ADMIN/.claude ]] || fail "lab setup wrote a ~/.claude for the lab admin"
  if [[ $(deny_mode) == managed ]]; then
    [[ $before == "$after" && ! -e /home/$AI/.claude ]] || fail "mode managed wrote into a home directory"
    ok "first run (mode managed, the attribute is not testable here): home directories unchanged, planted links not followed"
  else
    check_layer_content
    ok "first run: only the layer changed in the homes, planted links not followed, the layer is the canonical object (PA-A34)"
  fi
  [[ $(stat -c '%U:%G %a' "$TOOLS/deny.txt") == 'root:root 644' ]] || fail "deny.txt is not root-owned 0644"
  cmp -s "$TOOLS/deny.txt" "$LAB/workspace/claude-user/required-deny.txt" || fail "deny.txt is not a byte copy of required-deny.txt"
  grep -qx "deny_layer=$(deny_mode)" "$TOOLS/lab.conf" || fail "lab.conf does not record deny_layer=$(deny_mode)"
}

# check_layer_content: ~/.claude and the layer as PA-A34 states them, compared entry by entry with the core list.
check_layer_content() {
  local layer=/home/$AI/.claude/settings.json
  [[ $(stat -c '%U:%G %a' "/home/$AI/.claude") == "$AI:$AI 700" ]] || fail "the .claude directory is not owned by the AI user with mode 0700"
  [[ $(stat -c '%U:%G %a %h' "$layer") == 'root:root 644 1' ]] || fail "the layer is not root:root 0644 with one link"
  lsattr -d "$layer" | awk '{print $1}' | grep -q i || fail "the layer is not immutable"
  jq -e '.enableAllProjectMcpServers == false and .permissions.disableBypassPermissionsMode == "disable"
    and (keys == ["enableAllProjectMcpServers", "permissions"]) and (.permissions | keys == ["deny", "disableBypassPermissionsMode"])' "$layer" >/dev/null ||
    fail "the layer is not the canonical object"
  diff <(jq -r '.permissions.deny[]' "$layer") <(grep -vE '^[[:space:]]*(#|$)' "$LAB/workspace/claude-user/required-deny.txt") >/dev/null ||
    fail "the layer's deny list is not the core list entry by entry and in order"
  [[ $(jq '.permissions.deny | length' "$layer") -eq 90 ]] || fail "the layer does not hold 90 entries"
  [[ $(tail -c 1 "$layer" | od -An -tx1 | tr -d ' ') == 0a ]] || fail "the layer has no final newline"
}

second_run() {
  playbook "$LAB" -e lab_apply=true -e ssh_second_login_confirmed=true | tee "$WORK/second-apply.txt"
  grep -Eq 'changed=0 +unreachable=0 +failed=0' "$WORK/second-apply.txt" || fail "the second run changed something"
  # The reload and its record are for systemd hosts only (a real reload is PA-A33): a container has no systemd, so none is recorded.
  [[ ! -e $LOADED ]] || fail "a reload of sshd is recorded on a host without systemd"
  ok "second run: zero changes, no reload recorded without systemd"
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

# deny_layer: plan PR 4a, PA-A37. With the attribute: every write attempt of the AI user fails, LC-16 passes, each root change after
# `chattr -i` makes LC-16 fail, and a lab switched to mode managed keeps the layer. Without it: the fail-closed fixture of PA-51.
deny_layer() {
  local layer=/home/$AI/.claude/settings.json
  complete_lab
  if [[ $(deny_mode) == managed ]]; then
    deny_fail_closed
    return
  fi
  local attempt sum inode mutation
  sum=$(sha256sum "$layer")
  # shellcheck disable=SC2016 # the attempts are for the inner shell, which expands $1
  for attempt in 'printf x >>"$1"' ': >"$1"' 'rm -f -- "$1"' 'mv -- "$1" "$1.off"' 'ln -- "$1" "$1.link"' 'chmod 0600 -- "$1"' 'chattr -i -- "$1"'; do
    if as_ai bash -c "$attempt" _ "$layer" 2>/dev/null; then fail "the AI user succeeded with: $attempt"; fi
  done
  [[ $(sha256sum "$layer") == "$sum" ]] || fail "the layer changed under the write attempts of the AI user"
  [[ $(ls -A "/home/$AI/.claude") == settings.json ]] || fail "a write attempt left a file in ~/.claude"
  check_layer_content
  lab_run --gh "$LAB_GH"
  expect_failing "LC-16 passes on the complete layer" ""
  grep -q '^PASS LC-16:' "$WORK/lab-check.txt" || fail "LC-16 does not pass"
  # Each change that root makes after `chattr -i` makes LC-16 fail; lab setup puts the layer back.
  for mutation in unflag content mode owner; do
    chattr -i "$layer"
    case $mutation in
      content) jq '.permissions.deny += ["Bash(extra *)"]' "$layer" >"$WORK/layer.new" && cat "$WORK/layer.new" >"$layer" ;;
      mode) chmod 0600 "$layer" ;;
      owner) chown "$AI:$AI" "$layer" ;;
      *) ;;
    esac
    if [[ $mutation != unflag ]]; then chattr +i "$layer"; fi
    lab_run --gh "$LAB_GH"
    expect_failing "root change '$mutation' after chattr -i makes LC-16 fail" "LC-16"
    chattr -i "$layer" 2>/dev/null || true
    rm -f "$layer"
    playbook "$LAB" -e lab_apply=true --tags claude_user_deny >"$WORK/layer-restore.txt" 2>&1 || {
      cat "$WORK/layer-restore.txt"
      fail "lab setup did not put the layer back after '$mutation'"
    }
    check_layer_content
  done
  # A second run changes nothing (the layer included), and a lab switched to mode managed keeps the layer, unchanged.
  playbook "$LAB" -e lab_apply=true --tags claude_user_deny | tee "$WORK/layer-again.txt"
  grep -Eq 'changed=0 +unreachable=0 +failed=0' "$WORK/layer-again.txt" || fail "the second run changed the layer"
  sum=$(sha256sum "$layer")
  inode=$(stat -c %i "$layer")
  playbook "$LAB" -e lab_apply=true -e lab_deny_layer=managed --tags lab_tools,claude_user_deny >"$WORK/layer-managed.txt" 2>&1 ||
    { cat "$WORK/layer-managed.txt"; fail "the switch to mode managed failed"; }
  [[ $(sha256sum "$layer") == "$sum" && $(stat -c %i "$layer") == "$inode" ]] || fail "switching to mode managed changed the layer"
  grep -qx deny_layer=managed "$TOOLS/lab.conf" || fail "lab.conf does not record the switch"
  lab_run --gh "$LAB_GH"
  expect_failing "a lab switched from both to managed passes" ""
  grep -q '^WARN LC-16: .*switched' "$WORK/lab-check.txt" || fail "LC-16 does not warn about the root-owned file in mode managed"
  playbook "$LAB" -e lab_apply=true -e lab_deny_layer=both --tags lab_tools,claude_user_deny >/dev/null 2>&1 || fail "the switch back to both failed"
  grep -qx deny_layer=both "$TOOLS/lab.conf" || fail "lab.conf does not record the switch back"
  printf 'immutable attribute proved in this job: write, append, truncate, rm, mv, ln, chmod, chattr -i by the AI user fail; LC-16 fails for each root change\n' >>"$WORK/attribute.txt"
  # The fail-closed fixture of PA-51 also runs here, for real: with the capability dropped from the bounding set the attribute cannot be
  # set, which is what a container without it looks like. The layer is removed first (as root) and put back by lab setup afterwards.
  command -v capsh >/dev/null || fail "capsh is not installed (package libcap2-bin): the fail-closed fixture cannot run"
  chattr -i "$layer"
  rm -rf "/home/$AI/.claude"
  capsh --drop=cap_linux_immutable -- -c "'$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/pa28-lab.sh' deny-fail-closed" ||
    fail "the fail-closed fixture failed with the capability dropped"
  playbook "$LAB" -e lab_apply=true --tags claude_user_deny >"$WORK/layer-restore.txt" 2>&1 || {
    cat "$WORK/layer-restore.txt"
    fail "lab setup did not put the layer back after the fail-closed fixture"
  }
  check_layer_content
  ok "user-level layer: the attribute holds against the AI user, LC-16 sees each change, the switch to managed removes nothing"
}

# deny_fail_closed (PA-51, PA-A37): the attribute is not usable here, so mode both must fail, leave no file, and name the errno; mode
# managed (what the other steps used) must have written nothing.
deny_fail_closed() {
  local claude=/home/$AI/.claude
  [[ ! -e $claude ]] || fail "mode managed left a ~/.claude"
  refused "mode both fails when the attribute is not usable (the probe pre-task)" "$LAB" "does not support the immutable attribute" -e lab_apply=true -e lab_deny_layer=both
  grep -Eq 'errno E[A-Z]+' "$WORK/refusal.txt" || fail "the failure does not name the errno"
  [[ ! -e $claude ]] || fail "the failed probe left a ~/.claude"
  refused "mode both fails after the file is placed and leaves nothing (the module itself)" "$LAB" "does not support the immutable attribute" \
    -e lab_apply=true -e lab_deny_layer=both --tags claude_user_deny --skip-tags claude_user_deny_probe
  grep -Eq 'errno E[A-Z]+' "$WORK/refusal.txt" || fail "the module's failure does not name the errno"
  [[ ! -e $claude ]] || fail "the failed write left a ~/.claude or a file in it"
  printf 'fail-closed fixture passed: mode both fails before any change and, with the probe skipped, after placing the file; nothing is left behind\n' >>"$WORK/attribute.txt"
  ok "mode both fails closed without the attribute, names the errno, and leaves no file"
}

# project: plan PR 8, PA-34, PA-A23, PA-A31 (I-7, O-18, O-22, R-2). A project repository owned by the AI user (a merged-by-choice commit
# the user supplies, with the project's CI manifest, a package list, a seeded .claude/deny.platform.txt, and a planted scripts/toolchain
# that writes a sentinel when run). The dry run prints every package name and version and changes nothing; the apply needs the digest of
# that dry run; the tools land root-owned in /opt/ai-lab/project; the smoke test prints the AI user's own name; the AI user cannot change
# the tools or the records; the project's scripts/toolchain never runs; a second run changes nothing; one list feeds deny.txt, the managed
# settings, and the layer; a third-party apt source is refused before anything changes; the lab check passes and then fails for a listed
# path that the project's file does not cover.
readonly PROJECT_TOOLS=/opt/ai-lab/project RECORD=/opt/ai-lab/lab/project
project_commit() { # project_commit MESSAGE: commit the working tree of the fixture project as the AI user, print the SHA
  # shellcheck disable=SC2016 # the command is for the inner shell, which expands ~ and $1
  as_ai bash -c 'cd ~/work/project-fixture && git add -A && git -c user.name=ci -c user.email=noreply commit -q -m "$1" && git rev-parse HEAD' _ "$1"
}
project_fixture() {
  local sentinel=$WORK/planted-ran
  rm -f "$sentinel"
  as_ai bash -c 'rm -rf ~/work/project-fixture && mkdir -p ~/work/project-fixture/toolchain ~/work/project-fixture/.claude ~/work/project-fixture/scripts ~/work/project-fixture/docs ~/.config/svc &&
    git -C ~/work/project-fixture init -q -b main && : >~/.config/svc/token && chmod 0600 ~/.config/svc/token'
  # The project's CI manifest: one download tool (the artifact and checksum of the platform manifest's yq, so no new pin is needed here)
  # whose smoke command prints the account that runs it.
  python3 -I - "$LAB/toolchain/manifest.toml" "$AI" >"$WORK/project-manifest.toml" <<'PY'
import sys
import tomllib

with open(sys.argv[1], "rb") as handle:
    tool = tomllib.load(handle)["tools"]["yq"]
artifact = tool["artifacts"]["amd64"]
print(f"""schema_version = 1

[tools.yq]
version     = "{tool["version"]}"
profiles    = ["lab"]
source      = "download"
format      = "binary"
binaries    = ["yq"]
smoke       = ["id", "-un"]
smoke_match = "{sys.argv[2]}"
max_bytes   = 104857600

[tools.yq.artifacts.amd64]
url    = "{artifact["url"]}"
sha256 = "{artifact["sha256"]}"
""")
PY
  install -m 0644 -o "$AI" -g "$AI" "$WORK/project-manifest.toml" "/home/$AI/work/project-fixture/toolchain/manifest.toml"
  printf '# the project package list\nhello\n' | as_ai tee "/home/$AI/work/project-fixture/toolchain/lab-packages.txt" >/dev/null
  printf '# the project seeded list\nRead(~/.config/svc/**)\n' | as_ai tee "/home/$AI/work/project-fixture/.claude/deny.platform.txt" >/dev/null
  # shellcheck disable=SC2016 # backticks are Markdown here
  printf '## Credential paths\n\n- `~/.config/svc/token` - a test credential\n' | as_ai tee "/home/$AI/work/project-fixture/docs/PROJECT.md" >/dev/null
  printf '#!/bin/sh\n: >%s\n' "$sentinel" | as_ai tee "/home/$AI/work/project-fixture/scripts/toolchain" >/dev/null
  as_ai chmod 0755 "/home/$AI/work/project-fixture/scripts/toolchain"
}

project() {
  complete_lab
  local repo=/home/$AI/work/project-fixture sentinel=$WORK/planted-ran sha digest before after homes_before homes_after attempt entry
  project_fixture
  sha=$(project_commit "A: the project's toolchain, package list, and deny list")
  local -a args=(-e "lab_project_clone=$repo" -e "lab_project_sha=$sha" -e ssh_second_login_confirmed=true)

  # 1. The dry run reads the project, prints every package name and version and the tools it would install, and changes nothing.
  before=$(tree_hash)
  homes_before=$(home_hash)
  playbook "$LAB" --check --diff "${args[@]}" >"$WORK/project-dry.txt" 2>&1 || { cat "$WORK/project-dry.txt"; fail "the dry run with a project failed"; }
  cat "$WORK/project-dry.txt"
  after=$(tree_hash)
  homes_after=$(home_hash)
  [[ $before == "$after" && $homes_before == "$homes_after" ]] || fail "the dry run with a project changed the machine"
  grep -Eq 'hello [0-9][^ ]* Debian' "$WORK/project-dry.txt" || fail "the dry run does not print the name, version, and origin of the package"
  grep -q 'would install' "$WORK/project-dry.txt" || fail "the dry run does not say what the toolchain would install"
  digest=$(grep -o 'plan_sha256=[0-9a-f]\{64\}' "$WORK/project-dry.txt" | head -n 1 | cut -d= -f2)
  [[ -n $digest ]] || fail "the dry run prints no plan digest"
  [[ ! -e $PROJECT_TOOLS && ! -e $RECORD ]] || fail "the dry run created the project tools or records"
  ok "project dry run: every package name and version printed, tree and homes unchanged"

  # 2. The package list is applied only after the dry run was read: no digest, no change (the play stops before any role has written).
  refused "a package list is not applied without the digest of its dry run" "$LAB" "lab_project_packages_reviewed" -e lab_apply=true "${args[@]}"
  ! dpkg -s hello >/dev/null 2>&1 || fail "the package was installed without the digest"
  [[ ! -e $PROJECT_TOOLS ]] || fail "the tools were installed before the package list was accepted"
  refused "a digest that is not the digest of the plan is refused" "$LAB" "changed since" -e lab_apply=true "${args[@]}" -e "lab_project_packages_reviewed=$(printf '0%.0s' {1..64})"

  # 3. The apply with the digest: tools, packages, records, and the one deny list in three places.
  playbook "$LAB" -e lab_apply=true "${args[@]}" -e "lab_project_packages_reviewed=$digest" | tee "$WORK/project-apply.txt"
  dpkg -s hello >/dev/null 2>&1 || fail "the package of the list is not installed"
  [[ $(stat -c '%U:%G %a' "$PROJECT_TOOLS" "$PROJECT_TOOLS/bin" "$RECORD" | sort -u) == 'root:root 755' ]] || fail "the project directories are not root-owned 0755"
  [[ -L $PROJECT_TOOLS/bin/yq && -x $PROJECT_TOOLS/bin/yq ]] || fail "the project tool is not linked into $PROJECT_TOOLS/bin"
  [[ -z $(find "$PROJECT_TOOLS" "$RECORD" \( ! -user root -o -perm /022 \) -not -type l -print -quit) ]] || fail "something under the project directories is not root-owned or is writable by others"
  for entry in manifest.toml packages.txt deny.platform.txt SOURCE; do
    [[ $(stat -c '%U:%G %a' "$RECORD/$entry") == 'root:root 644' ]] || fail "$RECORD/$entry is not a root-owned 0644 file"
  done
  grep -qx "kind=supplied-sha" "$RECORD/SOURCE" || fail "the record does not name the supplied-SHA channel"
  grep -qx "commit=$sha" "$RECORD/SOURCE" || fail "the record does not name the supplied commit"
  [[ ! -e $sentinel ]] || fail "the project's own scripts/toolchain was run"
  [[ -z $(find "$RECORD" "$PROJECT_TOOLS" -name toolchain -path '*scripts*') ]] || fail "the project's scripts/toolchain was copied to the machine"
  entry='Read(~/.config/svc/**)'
  grep -qxF "$entry" "$TOOLS/deny.txt" || fail "deny.txt lacks the project's entry"
  jq -e --arg e "$entry" '.permissions.deny | index($e) != null' /etc/claude-code/managed-settings.json >/dev/null || fail "the managed settings lack the project's entry"
  # The managed settings may also hold entries of the merge step (a foreign file is merged, never replaced), so they are compared as a set.
  [[ -z $(comm -13 <(jq -r '.permissions.deny[]' /etc/claude-code/managed-settings.json | LC_ALL=C sort -u) \
    <(grep -vE '^[[:space:]]*(#|$)' "$TOOLS/deny.txt" | LC_ALL=C sort -u)) ]] || fail "the managed settings lack an entry of the lab-wide list"
  [[ $(grep -vcE '^[[:space:]]*(#|$)' "$TOOLS/deny.txt") -eq 91 ]] || fail "deny.txt does not hold the core list and one project entry"
  if [[ $(deny_mode) != managed ]]; then
    diff <(jq -r '.permissions.deny[]' "/home/$AI/.claude/settings.json") <(grep -vE '^[[:space:]]*(#|$)' "$TOOLS/deny.txt") >/dev/null ||
      fail "the layer is not the lab-wide list entry by entry and in order"
    [[ $(jq '.permissions.deny | length' "/home/$AI/.claude/settings.json") -eq 91 ]] || fail "the layer does not hold the core list and one project entry"
    lsattr -d "/home/$AI/.claude/settings.json" | awk '{print $1}' | grep -q i || fail "the layer is not immutable"
  fi
  diff <(head -n 90 <(grep -vE '^[[:space:]]*(#|$)' "$TOOLS/deny.txt")) <(grep -vE '^[[:space:]]*(#|$)' "$LAB/workspace/claude-user/required-deny.txt") >/dev/null ||
    fail "the core entries of deny.txt are not the 90 entries of required-deny.txt in order"
  ok "project apply: tools root-owned, package installed, the records, and one deny list in deny.txt, the managed settings, and the layer"

  # 4. Smoke tests run as the AI user, with the installed engine, and print its name.
  as_ai python3 -I "$TOOLS/engine/scripts/toolchain" --manifest "$RECORD/manifest.toml" --root "$RECORD" verify --profile lab \
    --prefix "$PROJECT_TOOLS" --arch amd64 --source download >"$WORK/project-smoke.txt" 2>&1 || { cat "$WORK/project-smoke.txt"; fail "the smoke test failed as the AI user"; }
  grep -q "ok ($AI)" "$WORK/project-smoke.txt" || { cat "$WORK/project-smoke.txt"; fail "the smoke test did not print the AI user's name"; }
  grep -q "ok ($AI)" "$WORK/project-apply.txt" || fail "lab setup did not run the smoke test as the AI user"
  # shellcheck disable=SC2016 # the command is for the inner login shell, which expands $PATH
  [[ $(as_ai bash -lc 'printf %s "${PATH##*:}"') == "$PROJECT_TOOLS/bin" ]] || fail "the project tools are not last on the AI user's PATH"
  ok "smoke tests: run as the AI user and print its name"

  # 5. The AI user cannot change the installed tools or the records.
  local target
  for target in "$PROJECT_TOOLS" "$PROJECT_TOOLS/bin" "$PROJECT_TOOLS/bin/yq" "$(readlink -f "$PROJECT_TOOLS/bin/yq")" "$RECORD" "$RECORD/manifest.toml" "$RECORD/deny.platform.txt" "$RECORD/SOURCE"; do
    # shellcheck disable=SC2016 # the attempts are for the inner shell, which expands $1
    for attempt in 'printf x >>"$1"' ': >"$1"' 'rm -rf -- "$1"' 'mv -- "$1" "$1.off"' 'chmod 0777 -- "$1"' 'touch -- "$1/new"'; do
      if as_ai bash -c "$attempt" _ "$target" 2>/dev/null; then fail "the AI user succeeded with '$attempt' on $target"; fi
    done
  done
  ok "the AI user cannot write, move, remove, or chmod the project tools or records"

  # 6. A second run, with and without the project variables, changes nothing; the recorded deny list is kept.
  playbook "$LAB" -e lab_apply=true "${args[@]}" | tee "$WORK/project-second.txt"
  grep -Eq 'changed=0 +unreachable=0 +failed=0' "$WORK/project-second.txt" || fail "the second run with the project changed something"
  playbook "$LAB" -e lab_apply=true -e ssh_second_login_confirmed=true | tee "$WORK/project-recorded.txt"
  grep -Eq 'changed=0 +unreachable=0 +failed=0' "$WORK/project-recorded.txt" || fail "a run with no project selected changed something (the recorded deny entries must be kept)"
  grep -qxF "$entry" "$TOOLS/deny.txt" || fail "a run with no project selected dropped the project's deny entry"
  ok "second run: zero changes, with the project variables and without them (the recorded entries are kept)"

  # 7. The lab check passes with the entry that arrived from the project, and fails for a listed path that the file does not cover.
  lab_run --gh "$LAB_GH"
  expect_failing "the lab check passes: the credential path is covered by the entry that lab setup merged (PA-A31)" ""
  # shellcheck disable=SC2016 # backticks are Markdown here
  printf '## Credential paths\n\n- `~/.config/svc/token` - a test credential\n- `~/.config/other/key` - one the project forgot\n' |
    as_ai tee "$repo/docs/PROJECT.md" >/dev/null
  lab_run --gh "$LAB_GH"
  expect_failing "a listed path that deny.platform.txt does not cover fails PA-43" "PA-43"
  # shellcheck disable=SC2088 # the text is the message, with the tilde as written in PROJECT.md
  mentions "$WORK/lab-check.txt" '~/.config/other/key is not covered' || fail "PA-43 does not name the uncovered path"

  # 8. A third-party apt source in the package list is refused before anything changes; so is a pip tool.
  printf '# a package list that adds a source\ndeb http://example.org/debian trixie main\n' | as_ai tee "$repo/toolchain/lab-packages.txt" >/dev/null
  sha=$(project_commit "B: a third-party apt source")
  refused "a third-party apt source is refused" "$LAB" "third-party apt source" -e lab_apply=true -e "lab_project_clone=$repo" -e "lab_project_sha=$sha" -e ssh_second_login_confirmed=true
  refused "a third-party apt source is refused in the dry run too" "$LAB" "third-party apt source" --check --diff -e "lab_project_clone=$repo" -e "lab_project_sha=$sha"
  ok "a third-party apt source is refused before anything changes"

  # 9. The anonymous channel, for real, in a dry run: a tag of this repository on GitHub (merged by definition: a release tag).
  if [[ -n ${GITHUB_REPOSITORY:-} ]]; then
    playbook "$LAB" --check --diff -e "lab_project_repo=https://github.com/$GITHUB_REPOSITORY" -e lab_project_ref=v0.9.0 >"$WORK/project-anonymous.txt" 2>&1 ||
      { cat "$WORK/project-anonymous.txt"; fail "the anonymous channel did not read the tag"; }
    ok "anonymous channel: a release tag of this repository was read in a dry run"
  else
    printf 'anonymous channel not exercised here: GITHUB_REPOSITORY is not set\n' >>"$WORK/attribute.txt"
  fi
  as_ai bash -c 'rm -rf ~/work ~/.config/svc ~/.config/other' || true
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
  deny-probe) deny_probe ;;
  deny-layer) deny_layer ;;
  deny-fail-closed) deny_fail_closed ;;
  project) project ;;
  *)
    echo "usage: pa28-lab.sh prepare SOURCE | deny-probe | refusals | unconfirmed | first-run | second-run | dry-run | verify | merge | token-step | lab-check | deny-layer | deny-fail-closed | project" >&2
    exit 2
    ;;
esac
