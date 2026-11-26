#!/usr/bin/env bash
# The operator half of the PA-28 job (CR-57 PA-A14, PA-A18, PA-A21, PA-A26, PA-A27, PA-A29, PA-A30; design C-4, C-5): the operator
# configuration in a disposable Debian 13 container with two managed accounts and one key each. The CI job `operator-profile` calls one
# subcommand per step: prepare SOURCE (accounts, keys, four clones of SOURCE with a local bare origin at its HEAD: one with an unpushed
# local v* test tag, one without a tag, one whose tag origin/main does not contain, a second one with its own tag for a second project;
# the first clone is made under umask 002 and the second under umask 000, as an operator admin's account may have them, so the installed
# tree must not inherit the clone's modes),
# refusals (release tag, apply variable, wrong user, key rules), unconfirmed (the sshd step without the second login), first-run,
# second-run, dry-run, second-project (a second project is installed beside the first, then nothing changes), verify (what the operator user
# cannot change, sshd settings in force), operator-check (the installed check as the operator user: OC-8 and OC-12 shown, the failures a
# container can show, the run lock; the tree hash is unchanged). A real sshd restart, `sshd -T` of a running daemon, the unattended-upgrade
# units, and that the operator user cannot sudo on a real machine are PA-A33. The lab half is pa28-lab.sh, in its own container: the two
# profiles own the same sshd drop-in.
# The script changes /etc, so it runs only as root on a disposable host.
set -euo pipefail

if [[ ${AI_LAB_ALLOW_SYSTEM_CHANGES:-} != 1 || $(id -u) -ne 0 ]]; then
  echo "refusing to run: set AI_LAB_ALLOW_SYSTEM_CHANGES=1 and run as root on a disposable host" >&2
  exit 2
fi

readonly WORK=/var/tmp/pa28
# AI, ADMIN, and OTHER are the names pa28-common.sh uses: here the first account is the operator user (it may hold no private key).
readonly AI=ci-op ADMIN=ci-opadm OTHER=ci-other
readonly KEYS=/etc/ssh/authorized_keys
readonly DROPIN=/etc/ssh/sshd_config.d/00-ai-lab.conf
readonly LOADED=/etc/ssh/ai-lab-sshd-loaded.txt
readonly TOOLS=/opt/ai-lab/operator
readonly STATE=/var/lib/ai-lab/operator
readonly CLONE=$WORK/clone UNTAGGED=$WORK/untagged AHEAD=$WORK/ahead SECOND=$WORK/second
readonly SECOND_NAME=second-project
# The name of the first project is the one the profile reads from config/project.yaml of the clone it runs from (the default list).
PROJECT=$(sed -n 's/^  name: //p' "$(dirname "${BASH_SOURCE[0]}")/../../config/project.yaml" | head -n 1)
readonly PROJECT
# shellcheck disable=SC2034 # read by tree_list in pa28-common.sh
TREE_ROOTS=(/etc /opt/ai-lab /usr/local /home /var/lib/ai-lab)

# shellcheck source=pa28-common.sh source-path=SCRIPTDIR
. "$(dirname "${BASH_SOURCE[0]}")/pa28-common.sh"

# The same for the two managed accounts' home directories only: the operator configuration writes nothing into a user's home.
home_hash() {
  {
    find "/home/$AI" "/home/$ADMIN" -printf '%p %y %m %U %G %s %l\n'
    find "/home/$AI" "/home/$ADMIN" -type f -print0 | xargs -0 -r sha256sum
  } | LC_ALL=C sort | sha256sum | cut -d' ' -f1
}

# playbook CLONE ARGUMENT...: run as root on behalf of the operator admin (the account that would have used sudo).
playbook() {
  local clone=$1
  shift
  (cd "$clone" && SUDO_USER=$ADMIN ANSIBLE_CONFIG="$clone/ansible/ansible.cfg" ANSIBLE_NOCOLOR=1 \
    ansible-playbook -i ansible/inventory/localhost.yml ansible/operator.yml -e "operator_user=$AI" -e "operator_admin_user=$ADMIN" "$@")
}

