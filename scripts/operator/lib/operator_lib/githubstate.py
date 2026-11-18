"""github-setup (CR-18 design section 5.2): the desired state of a repository, how to read the current state with GET calls, how to
compare them, and which write calls bring them together. Only values the desired-state file names are compared or written; other
settings and rule types are never touched. Output goes through show(), which prints yes/no, counts, and a fixed vocabulary."""
import re
import tomllib
from dataclasses import dataclass

import operator_lib  # noqa: F401  (puts scripts/ on sys.path)
from pr_contract.errors import ApiError, NotFound

from . import steps

UNKNOWN = "unknown"
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}")
_PARAM = re.compile(r"[a-z][a-z0-9_]{0,60}")
ENUMS = frozenset({
    "PR_TITLE", "PR_BODY", "COMMIT_OR_PR_TITLE", "COMMIT_MESSAGES", "BLANK", "enabled", "disabled", "all", "local_only", "selected",
    "read", "write", "all_external_contributors", "first_time_contributors", "first_time_contributors_new_to_github",
    "active", "evaluate", "branch", "tag", "missing", "present", "yes", "no", "pending", "unknown",
})
SETTINGS = {
    "has_issues": bool, "has_projects": bool, "has_wiki": bool, "allow_merge_commit": bool, "allow_squash_merge": bool,
    "allow_rebase_merge": bool, "allow_auto_merge": bool, "allow_update_branch": bool, "delete_branch_on_merge": bool,
    "squash_merge_commit_title": str, "squash_merge_commit_message": str,
}
SECURITY = {"secret_scanning": str, "secret_scanning_push_protection": str, "vulnerability_alerts": bool,
            "automated_security_fixes": bool, "private_vulnerability_reporting": bool}
ACTIONS = {"enabled": bool, "allowed_actions": str, "sha_pinning_required": bool, "github_owned_allowed": bool, "verified_allowed": bool,
           "patterns_allowed": list, "default_workflow_permissions": str, "can_approve_pull_request_reviews": bool,
           "approval_policy": str, "artifact_log_retention_days": int}
ACTIONS_GROUPS = {
    "permissions": ("enabled", "allowed_actions", "sha_pinning_required"),
    "selected-actions": ("github_owned_allowed", "verified_allowed", "patterns_allowed"),
    "workflow": ("default_workflow_permissions", "can_approve_pull_request_reviews"),
    "fork-pr-contributor-approval": ("approval_policy",),
    "artifact-and-log-retention": ("artifact_log_retention_days",),
}


class StateError(Exception):
    """The desired-state file is invalid. The message names the problem, never a value."""


@dataclass(frozen=True)
class Diff:
    key: str
    current: object
    wanted: object


def _table(raw, name, spec):
    section = raw.get(name, {})
    if not isinstance(section, dict) or any(key not in spec for key in section):
        raise StateError(f"[{name}] has an unknown key or is not a table")
    for key, value in section.items():
        kind = spec[key]
        if isinstance(value, bool) != (kind is bool) or not isinstance(value, kind) or (kind is list and not all(isinstance(i, str) for i in value)):
            raise StateError(f"[{name}] {key} has the wrong type")
    return section


def _ruleset(entry):
    if not isinstance(entry, dict) or set(entry) - {"name", "target", "enforcement", "include", "exclude", "bypass_actors", "rules"}:
        raise StateError("a ruleset has an unknown key")
    if not (isinstance(entry.get("name"), str) and NAME.fullmatch(entry["name"])) or entry.get("target") not in ("branch", "tag") \
            or entry.get("enforcement") not in ("active", "evaluate", "disabled"):
        raise StateError("a ruleset needs a name, a target, and an enforcement")
    for key in ("include", "exclude"):
        if not isinstance(entry.get(key), list) or not all(isinstance(i, str) and 0 < len(i) < 100 for i in entry[key]):
            raise StateError(f"a ruleset needs {key} as a list of patterns")
    for actor in entry.get("bypass_actors", []):
        if not (isinstance(actor, dict) and set(actor) == {"actor_type", "actor_id", "bypass_mode"} and isinstance(actor["actor_type"], str)
                and isinstance(actor["actor_id"], int) and not isinstance(actor["actor_id"], bool) and actor["bypass_mode"] in ("always", "pull_request", "exempt")):
            raise StateError("a bypass actor needs actor_type, actor_id, and bypass_mode")
    for rule in entry.get("rules", []):
        if not isinstance(rule, dict) or not isinstance(rule.get("type"), str) or not _PARAM.fullmatch(rule["type"]):
            raise StateError("a rule needs a type")
        for key, value in rule.items():
            if key != "type" and not (_PARAM.fullmatch(key) and (isinstance(value, (bool, int, str)) or (isinstance(value, list) and all(isinstance(i, str) for i in value)))):
                raise StateError("a rule parameter has an invalid name or value")
    return {"name": entry["name"], "target": entry["target"], "enforcement": entry["enforcement"], "include": list(entry["include"]),
            "exclude": list(entry["exclude"]), "bypass_actors": [dict(a) for a in entry.get("bypass_actors", [])],
            "rules": [{"type": r["type"], "parameters": {k: v for k, v in r.items() if k != "type"}} for r in entry.get("rules", [])]}


