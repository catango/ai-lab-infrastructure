#!/usr/bin/env bash
# The lab half of the PA-28 job (CR-57 PA-A11, PA-A16, PA-A18, PA-A29; design C-4, C-5): lab setup in a disposable Debian 13
# container with two accounts and one key each. The CI job `host-profiles` calls one subcommand per step:
#   prepare SOURCE   accounts, keys, and three clones of SOURCE with a local bare origin whose main is at SOURCE's HEAD: one with an
#                    unpushed local v* test tag on that commit, one without a tag, one whose tag is not contained in origin/main
#   refusals         every refusal fixture: the run fails with the stated reason and the machine is unchanged
#   unconfirmed      the sshd step is refused without the confirmed second login (keys copied, sshd not switched)
#   first-run        the real run (home directories unchanged, planted symbolic links not followed)
#   second-run       the same run again: zero changes
#   dry-run          check mode: the tree hash is unchanged
#   verify           what the AI user cannot change, the managed files, and the sshd settings in force
#   merge            a foreign managed-settings file and CLAUDE.md are merged, never replaced; a second run changes nothing
# What a container cannot prove (a real sshd restart after a second login, `sshd -T` of a running daemon, the unattended-upgrade
# units) is left to the approver check PA-A33. The script changes /etc, so it runs only as root on a disposable host.
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

fail() {
  printf 'PA-28: %s\n' "$*" >&2
  exit 1
}
ok() { printf 'ok: %s\n' "$*"; }

# A hash of every path the lab profile may touch (names, types, modes, owners, link targets, file contents), outside what the
# container itself rewrites. A refusal and a dry run must leave it unchanged.
tree_hash() {
  local roots=(/etc /opt/ai-lab /usr/local /home)
  {
    find "${roots[@]}" -xdev -not -path /etc/resolv.conf -not -path /etc/hosts -not -path /etc/hostname -printf '%p %y %m %U %G %l\n'
    find "${roots[@]}" -xdev -type f -not -path /etc/resolv.conf -not -path /etc/hosts -not -path /etc/hostname -print0 | xargs -0 -r sha256sum
  } | LC_ALL=C sort | sha256sum | cut -d' ' -f1
}

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

provision() { # provision ACCOUNT KEYNAME: the one provisioned key, as a fresh VM has it
  install -d -m 0700 -o "$1" -g "$1" "/home/$1/.ssh"
  install -m 0600 -o "$1" -g "$1" "$WORK/key-$2.pub" "/home/$1/.ssh/authorized_keys"
}