# fixture NAME MESSAGE SETUP RESTORE: put the machine in a bad state, expect the refusal, put it back.
fixture() {
  local name=$1 message=$2 setup=$3 restore=$4
  "$setup"
  refused "$name" "$CLONE" "$message" -e operator_apply=true -e ssh_second_login_confirmed=true
  "$restore"
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
  # The clone's modes are not the installation's: umask 002 gives 664 and 775 (group-writable), umask 000 gives 666 and 777.
  (umask 002 && git clone -q "$WORK/origin.git" "$CLONE")
  git -C "$CLONE" tag v0.0.0-ci
  git clone -q "$WORK/origin.git" "$UNTAGGED"
  git clone -q "$WORK/origin.git" "$AHEAD"
  git -C "$AHEAD" -c user.name=ci -c user.email=noreply commit -q --allow-empty -m ahead
  git -C "$AHEAD" tag v0.0.1-ci
  (umask 000 && git clone -q "$WORK/origin.git" "$SECOND")
  git -C "$SECOND" tag v0.0.2-ci
  git -C "$CLONE" tag --points-at HEAD | grep -qx v0.0.0-ci
  [[ $(git -C "$CLONE" rev-parse HEAD) == "$(git -C "$source" rev-parse HEAD)" ]] || fail "the clone is not at the head of the pull request"
  ! git -C "$WORK/origin.git" tag --list | grep -q . || fail "the test tag must stay unpushed"
  # The fixture must really be what it claims, or the installation modes below prove nothing.
  [[ -n $(find "$CLONE/scripts/operator" -type f -perm -g+w -print -quit) && -n $(find "$CLONE/scripts/operator" -type d -perm -g+w -print -quit) ]] ||
    fail "the clone is not group-writable (umask 002)"
  [[ -n $(find "$SECOND/scripts/operator" -type f -perm -o+w -print -quit) ]] || fail "the second clone is not writable by others (umask 000)"
  ok "prepared: four clones, a local bare origin at the head, unpushed test tags"
}

refusals() {
  refused "a real run without the apply variable is refused" "$CLONE" "operator_apply=true"
  refused "an untagged tree is refused" "$UNTAGGED" "this clone is not a release" -e operator_apply=true -e ssh_second_login_confirmed=true
  refused "a tag that origin/main does not contain is refused" "$AHEAD" "this clone is not a release" -e operator_apply=true
  refused "a dry run of an untagged tree is refused too" "$UNTAGGED" "this clone is not a release" --check
  # PA-A21: the wrong user. The same tagged clone, run by root for another account than the operator admin, or by nobody in particular.
  local before after rc=0
  before=$(tree_hash)
  (cd "$CLONE" && SUDO_USER=$AI ANSIBLE_CONFIG="$CLONE/ansible/ansible.cfg" ANSIBLE_NOCOLOR=1 \
    ansible-playbook -i ansible/inventory/localhost.yml ansible/operator.yml -e "operator_user=$AI" -e "operator_admin_user=$ADMIN" \
    -e operator_apply=true) >"$WORK/refusal.txt" 2>&1 || rc=$?
  after=$(tree_hash)
  ((rc != 0)) || fail "the operator user ran the operator configuration"
  grep -qF 'run by the operator admin' "$WORK/refusal.txt" || fail "the refusal for the wrong user does not say why"
  [[ $before == "$after" ]] || fail "the wrong user changed the machine"
  rc=0
  (cd "$CLONE" && env -u SUDO_USER ANSIBLE_CONFIG="$CLONE/ansible/ansible.cfg" ANSIBLE_NOCOLOR=1 \
    ansible-playbook -i ansible/inventory/localhost.yml ansible/operator.yml -e "operator_user=$AI" -e "operator_admin_user=$ADMIN" \
    -e operator_apply=true) >"$WORK/refusal.txt" 2>&1 || rc=$?
  ((rc != 0)) || fail "root without sudo from the admin ran the operator configuration"
  grep -qF 'run by the operator admin' "$WORK/refusal.txt" || fail "the refusal for root alone does not say why"
  ok "the wrong user is refused: the operator user, and root without sudo from the operator admin"
  refused "two projects with one name are refused" "$CLONE" "operator_projects needs at least one project" -e operator_apply=true \
    -e '{"operator_projects":[{"name":"a","source":"/x"},{"name":"a","source":"/y"}]}'
  refused "a project whose clone is not at a release tag is refused" "$CLONE" "this clone is not a release" -e operator_apply=true \
    -e "{\"operator_projects\":[{\"name\":\"a\",\"source\":\"$UNTAGGED\"}]}"
  key_rule_fixtures
}