def load_desired(path):
    try:
        with open(path, "rb") as handle:
            raw = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        raise StateError("the desired-state file could not be read") from None
    allowed = {"schema_version", "repositories", "settings", "security", "actions", "collaborator", "rulesets", "environments"}
    if raw.get("schema_version") != 1 or set(raw) - allowed:
        raise StateError("unknown schema_version or top-level key")
    repositories = raw.get("repositories")
    if not isinstance(repositories, dict) or not repositories:
        raise StateError("no repositories")
    for name, entry in repositories.items():
        if not NAME.fullmatch(name) or not (isinstance(entry, dict) and set(entry) <= {"is_template"} and isinstance(entry.get("is_template", False), bool)):
            raise StateError("invalid repository entry")
    security = _table(raw, "security", SECURITY)
    for key in ("vulnerability_alerts", "automated_security_fixes", "private_vulnerability_reporting"):
        if security.get(key) is False:
            raise StateError(f"{key} can only be enabled by github-setup")
    for key in ("secret_scanning", "secret_scanning_push_protection"):
        if security.get(key) not in (None, "enabled", "disabled"):
            raise StateError(f"{key} must be enabled or disabled")
    collaborator = raw.get("collaborator", {})
    if not isinstance(collaborator, dict) or set(collaborator) - {"invite"} or not isinstance(collaborator.get("invite", False), bool):
        raise StateError("invalid [collaborator]")
    environments = raw.get("environments", [])
    if not isinstance(environments, list) or not all(isinstance(e, dict) and set(e) == {"name", "deferred"} and e["deferred"] is True
                                                     and isinstance(e["name"], str) and NAME.fullmatch(e["name"]) for e in environments):
        raise StateError("environments must be declared as deferred")
    rulesets = [_ruleset(r) for r in raw.get("rulesets", [])]
    if len({r["name"] for r in rulesets}) != len(rulesets):
        raise StateError("duplicate ruleset name")
    return {"repositories": {n: dict(e) for n, e in repositories.items()}, "settings": _table(raw, "settings", SETTINGS), "security": security,
            "actions": _table(raw, "actions", ACTIONS), "collaborator": dict(collaborator), "rulesets": rulesets,
            "environments": [e["name"] for e in environments]}


def show(value):
    """A value as the approver sees it: yes/no, a number, a count of items, or a word from the fixed vocabulary."""
    if value is None:
        return "not set"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        return str(value) if 0 <= value <= 10**6 else "<redacted>"
    if isinstance(value, list):
        return f"{len(value)} items"
    if isinstance(value, str) and (value in ENUMS):
        return value
    return "<redacted>"


def _read(client, path):
    """(state, data): ok with the data (None for an empty reply), missing for 404, denied for any other refusal."""
    try:
        return "ok", client.get(path)
    except NotFound:
        return "missing", None
    except ApiError:
        return "denied", None


@dataclass
class RepoState:
    reachable: bool
    values: dict
    rulesets: dict
    collaborator: str


def _status(data, feature):
    block = data.get("security_and_analysis") if isinstance(data, dict) else None
    entry = block.get(feature) if isinstance(block, dict) else None
    return entry.get("status") if isinstance(entry, dict) and isinstance(entry.get("status"), str) else UNKNOWN


