#!/usr/bin/env bash
# Shared helpers of the two halves of the PA-28 job (pa28-lab.sh and pa28-operator.sh). Sourced, never run directly.
# The caller sets TREE_ROOTS (an array: the directories its profile may touch) before it calls tree_list or tree_hash.
set -euo pipefail

fail() {
  printf 'PA-28: %s\n' "$*" >&2
  exit 1
}
ok() { printf 'ok: %s\n' "$*"; }

# tree_list: the names, types, modes, owners, link targets, and file contents under TREE_ROOTS, outside what the container itself
# rewrites. A refusal and a dry run must leave tree_hash unchanged; tree_list shows what changed when two hashes differ.
tree_list() {
  local roots=() root
  for root in "${TREE_ROOTS[@]}"; do
    if [[ -e $root ]]; then roots+=("$root"); fi
  done
  {
    find "${roots[@]}" -xdev -not -path /etc/resolv.conf -not -path /etc/hosts -not -path /etc/hostname -printf '%p %y %m %U %G %l\n'
    find "${roots[@]}" -xdev -type f -not -path /etc/resolv.conf -not -path /etc/hosts -not -path /etc/hostname -print0 | xargs -0 -r sha256sum
  } | LC_ALL=C sort
}
tree_hash() { tree_list | sha256sum | cut -d' ' -f1; }

# mentions FILE TEXT...: the file has every text
mentions() {
  local text
  for text in "${@:2}"; do grep -qF -- "$text" "$1" || return 1; done
}

# ---- the key rules (PA-16, PA-A29), the same fixtures for the lab and the operator profile
# The caller sets WORK, AI (the account whose ~/.ssh may hold no private key: the AI user, or the operator user), ADMIN (the admin account
# with the other key), OTHER (an account that is not managed), the keys $WORK/key-{ai,admin,other}[.pub], and these functions:
#   playbook CLONE ARGUMENT...        runs the profile and passes the arguments on
#   fixture NAME MESSAGE SETUP RESTORE   puts the machine in a bad state, expects the refusal, puts it back
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

key_rule_fixtures() {
  fixture "a second key for the first managed account" "$AI: has more than one key" set_second_key restore_ai
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