unconfirmed() {
  playbook "$CLONE" -e operator_apply=true --tags ssh_hardening | tee "$WORK/unconfirmed.txt"
  grep -q 'sshd was NOT switched' "$WORK/unconfirmed.txt" || fail "the refusal to switch sshd is not reported"
  [[ ! -e $DROPIN ]] || fail "sshd was switched without the second login"
  [[ $(stat -c '%U:%G %a' "$KEYS/$AI") == 'root:root 644' ]] || fail "the operator user's key is not a root-owned file"
  [[ $(stat -c '%U:%G %a' "$KEYS/$ADMIN") == 'root:root 644' ]] || fail "the admin's key is not a root-owned file"
  grep -q '^ssh-ed25519 ' "$KEYS/$AI" || fail "the operator user's key must carry no forced options (restrict,pty is the AI user's, LC-11)"
  grep -q '^ssh-ed25519 ' "$KEYS/$ADMIN" || fail "the admin's key must carry no forced options"
  ! /usr/sbin/sshd -T | grep -qx "authorizedkeysfile $KEYS/%u" || fail "sshd already reads the root-owned location"
  ok "sshd is not switched without the confirmed second login; the keys are in the root-owned location"
}

first_run() {
  # Symbolic links the operator user could plant: the configuration follows none of them and writes into no home directory.
  ln -s /var/lib/ai-lab "/home/$AI/state"
  ln -s "$KEYS" "/home/$AI/keys"
  ln -s /opt/ai-lab "/home/$ADMIN/tools"
  local before after
  before=$(home_hash)
  playbook "$CLONE" -e operator_apply=true -e ssh_second_login_confirmed=true | tee "$WORK/first-apply.txt"
  after=$(home_hash)
  [[ $before == "$after" ]] || fail "the operator configuration wrote into a user's home directory"
  [[ $(readlink "/home/$AI/state") == /var/lib/ai-lab ]] || fail "a planted link was changed"
  rm -f "/home/$AI/state" "/home/$AI/keys" "/home/$ADMIN/tools"
  grep -q 'operator-check' "$WORK/first-apply.txt" || fail "the run does not end with the operator check"
  ok "first run: home directories unchanged, planted links not followed, the run ends with the operator check"
}

second_run() {
  playbook "$CLONE" -e operator_apply=true -e ssh_second_login_confirmed=true | tee "$WORK/second-apply.txt"
  grep -Eq 'changed=0 +unreachable=0 +failed=0' "$WORK/second-apply.txt" || fail "the second run changed something"
  # The reload and its record are for systemd hosts only (a real reload is PA-A33): a container has no systemd, so none is recorded.
  [[ ! -e $LOADED ]] || fail "a reload of sshd is recorded on a host without systemd"
  ok "second run: zero changes, no reload recorded without systemd"
}

# Two projects (PA-A30, PA-42): this clone and a second clone at its own tag, each with its own installation and output directory.
two_projects() {
  printf '{"operator_projects":[{"name":"%s","source":"%s"},{"name":"%s","source":"%s"}]}\n' "$PROJECT" "$CLONE" "$SECOND_NAME" "$SECOND" \
    >"$WORK/projects.json"
}