def read_state(client, owner, repo, desired, collaborator_login):
    base = f"/repos/{owner}/{repo}"
    kind, data = _read(client, base)
    if kind != "ok" or not isinstance(data, dict):
        return RepoState(False, {}, {}, UNKNOWN)
    values = {f"settings.{key}": data.get(key) for key in desired["settings"]}
    values["is_template"] = data.get("is_template")
    for feature in ("secret_scanning", "secret_scanning_push_protection"):
        if feature in desired["security"]:
            values[f"security.{feature}"] = _status(data, feature)
    for flag, path in (("vulnerability_alerts", "vulnerability-alerts"), ("automated_security_fixes", "automated-security-fixes"),
                       ("private_vulnerability_reporting", "private-vulnerability-reporting")):
        if flag in desired["security"]:
            kind, body = _read(client, f"{base}/{path}")
            if kind == "ok":
                values[f"security.{flag}"] = body.get("enabled") if isinstance(body, dict) and "enabled" in body else True
            else:
                values[f"security.{flag}"] = False if kind == "missing" and flag != "private_vulnerability_reporting" else UNKNOWN
    actions = desired["actions"]
    for group, keys in ACTIONS_GROUPS.items():
        wanted_keys = [k for k in keys if k in actions]
        if not wanted_keys:
            continue
        if group == "selected-actions" and values.get("actions.allowed_actions") not in (UNKNOWN, "selected"):
            for key in wanted_keys:
                values[f"actions.{key}"] = None  # not in use until allowed_actions is selected
            continue
        kind, body = _read(client, f"{base}/actions/permissions" + ("" if group == "permissions" else f"/{group}"))
        for key in wanted_keys:
            if kind != "ok" or not isinstance(body, dict):
                values[f"actions.{key}"] = UNKNOWN
            elif key == "artifact_log_retention_days":
                values[f"actions.{key}"] = body.get("days")
            else:
                values[f"actions.{key}"] = body.get(key)
    rulesets = {}
    if desired["rulesets"]:
        kind, listing = _read(client, f"{base}/rulesets?per_page=100&includes_parents=false")
        if kind != "ok" or not isinstance(listing, list):
            rulesets = None
        else:
            for item in listing:
                if isinstance(item, dict) and item.get("name") in {r["name"] for r in desired["rulesets"]} and isinstance(item.get("id"), int):
                    kind, detail = _read(client, f"{base}/rulesets/{item['id']}")
                    rulesets[item["name"]] = detail if kind == "ok" and isinstance(detail, dict) else None
    return RepoState(True, values, rulesets, _collaborator(client, base, collaborator_login) if desired["collaborator"].get("invite") else "yes")


def _collaborator(client, base, login):
    kind, _ = _read(client, f"{base}/collaborators/{login}")
    if kind == "ok":
        return "yes"
    if kind == "denied":
        return UNKNOWN
    kind, invitations = _read(client, f"{base}/invitations")
    if kind != "ok" or not isinstance(invitations, list):
        return UNKNOWN
    pending = any(isinstance(i, dict) and isinstance(i.get("invitee"), dict) and i["invitee"].get("login") == login for i in invitations)
    return "pending" if pending else "no"


def _norm(value):
    return sorted(value) if isinstance(value, list) else value


def _ruleset_diffs(wanted, existing):
    name = wanted["name"]
    if existing is None:
        return [Diff(f"ruleset.{name}", "missing", "present")]
    found = []
    conditions = existing.get("conditions") or {}
    ref_name = conditions.get("ref_name") or {}
    pairs = [("target", existing.get("target"), wanted["target"]), ("enforcement", existing.get("enforcement"), wanted["enforcement"]),
             ("include", ref_name.get("include"), wanted["include"]), ("exclude", ref_name.get("exclude"), wanted["exclude"])]
    for field, current, want in pairs:
        if _norm(current) != _norm(want):
            found.append(Diff(f"ruleset.{name}.{field}", current, want))
    actors = lambda items: sorted((a.get("actor_type"), a.get("actor_id"), a.get("bypass_mode")) for a in (items or []) if isinstance(a, dict))  # noqa: E731
    if actors(existing.get("bypass_actors")) != actors(wanted["bypass_actors"]):
        found.append(Diff(f"ruleset.{name}.bypass_actors", len(existing.get("bypass_actors") or []), len(wanted["bypass_actors"])))
    have = {r.get("type"): r.get("parameters") or {} for r in existing.get("rules") or [] if isinstance(r, dict)}
    for rule in wanted["rules"]:
        if rule["type"] not in have:
            found.append(Diff(f"ruleset.{name}.rules.{rule['type']}", "missing", "present"))
            continue
        for key, want in rule["parameters"].items():
            if _norm(have[rule["type"]].get(key)) != _norm(want):
                found.append(Diff(f"ruleset.{name}.rules.{rule['type']}.{key}", have[rule["type"]].get(key), want))
    return found


