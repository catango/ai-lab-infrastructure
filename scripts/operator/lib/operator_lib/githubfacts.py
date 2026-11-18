"""facts, GitHub scope (CR-18 design section 5.1, R6): repository configuration as yes/no and counts, read with GET calls only.

The client is read-only, so a bug cannot write. Without a token only what GitHub shows for a public repository is known; a
value that needs a token is reported as unknown. With T3 (Administration, Environments, and Metadata read) the rest is known.
Nothing from the repository (names, descriptions, logins) is printed except the repository name the caller passed in."""
from pr_contract.errors import ApiError, NotFound

from . import github

UNKNOWN = "unknown"
MAX_RULESETS = 20


def get_paths(owner, repo):
    base = f"/repos/{owner}/{repo}"
    return [base, f"{base}/rulesets", f"{base}/rulesets/<id>", f"{base}/private-vulnerability-reporting", f"{base}/environments",
            f"{base}/vulnerability-alerts", f"{base}/automated-security-fixes", f"{base}/actions/permissions",
            f"{base}/actions/permissions/workflow", f"{base}/collaborators"]


def _get(client, path):
    try:
        return "ok", client.get(path)
    except NotFound:
        return "missing", None
    except ApiError:
        return "denied", None


def yn(value):
    return UNKNOWN if value is None or value == UNKNOWN else ("yes" if value else "no")


def _flag(data, key):
    return yn(data.get(key)) if isinstance(data, dict) and key in data else UNKNOWN


def _strong_branch(ruleset):
    types = {r.get("type") for r in ruleset.get("rules") or [] if isinstance(r, dict)}
    include = ((ruleset.get("conditions") or {}).get("ref_name") or {}).get("include") or []
    return (ruleset.get("target") == "branch" and ruleset.get("enforcement") == "active" and "~DEFAULT_BRANCH" in include
            and {"deletion", "non_fast_forward", "pull_request"} <= types)


def _strong_tag(ruleset):
    """The R3 tag ruleset: active, covers v* tags, and restricts creation, update, and deletion."""
    types = {r.get("type") for r in ruleset.get("rules") or [] if isinstance(r, dict)}
    include = ((ruleset.get("conditions") or {}).get("ref_name") or {}).get("include") or []
    return (ruleset.get("target") == "tag" and ruleset.get("enforcement") == "active"
            and any(isinstance(p, str) and p.startswith("refs/tags/v") for p in include) and {"creation", "update", "deletion"} <= types)


def collect(client, owner, repo):
    base = f"/repos/{owner}/{repo}"
    kind, data = _get(client, base)
    if kind != "ok" or not isinstance(data, dict):
        return {"reachable": "no"}
    facts = {"reachable": "yes", "merge_commits_allowed": _flag(data, "allow_merge_commit"), "squash_allowed": _flag(data, "allow_squash_merge"),
             "rebase_allowed": _flag(data, "allow_rebase_merge"), "auto_merge_allowed": _flag(data, "allow_auto_merge"),
             "wiki_enabled": _flag(data, "has_wiki"), "issues_enabled": _flag(data, "has_issues"), "projects_enabled": _flag(data, "has_projects"),
             "is_template": _flag(data, "is_template")}
    block = data.get("security_and_analysis")
    for feature in ("secret_scanning", "secret_scanning_push_protection"):
        entry = block.get(feature) if isinstance(block, dict) else None
        facts[feature] = yn(entry.get("status") == "enabled") if isinstance(entry, dict) and "status" in entry else UNKNOWN
    kind, listing = _get(client, f"{base}/rulesets?per_page=100&includes_parents=false")
    if kind == "ok" and isinstance(listing, list):
        facts["rulesets"] = len(listing)
        branch = tag = False
        for item in listing[:MAX_RULESETS]:
            if isinstance(item, dict) and isinstance(item.get("id"), int):
                kind, detail = _get(client, f"{base}/rulesets/{item['id']}")
                if kind == "ok" and isinstance(detail, dict):
                    branch = branch or _strong_branch(detail)
                    tag = tag or _strong_tag(detail)
        facts["branch_ruleset_active"], facts["tag_ruleset_active"] = yn(branch), yn(tag)
    else:
        facts.update({"rulesets": UNKNOWN, "branch_ruleset_active": UNKNOWN, "tag_ruleset_active": UNKNOWN})
    kind, body = _get(client, f"{base}/private-vulnerability-reporting")
    facts["private_vulnerability_reporting"] = _flag(body, "enabled") if kind == "ok" else UNKNOWN
    kind, body = _get(client, f"{base}/vulnerability-alerts")
    facts["vulnerability_alerts"] = "yes" if kind == "ok" else ("no" if kind == "missing" and block is not None else UNKNOWN)
    kind, body = _get(client, f"{base}/automated-security-fixes")
    facts["dependabot_security_updates"] = _flag(body, "enabled") if kind == "ok" else ("no" if kind == "missing" and block is not None else UNKNOWN)
    kind, body = _get(client, f"{base}/actions/permissions")
    facts["actions_selected_only"] = yn(body.get("allowed_actions") == "selected") if kind == "ok" and isinstance(body, dict) else UNKNOWN
    facts["sha_pinning_required"] = _flag(body, "sha_pinning_required") if kind == "ok" else UNKNOWN
    kind, body = _get(client, f"{base}/actions/permissions/workflow")
    facts["workflow_permissions_read_only"] = yn(body.get("default_workflow_permissions") == "read") if kind == "ok" and isinstance(body, dict) else UNKNOWN
    kind, body = _get(client, f"{base}/environments")
    facts["environments"] = body.get("total_count") if kind == "ok" and isinstance(body, dict) and isinstance(body.get("total_count"), int) else UNKNOWN
    kind, body = _get(client, f"{base}/collaborators")
    facts["collaborators"] = len(body) if kind == "ok" and isinstance(body, list) else UNKNOWN
    return facts


def client_for(token, opener=None):
    return github.make_client(token, read_only=True, opener=opener)