second_project() {
  two_projects
  playbook "$CLONE" -e operator_apply=true -e ssh_second_login_confirmed=true -e "@$WORK/projects.json" | tee "$WORK/second-project.txt"
  [[ -f $TOOLS/projects/$PROJECT/RELEASE && -f $TOOLS/projects/$SECOND_NAME/RELEASE ]] || fail "a project is not installed"
  grep -qx 'release_tag=v0.0.0-ci' "$TOOLS/projects/$PROJECT/RELEASE" || fail "the first project is not at its tag"
  grep -qx 'release_tag=v0.0.2-ci' "$TOOLS/projects/$SECOND_NAME/RELEASE" || fail "the second project is not at its own tag"
  [[ $(stat -c '%U %a' "$STATE/output/$PROJECT" "$STATE/output/$SECOND_NAME" | sort -u) == "$AI 700" ]] || fail "an output directory is not the operator user's 0700"
  playbook "$CLONE" -e operator_apply=true -e ssh_second_login_confirmed=true -e "@$WORK/projects.json" | tee "$WORK/second-project-again.txt"
  grep -Eq 'changed=0 +unreachable=0 +failed=0' "$WORK/second-project-again.txt" || fail "a second run with two projects changed something"
  ok "two projects installed, each at its own tag with its own 0700 output directory; a second run changes nothing"
}

dry_run() {
  two_projects
  local before after
  before=$(tree_hash)
  playbook "$CLONE" --check --diff -e ssh_second_login_confirmed=true -e "@$WORK/projects.json" | tee "$WORK/dry-run.txt"
  after=$(tree_hash)
  [[ $before == "$after" ]] || fail "the dry run changed the machine"
  ok "dry run: the tree hash is unchanged"
}

# installed_modes_are_safe CLONE PROJECT: the installation of PROJECT is root-owned with no group or other write bit (symbolic links aside:
# their own mode is meaningless), a file that is executable in CLONE is 0755 in the installation, and every executable installed file is 0755.
installed_modes_are_safe() {
  local clone=$1 root="$TOOLS/projects/$2" bad rel
  bad=$(find "$root" ! -type l \( -perm /022 -o ! -user root -o ! -group root \) -printf '%m %u:%g %P\n' | head -n 3)
  [[ -z $bad ]] || fail "the installation of $2 is not root-owned or is writable by group or others: $bad"
  while IFS= read -r rel; do
    [[ $(stat -c '%a' "$root/scripts/operator/$rel") == 755 ]] || fail "$2: the executable file $rel is not 0755 in the installation"
  done < <(cd "$clone/scripts/operator" && find . -type f -perm -u+x -printf '%P\n')
  [[ -z $(find "$root/scripts/operator" -type f -perm /111 -print0 | xargs -0 -r stat -c '%a' | grep -vx 755 || true) ]] ||
    fail "$2: an installed file is executable but not 0755"
}