def compute_diffs(desired, repo_name, state):
    """(diffs, unknown count). A current value that could not be read is counted as unknown and never changed."""
    diffs, unknown = [], 0
    wanted = {f"settings.{k}": v for k, v in desired["settings"].items()}
    wanted.update({f"security.{k}": v for k, v in desired["security"].items()})
    wanted.update({f"actions.{k}": v for k, v in desired["actions"].items()})
    if "is_template" in desired["repositories"][repo_name]:
        wanted["is_template"] = desired["repositories"][repo_name]["is_template"]
    for key, want in wanted.items():
        current = state.values.get(key, UNKNOWN)
        if current == UNKNOWN:
            unknown += 1
        elif _norm(current) != _norm(want):
            diffs.append(Diff(key, current, want))
    if state.rulesets is None:
        unknown += len(desired["rulesets"])
    else:
        for ruleset in desired["rulesets"]:
            existing = state.rulesets.get(ruleset["name"], "absent")
            if existing is None:
                unknown += 1
            else:
                diffs.extend(_ruleset_diffs(ruleset, None if existing == "absent" else existing))
    if desired["collaborator"].get("invite"):
        if state.collaborator == UNKNOWN:
            unknown += 1
        elif state.collaborator == "no":
            diffs.append(Diff("collaborator", "no", "yes"))
    return diffs, unknown


def _rule_body(rule):
    return {"type": rule["type"], **({"parameters": rule["parameters"]} if rule["parameters"] else {})}


def _ruleset_body(wanted, existing):
    managed = {r["type"] for r in wanted["rules"]}
    kept = [r for r in (existing or {}).get("rules", []) if isinstance(r, dict) and r.get("type") not in managed]
    return {"name": wanted["name"], "target": wanted["target"], "enforcement": wanted["enforcement"],
            "bypass_actors": wanted["bypass_actors"], "conditions": {"ref_name": {"include": wanted["include"], "exclude": wanted["exclude"]}},
            "rules": [_rule_body(r) for r in wanted["rules"]] + kept}


def build_steps(client, owner, repo_name, desired, diffs, state, collaborator_login):
    """The write calls for the differences, as steps: a PATCH, some PUTs, ruleset calls, an invitation."""
    base = f"/repos/{owner}/{repo_name}"
    keys = {d.key for d in diffs}
    plan = []

    def add(name, method, path, body=None, destructive=False):
        plan.append(steps.Step(name, lambda: True, lambda: client.request(method, path, body), destructive))

    patch = {k.split(".", 1)[1]: desired["settings"][k.split(".", 1)[1]] for k in keys if k.startswith("settings.")}
    if "is_template" in keys:
        patch["is_template"] = desired["repositories"][repo_name]["is_template"]
    sec = {k.split(".", 1)[1]: {"status": desired["security"][k.split(".", 1)[1]]} for k in keys
           if k in ("security.secret_scanning", "security.secret_scanning_push_protection")}
    if sec:
        patch["security_and_analysis"] = sec
    if patch:
        add(f"PATCH settings of {repo_name} ({len(patch)} fields)", "PATCH", base, patch)
    for flag, path in (("vulnerability_alerts", "vulnerability-alerts"), ("automated_security_fixes", "automated-security-fixes"),
                       ("private_vulnerability_reporting", "private-vulnerability-reporting")):
        if f"security.{flag}" in keys:
            add(f"PUT {path} of {repo_name}", "PUT", f"{base}/{path}")
    for group, group_keys in ACTIONS_GROUPS.items():
        if any(f"actions.{k}" in keys for k in group_keys):
            if group == "artifact-and-log-retention":
                body = {"days": desired["actions"]["artifact_log_retention_days"]}
            else:
                body = {k: desired["actions"][k] for k in group_keys if k in desired["actions"]}
            add(f"PUT actions {group} of {repo_name}", "PUT", f"{base}/actions/permissions" + ("" if group == "permissions" else f"/{group}"), body)
    for ruleset in desired["rulesets"]:
        if not any(k == f"ruleset.{ruleset['name']}" or k.startswith(f"ruleset.{ruleset['name']}.") for k in keys):
            continue
        existing = (state.rulesets or {}).get(ruleset["name"])
        if existing is None:
            add(f"create ruleset {ruleset['name']} in {repo_name}", "POST", f"{base}/rulesets", _ruleset_body(ruleset, None))
        else:
            add(f"update ruleset {ruleset['name']} in {repo_name}", "PUT", f"{base}/rulesets/{existing['id']}", _ruleset_body(ruleset, existing), destructive=True)
    if "collaborator" in keys:
        add(f"invite the collaborator to {repo_name}", "PUT", f"{base}/collaborators/{collaborator_login}")
    return plan
