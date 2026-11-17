# Line-based scan for workflow-policy.sh (POSIX awk; no YAML parser). Run with -v file=PATH.
# It reads only the keys it needs: top-level keys, `uses:`, `run:` (inline and block scalars),
# and a few forbidden words. Findings are "path:line: message"; no file content is printed.
function report(msg) { printf "%s:%d: %s\n", file, FNR, msg }
FNR == 1 { top = ""; inrun = 0; runind = 0 }
{
  line = $0
  sub(/\r$/, "", line)
  match(line, /^ */)
  ind = RLENGTH
  rest = substr(line, ind + 1)
  if (rest == "") next
  if (inrun && ind <= runind) inrun = 0
  if (substr(rest, 1, 1) == "#") next

  if (ind == 0 && match(rest, /^[A-Za-z_][A-Za-z0-9_-]*:/)) {
    top = substr(rest, 1, RLENGTH - 1)
    if (rest ~ /^permissions:[ ]*(write-all|read-all)/) report("top-level permissions too broad (use {} and grant per job)")
  }
  if (top == "on" && rest ~ /^paths(-ignore)?:/) report("paths filter on a trigger (required jobs must always run)")

  if (rest ~ /pull_request_target/) report("pull_request_target is not allowed")
  if (rest ~ /(^|[^A-Za-z_])workflow_run([^A-Za-z_]|$)/) report("workflow_run is not allowed")
  s = rest
  while (match(s, /secrets\.[A-Za-z0-9_]+/)) {
    if (substr(s, RSTART, RLENGTH) != "secrets.GITHUB_TOKEN") report("secret reference (no secrets in Stage 1)")
    s = substr(s, RSTART + RLENGTH)
  }
  if (rest ~ /(curl|wget)[^#]*\|[ ]*(sudo[ ]+)?(ba|da|z|k)?sh([ ]|$)/ ||
      rest ~ /(ba|da)?sh[ ]+-c[ ]+["']?\$\([ ]*(curl|wget)/) report("download piped to a shell")

  if (inrun) {
    if (rest ~ /\$\{\{[^}]*github\.(event\.|head_ref)/) report("untrusted expression inside a run block (pass it through env:)")
    next
  }

  r = rest
  dash = 0
  if (match(r, /^- +/)) { dash = RLENGTH; r = substr(r, RLENGTH + 1) }
  if (r ~ /^uses:/) {
    v = r
    sub(/^uses:[ ]*/, "", v)
    cmt = ""
    if (match(v, /[ ]#/)) { cmt = substr(v, RSTART + 1); v = substr(v, 1, RSTART - 1) }
    gsub(/["' ]/, "", v)
    if (substr(v, 1, 2) == "./") next
    n = split(v, parts, "@")
    sha = (n == 2) ? parts[2] : ""
    if (n != 2 || length(sha) != 40 || sha !~ /^[0-9a-f]+$/) report("action not pinned to a full 40-character commit SHA")
    else if (cmt !~ /^#[ ]*v?[0-9]/) report("pinned action lacks a trailing version comment")
  } else if (r ~ /^run:/) {
    v = r
    sub(/^run:[ ]*/, "", v)
    if (v ~ /^[|>][-+0-9]*([ ]+#.*)?$/) { inrun = 1; runind = ind + dash }
    else if (v ~ /\$\{\{[^}]*github\.(event\.|head_ref)/) report("untrusted expression inside a run block (pass it through env:)")
  }
}