verify() {
  local target dir tool effective setting
  local append=": >>\"\$1\"" # the inner shell expands $1
  # The tools: root-owned, and the commands the user types are links to them.
  [[ $(stat -c '%U:%G %a' "$TOOLS/operator-check" "$TOOLS/operator-run" | sort -u) == 'root:root 755' ]] || fail "the operator tools are not root-owned 0755"
  [[ $(stat -c '%U:%G %a' "$TOOLS/operator.conf" "$TOOLS/ssh_hardening_audit.py" | sort -u) == 'root:root 644' ]] || fail "the operator configuration files are not root-owned 0644"
  [[ $(readlink /usr/local/bin/operator-check) == "$TOOLS/operator-check" && $(readlink /usr/local/bin/operator-run) == "$TOOLS/operator-run" ]] ||
    fail "the commands are not links to the root-owned files"
  grep -qx "operator_user=$AI" "$TOOLS/operator.conf" || fail "operator.conf does not name the operator user"
  # What the operator user cannot change (PA-A21): the installed scripts of every project, the tools, the keys, the sshd settings.
  tool=$(find "$TOOLS/projects/$PROJECT/scripts/operator" -maxdepth 1 -type f | LC_ALL=C sort | head -n 1)
  for target in "$tool" "$TOOLS/operator-check" "$TOOLS/operator.conf" "$TOOLS/projects/$PROJECT/RELEASE" "$KEYS/$AI" "$KEYS/$ADMIN" "$DROPIN"; do
    if runuser -u "$AI" -- bash -c "$append" _ "$target" 2>/dev/null; then fail "the operator user can write $target"; fi
    runuser -u "$AI" -- rm -f -- "$target" 2>/dev/null || true
    [[ -e $target ]] || fail "the operator user removed $target"
  done
  for dir in "$TOOLS" "$TOOLS/projects" "$TOOLS/projects/$PROJECT" "$TOOLS/projects/$PROJECT/scripts/operator" "$KEYS" /etc/ssh/sshd_config.d /opt/ai-lab; do
    if runuser -u "$AI" -- test -w "$dir"; then fail "the operator user can write into $dir"; fi
  done
  # The installed scripts of every project are root-owned with no group or other write bit, whatever the umask of its clone was
  # (CLONE: 002, SECOND: 000), and the executable files of the source are 0755 there.
  installed_modes_are_safe "$CLONE" "$PROJECT"
  installed_modes_are_safe "$SECOND" "$SECOND_NAME"
  # Per project: one root-owned installation directory at its tag, one output directory (0700) of the operator user.
  for dir in "$PROJECT" "$SECOND_NAME"; do
    [[ $(stat -c '%U:%G %a' "$TOOLS/projects/$dir") == 'root:root 755' ]] || fail "the installation of $dir is not root-owned"
    [[ $(stat -c '%U %a' "$STATE/output/$dir") == "$AI 700" ]] || fail "the output directory of $dir is not the operator user's 0700"
  done
  # The operator user has no sudo (the account database; a real sudo is PA-A33) and the unattended updates are configured (OC-12).
  ! id -nG "$AI" | tr ' ' '\n' | grep -qxE 'sudo|wheel|admin|docker|lxd|disk' || fail "the operator user is in a root-equivalent group"
  dpkg-query -W -f='${Status}' unattended-upgrades | grep -q 'install ok installed' || fail "unattended-upgrades is not installed"
  [[ $(apt-config dump | grep -c -E '^APT::Periodic::(Update-Package-Lists|Unattended-Upgrade) "1";$') -eq 2 ]] || fail "the apt periodic settings are not 1"
  ! grep -rq 'Automatic-Reboot "true"' /etc/apt/apt.conf.d || fail "a reboot is scheduled by the configuration (the operator admin schedules reboots)"
  # Nothing the lab profile owns is here: no git identity, no managed Claude settings, no lab tools.
  [[ ! -e /etc/gitconfig && ! -e /etc/claude-code && ! -e /opt/ai-lab/lab ]] || fail "the operator machine got something of the lab profile"
  # The sshd settings in force: OC-10, the LC-13 settings for both accounts (`sshd -T` reads the files; the running daemon is PA-A33).
  effective=$(/usr/sbin/sshd -T)
  for setting in 'passwordauthentication no' 'permitrootlogin no' 'pubkeyauthentication yes' 'authenticationmethods publickey' \
    "authorizedkeysfile $KEYS/%u" 'authorizedkeyscommand none' 'trustedusercakeys none' 'authorizedprincipalsfile none' \
    'allowagentforwarding no' 'allowtcpforwarding no' 'x11forwarding no' 'permittunnel no' 'permituserrc no' "allowusers $AI" "allowusers $ADMIN"; do
    grep -qx "$setting" <<<"$effective" || fail "sshd -T does not show: $setting"
  done
  ! grep -Eq '^(kexalgorithms|macs) .*sha1' <<<"$effective" || fail "a SHA-1 key exchange or MAC is still offered"
  ok "installed tools, write attempts as the operator user, two projects, no sudo, unattended updates, and the sshd settings in force"
}