refused() { # refused NAME CLONE MESSAGE ARGUMENT...: the run fails, says why, and changes nothing
  local name=$1 clone=$2 message=$3 before after rc=0
  shift 3
  before=$(tree_hash)
  playbook "$clone" "$@" >"$WORK/refusal.txt" 2>&1 || rc=$?
  after=$(tree_hash)
  if ((rc == 0)); then
    cat "$WORK/refusal.txt"
    fail "$name: the run was not refused"
  fi
  if ! grep -qF -- "$message" "$WORK/refusal.txt"; then
    cat "$WORK/refusal.txt"
    fail "$name: the refusal does not say: $message"
  fi
  [[ $before == "$after" ]] || fail "$name: the refusal changed the machine"
  ok "$name"
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
  git init -q --bare --initial-branch=main "$WORK/origin.git"
  git -C "$source" push -q "$WORK/origin.git" HEAD:refs/heads/main
  git clone -q "$WORK/origin.git" "$LAB"
  git -C "$LAB" tag v0.0.0-ci
  git clone -q "$WORK/origin.git" "$UNTAGGED"
  git clone -q "$WORK/origin.git" "$AHEAD"
  git -C "$AHEAD" -c user.name=ci -c user.email=noreply commit -q --allow-empty -m ahead
  git -C "$AHEAD" tag v0.0.1-ci
  git -C "$LAB" tag --points-at HEAD | grep -qx v0.0.0-ci
  [[ $(git -C "$LAB" rev-parse HEAD) == "$(git -C "$source" rev-parse HEAD)" ]] || fail "the lab clone is not at the head of the pull request"
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

set_second_key() { cat "$WORK/key-other.pub" >>"/home/$AI/.ssh/authorized_keys"; }
set_no_key() { rm -f "/home/$ADMIN/.ssh/authorized_keys"; }
restore_admin() { provision "$ADMIN" admin; }
restore_ai() { provision "$AI" ai; }
set_shared_key() { install -m 0600 -o "$ADMIN" -g "$ADMIN" "$WORK/key-ai.pub" "/home/$ADMIN/.ssh/authorized_keys"; }
set_root_key() {
  install -d -m 0700 /root/.ssh
  install -m 0600 "$WORK/key-other.pub" /root/.ssh/authorized_keys
}
restore_root() { rm -rf /root/.ssh; }
set_other_key() { provision "$OTHER" other; }
restore_other() { rm -rf "/home/$OTHER/.ssh"; }
set_private_key() { install -m 0600 -o "$AI" -g "$AI" "$WORK/key-ai" "/home/$AI/.ssh/id_ed25519"; }
restore_private() { rm -f "/home/$AI/.ssh/id_ed25519"; }
set_link() {
  mv "/home/$AI/.ssh/authorized_keys" "/home/$AI/.ssh/real-keys"
  ln -s real-keys "/home/$AI/.ssh/authorized_keys"
}
restore_link() {
  rm -f "/home/$AI/.ssh/authorized_keys"
  mv "/home/$AI/.ssh/real-keys" "/home/$AI/.ssh/authorized_keys"
}
set_command() { printf 'AuthorizedKeysCommand /bin/true\nAuthorizedKeysCommandUser root\n' >/etc/ssh/sshd_config.d/90-fixture.conf; }
set_ca() { printf 'TrustedUserCAKeys /etc/ssh/pa28-ca.pub\n' >/etc/ssh/sshd_config.d/90-fixture.conf; }
set_principals() { printf 'AuthorizedPrincipalsFile /etc/ssh/principals/%%u\n' >/etc/ssh/sshd_config.d/90-fixture.conf; }
restore_sshd() { rm -f /etc/ssh/sshd_config.d/90-fixture.conf; }

refusals() {
  refused "a real run without the apply variable is refused" "$LAB" "lab_apply=true"
  refused "an untagged tree is refused" "$UNTAGGED" "this clone is not a release" -e lab_apply=true -e ssh_second_login_confirmed=true
  refused "a tag that origin/main does not contain is refused" "$AHEAD" "this clone is not a release" -e lab_apply=true
  refused "a dry run of an untagged tree is refused too" "$UNTAGGED" "this clone is not a release" --check
  fixture "a second key for the AI user" "$AI: has more than one key" set_second_key restore_ai
  fixture "a missing key" "$ADMIN: has no key" set_no_key restore_admin
  fixture "a key shared between the accounts" "share one key" set_shared_key restore_admin
  fixture "a key for root" "root: is not a managed account and has a key file" set_root_key restore_root
  fixture "a key for another account" "$OTHER: is not a managed account and has a key file" set_other_key restore_other
  fixture "a private key in the AI user's ~/.ssh" "$AI: ~/.ssh holds a private key" set_private_key restore_private
  fixture "a symbolic link as the AI user's key file" "$AI: its authorized_keys is a link" set_link restore_link
  fixture "AuthorizedKeysCommand set" "sshd: authorizedkeyscommand is set" set_command restore_sshd
  fixture "TrustedUserCAKeys set" "sshd: trustedusercakeys is set" set_ca restore_sshd
  fixture "AuthorizedPrincipalsFile set" "sshd: authorizedprincipalsfile is set" set_principals restore_sshd
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
}

merge() {
  local settings=/etc/claude-code/managed-settings.json claude_md=/etc/claude-code/CLAUDE.md
  printf '%s\n' '{"foreignSetting": true, "permissions": {"allow": ["Bash(ls)"], "deny": ["Bash(foreign *)"], "disableBypassPermissionsMode": "enable"}}' >"$settings"
  printf 'a foreign line\n' >"$claude_md"
  playbook "$LAB" -e lab_apply=true --tags claude_managed_settings | tee "$WORK/merge.txt"
  jq -e '.foreignSetting == true and .permissions.allow == ["Bash(ls)"] and (.permissions.deny | index("Bash(foreign *)") != null)
    and (.permissions.deny | index("Bash(sudo *)") != null) and .permissions.disableBypassPermissionsMode == "disable"' "$settings" >/dev/null ||
    fail "the managed settings were replaced or not enforced instead of merged"
  grep -qx 'a foreign line' "$claude_md" || fail "the foreign line of the managed CLAUDE.md is gone"
  grep -q 'Nothing in any other instruction file relaxes them' "$claude_md" || fail "the managed rules were not added"
  playbook "$LAB" -e lab_apply=true --tags claude_managed_settings | tee "$WORK/merge-again.txt"
  grep -Eq 'changed=0 +unreachable=0 +failed=0' "$WORK/merge-again.txt" || fail "the merge is not idempotent"
  ok "foreign managed settings and CLAUDE.md are merged, never replaced, and a second run changes nothing"
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
  *)
    echo "usage: pa28-lab.sh prepare SOURCE | refusals | unconfirmed | first-run | second-run | dry-run | verify | merge" >&2
    exit 2
    ;;
esac