# ---- the operator check as the operator user
# op_run: the installed check as the operator user; its output goes to $WORK/operator-check.txt, its status to $OP_RC.
op_run() {
  OP_RC=0
  runuser -u "$AI" -- "$TOOLS/operator-check" >"$WORK/operator-check.txt" 2>&1 || OP_RC=$?
}
# refusal_is STATUS FILE TEXT MESSAGE: the last run ended with STATUS and its output says TEXT.
refusal_is() {
  [[ $OP_RC -eq $1 ]] || fail "$4 (exit status $OP_RC)"
  grep -q -- "$3" "$2" || fail "$4 (the output does not say: $3)"
}
failing_items() { sed -n -E 's/^FAIL ([A-Z0-9-]+):.*/\1/p' "$WORK/operator-check.txt" | sort | tr '\n' ' '; }
expect_failing() { # expect_failing NAME ITEMS: exactly these items fail (space separated, sorted)
  local got
  got=$(failing_items)
  if [[ $got != "$2 " && -n $2 ]] || [[ -z $2 && -n $got ]]; then
    cat "$WORK/operator-check.txt"
    fail "$1: the operator check fails '${got% }', expected '$2'"
  fi
  if [[ -z $2 && $OP_RC -ne 0 ]] || [[ -n $2 && $OP_RC -ne 1 ]]; then fail "$1: exit status $OP_RC"; fi
  ok "$1"
}

operator_check() {
  local before after homes_before homes_after saved
  [[ $(stat -c '%U:%G %a' "$TOOLS/operator-check") == 'root:root 755' ]] || fail "the installed check is not root-owned 0755"
  before=$(tree_hash)
  homes_before=$(home_hash)
  tree_list >"$WORK/tree-before.txt"

  # 1. The machine that the operator configuration leaves passes every item; OC-8 (no sudo) and OC-12 (unattended updates) are shown.
  op_run
  cat "$WORK/operator-check.txt"
  expect_failing "a machine as the operator configuration leaves it: every item passes" ""
  for item in OC-1 OC-2 OC-6 OC-8 OC-10 OC-11 OC-12 PA-42 PA-13; do
    grep -q "^PASS $item:" "$WORK/operator-check.txt" || fail "$item does not pass on the machine that the operator configuration leaves"
  done
  grep -q '^PASS OC-2: 2 project(s)' "$WORK/operator-check.txt" || fail "OC-2 does not show both projects"
  grep -q '^WARN OC-10: .*inert authorized_keys' "$WORK/operator-check.txt" || fail "the inert authorized_keys file in the operator user's home is not a warning"
  grep -q '^PASS OC-12: .*no systemd here' "$WORK/operator-check.txt" || fail "OC-12 does not say the units are left to PA-A33"
  grep -q '^WARN OC-10: sshd_config.d/60-provider.conf cannot be read by this account' "$WORK/operator-check.txt" ||
    fail "the drop-in that the operator user cannot read is not a warning"
  # A sudo that asks for a password (as for an account with no rule) is a warning, not a failure (OC-8).
  sudo_stub on
  op_run
  sudo_stub off
  grep -q '^WARN OC-8: sudo asks this account for a password' "$WORK/operator-check.txt" || fail "a sudo password prompt is not a warning for OC-8"
  expect_failing "a password prompt of sudo does not fail the operator check" ""
  op_run

  # 2. The refusals: a run from a tree the operator user owns, and from the clone of the admin.
  install -m 0755 -o "$AI" -g "$AI" "$TOOLS/operator-check" "/home/$AI/operator-check"
  install -m 0644 -o "$AI" -g "$AI" "$TOOLS/ssh_hardening_audit.py" "/home/$AI/ssh_hardening_audit.py"
  OP_RC=0
  runuser -u "$AI" -- "/home/$AI/operator-check" --prefix /home/ci-op/prefix >"$WORK/operator-check.txt" 2>&1 || OP_RC=$?
  rm -f "/home/$AI/operator-check" "/home/$AI/ssh_hardening_audit.py"
  refusal_is 2 "$WORK/operator-check.txt" refused "a run from a user-owned tree was not refused"
  OP_RC=0
  runuser -u "$AI" -- python3 -I -B "$CLONE/ansible/roles/operator_tools/files/operator-check" >"$WORK/operator-check.txt" 2>&1 || OP_RC=$?
  refusal_is 2 "$WORK/operator-check.txt" refused "a run from a clone was not refused"
  OP_RC=0
  "$TOOLS/operator-check" >"$WORK/operator-check.txt" 2>&1 || OP_RC=$?
  refusal_is 2 "$WORK/operator-check.txt" 'run this as the operator user' "a run as root was not refused"
  ok "the check runs only from the root-owned installation and only as the operator user"

  # 3. One fixture per failure that a container can show.
  getent group sudo >/dev/null || groupadd sudo
  gpasswd -a "$AI" sudo >/dev/null
  op_run
  gpasswd -d "$AI" sudo >/dev/null
  expect_failing "the operator user in the sudo group fails OC-8" "OC-8"
  mentions "$WORK/operator-check.txt" 'in the group(s) sudo' || fail "OC-8 does not name the group"
  install -d -m 0700 -o "$AI" -g "$AI" "/home/$AI/.claude"
  op_run
  rmdir "/home/$AI/.claude"
  expect_failing "a ~/.claude/ in the operator user's home fails OC-1" "OC-1"
  saved=$(cat "$KEYS/$ADMIN")
  install -m 0644 "$KEYS/$AI" "$KEYS/$ADMIN"
  op_run
  printf '%s\n' "$saved" >"$KEYS/$ADMIN"
  expect_failing "one key on two accounts fails OC-11" "OC-11"
  printf 'ClientAliveInterval 5\n' >/etc/ssh/sshd_config.d/50-stray.conf
  op_run
  rm -f /etc/ssh/sshd_config.d/50-stray.conf
  expect_failing "a stray sshd option fails OC-10" "OC-10"
  cp /etc/apt/apt.conf.d/20auto-upgrades "$WORK/auto-upgrades"
  printf 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "0";\n' >/etc/apt/apt.conf.d/20auto-upgrades
  op_run
  cp "$WORK/auto-upgrades" /etc/apt/apt.conf.d/20auto-upgrades
  expect_failing "unattended updates switched off fail OC-12" "OC-12"
  chmod 0755 "$STATE/output/$SECOND_NAME"
  op_run
  chmod 0700 "$STATE/output/$SECOND_NAME"
  expect_failing "an output directory that is not 0700 fails PA-42" "PA-42"
  # T2 and T3 only inside script processes (PA-A26): in a file, and in the environment of a process that is not a script.
  # shellcheck disable=SC2016 # the token text is assembled by the operator user's shell
  runuser -u "$AI" -- bash -c 'printf "token %s%s\n" "gh""p_" "AAAAAAAAAAAAAAAAAAAAAAAA" >"$1/leak.txt"' _ "$STATE/output/$PROJECT"
  op_run
  rm -f "$STATE/output/$PROJECT/leak.txt"
  expect_failing "a token in a file of an output directory fails PA-13" "PA-13"
  runuser -u "$AI" -- env GH_TOKEN=canary sleep 120 &
  local holder=$!
  sleep 1
  op_run
  kill "$holder" 2>/dev/null || true
  wait "$holder" 2>/dev/null || true
  expect_failing "a token in the environment of a process that is not a script fails PA-13" "PA-13"
  ! grep -q canary "$WORK/operator-check.txt" || fail "the check printed the value of a token variable"

  # 4. The run lock (PA-A30): a second run is refused while a first is in progress, and runs again once the first has ended. The fixture
  #    script is put into each installation by root for this step and taken away again; the operator scripts themselves are not run here.
  for dir in "$PROJECT" "$SECOND_NAME"; do
    # shellcheck disable=SC2016 # the fixture script expands its own variables
    printf '#!/bin/sh\nprintf "%%s\\n" "$OPERATOR_PROJECT" >"$OPERATOR_OUTPUT_DIR/ran.txt"\n' >"$TOOLS/projects/$dir/scripts/operator/lock-fixture"
    chmod 0755 "$TOOLS/projects/$dir/scripts/operator/lock-fixture"
  done
  runuser -u "$AI" -- python3 -I -c 'import fcntl, os, sys, time
fd = os.open(sys.argv[1], os.O_RDWR)
fcntl.flock(fd, fcntl.LOCK_EX)
print("held", flush=True)
time.sleep(120)' "$STATE/run.lock" >"$WORK/lock-holder.txt" &
  holder=$!
  for _ in 1 2 3 4 5 6 7 8 9 10; do grep -q held "$WORK/lock-holder.txt" && break; sleep 0.5; done
  grep -q held "$WORK/lock-holder.txt" || fail "the lock holder did not start"
  OP_RC=0
  runuser -u "$AI" -- "$TOOLS/operator-run" "$PROJECT" scripts/operator/lock-fixture >"$WORK/operator-run.txt" 2>&1 || OP_RC=$?
  kill "$holder" 2>/dev/null || true
  wait "$holder" 2>/dev/null || true
  refusal_is 1 "$WORK/operator-run.txt" 'another operator run is in progress' "a second run was not refused while the first was in progress"
  if ! runuser -u "$AI" -- "$TOOLS/operator-run" "$PROJECT" scripts/operator/lock-fixture >"$WORK/operator-run.txt" 2>&1; then
    cat "$WORK/operator-run.txt"
    fail "the script did not run once the lock was free"
  fi
  [[ $(cat "$STATE/output/$PROJECT/ran.txt") == "$PROJECT" ]] || fail "the script did not run in the output directory of its project"
  if ! runuser -u "$AI" -- "$TOOLS/operator-run" "$SECOND_NAME" scripts/operator/lock-fixture >"$WORK/operator-run.txt" 2>&1; then
    cat "$WORK/operator-run.txt"
    fail "the second project's script did not run"
  fi
  rm -f "$STATE/output/$PROJECT/ran.txt" "$STATE/output/$SECOND_NAME/ran.txt" "$TOOLS/projects/$PROJECT/scripts/operator/lock-fixture" \
    "$TOOLS/projects/$SECOND_NAME/scripts/operator/lock-fixture"
  ok "the run lock refuses a second run while one is in progress and releases after it"

  # 5. Read-only: the tree and the homes are the same after the run and all fixtures; the profile then makes the account sudo-free again.
  op_run
  expect_failing "the machine passes again after the fixtures" ""
  after=$(tree_hash)
  homes_after=$(home_hash)
  if [[ $before != "$after" ]]; then
    tree_list | diff "$WORK/tree-before.txt" - || true
    fail "the operator check or its fixtures left the machine changed"
  fi
  [[ $homes_before == "$homes_after" ]] || fail "the home directories changed"
  ok "operator check: every item passes, eight failures a container can show, the run lock; the tree hash is unchanged"
}

# The profile takes the operator user out of a root-equivalent group again (it "sets the operator user without sudo").
unsudo() {
  getent group sudo >/dev/null || groupadd sudo
  gpasswd -a "$AI" sudo >/dev/null
  playbook "$CLONE" -e operator_apply=true -e ssh_second_login_confirmed=true -e "@$WORK/projects.json" --tags operator_user | tee "$WORK/unsudo.txt"
  ! id -nG "$AI" | tr ' ' '\n' | grep -qx sudo || fail "the profile left the operator user in the sudo group"
  op_run
  expect_failing "after the profile ran, OC-8 passes again" ""
  ok "the operator configuration takes the operator user out of the sudo group"
}

case ${1:-} in
  prepare) prepare "${2:-}" ;;
  refusals) refusals ;;
  unconfirmed) unconfirmed ;;
  first-run) first_run ;;
  second-run) second_run ;;
  second-project) second_project ;;
  dry-run) dry_run ;;
  verify) verify ;;
  operator-check) operator_check ;;
  unsudo) unsudo ;;
  *)
    echo "usage: pa28-operator.sh prepare SOURCE | refusals | unconfirmed | first-run | second-run | second-project | dry-run | verify | operator-check | unsudo" >&2
    exit 2
    ;;
esac
