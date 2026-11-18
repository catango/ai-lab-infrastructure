"""An in-memory GitHub REST API for the github-setup and facts tests: the endpoints the scripts use, with state that changes
on PATCH, PUT, and POST, so that a second apply can be shown to change nothing. It records every request."""
import copy
import io
import json
import re
import urllib.error

OWNER = "exampleowner"
COLLABORATOR = "examplebot"
REPOS = ("ai-lab-infrastructure", "ai-software-template")
CANARY = "CANARY-DESCRIPTION-7731"

DESIRED_SETTINGS = {"has_issues": True, "has_projects": False, "has_wiki": False, "allow_merge_commit": False, "allow_squash_merge": True,
                    "allow_rebase_merge": False, "allow_auto_merge": False, "allow_update_branch": True, "delete_branch_on_merge": True,
                    "squash_merge_commit_title": "PR_TITLE", "squash_merge_commit_message": "PR_BODY"}
DRIFTED_SETTINGS = {"has_issues": True, "has_projects": True, "has_wiki": True, "allow_merge_commit": True, "allow_squash_merge": True,
                    "allow_rebase_merge": True, "allow_auto_merge": True, "allow_update_branch": False, "delete_branch_on_merge": False,
                    "squash_merge_commit_title": "COMMIT_OR_PR_TITLE", "squash_merge_commit_message": "COMMIT_MESSAGES"}
MAIN_RULES = [
    {"type": "deletion"}, {"type": "required_linear_history"}, {"type": "non_fast_forward"},
    {"type": "pull_request", "parameters": {"required_approving_review_count": 1, "dismiss_stale_reviews_on_push": True,
                                             "require_code_owner_review": False, "require_last_push_approval": True,
                                             "required_review_thread_resolution": True, "allowed_merge_methods": ["squash"]}},
]
TAG_RULES = [{"type": "creation"}, {"type": "update", "parameters": {"update_allows_fetch_and_merge": False}}, {"type": "deletion"},
             {"type": "non_fast_forward"}]
ADMIN_BYPASS = [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}]


def good_rulesets():
    return [
        {"id": 11, "name": "main-protection", "target": "branch", "enforcement": "active", "bypass_actors": [],
         "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}}, "rules": copy.deepcopy(MAIN_RULES)},
        {"id": 12, "name": "release-tags", "target": "tag", "enforcement": "active", "bypass_actors": copy.deepcopy(ADMIN_BYPASS),
         "conditions": {"ref_name": {"include": ["refs/tags/v*"], "exclude": []}}, "rules": copy.deepcopy(TAG_RULES)},
    ]


def good_repo(template=False):
    return {
        "settings": dict(DESIRED_SETTINGS), "is_template": template, "description": CANARY,
        "security_and_analysis": {"secret_scanning": {"status": "enabled"}, "secret_scanning_push_protection": {"status": "enabled"}},
        "vulnerability_alerts": True, "automated_security_fixes": True, "private_vulnerability_reporting": True,
        "actions": {"enabled": True, "allowed_actions": "selected", "sha_pinning_required": True},
        "selected": {"github_owned_allowed": True, "verified_allowed": False, "patterns_allowed": []},
        "workflow": {"default_workflow_permissions": "read", "can_approve_pull_request_reviews": False},
        "fork": {"approval_policy": "all_external_contributors"}, "retention": {"days": 30, "maximum_allowed_days": 90},
        "rulesets": good_rulesets(), "collaborators": {COLLABORATOR}, "invitations": set(), "next_id": 100,
    }


def drifted_repo(template=False):
    repo = good_repo(template)
    repo["settings"] = dict(DRIFTED_SETTINGS)
    repo["is_template"] = not template
    repo["security_and_analysis"] = {"secret_scanning": {"status": "disabled"}, "secret_scanning_push_protection": {"status": "disabled"}}
    repo["vulnerability_alerts"] = False
    repo["automated_security_fixes"] = False
    repo["private_vulnerability_reporting"] = False
    repo["actions"] = {"enabled": True, "allowed_actions": "all", "sha_pinning_required": False}
    repo["workflow"] = {"default_workflow_permissions": "write", "can_approve_pull_request_reviews": True}
    repo["fork"] = {"approval_policy": "first_time_contributors"}
    repo["retention"] = {"days": 90, "maximum_allowed_days": 90}
    repo["rulesets"] = []
    repo["collaborators"] = set()
    return repo


class Response:
    def __init__(self, status, payload):
        self.status = status
        self._data = b"" if payload is None else json.dumps(payload).encode()

    def read(self, limit=-1):
        return self._data if limit < 0 else self._data[:limit]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeGitHub:
    """Behaves like urllib's opener: open(request, timeout). Anonymous requests see only what GitHub shows without a token."""

    PUBLIC_GETS = (r"/repos/[^/]+/[^/]+", r"/repos/[^/]+/[^/]+/rulesets", r"/repos/[^/]+/[^/]+/rulesets/\d+",
                   r"/repos/[^/]+/[^/]+/private-vulnerability-reporting", r"/repos/[^/]+/[^/]+/environments")

    def __init__(self, repos=None, deny_admin_reads=False):
        self.repos = repos if repos is not None else {name: good_repo(name == "ai-software-template") for name in REPOS}
        self.requests = []
        self.deny_admin_reads = deny_admin_reads

    def open(self, request, timeout=None):
        method = request.get_method()
        path = request.full_url.split("api.github.com", 1)[1]
        body = json.loads(request.data) if request.data else None
        token = request.get_header("Authorization")
        self.requests.append({"method": method, "path": path, "token": token, "body": body})
        status, payload = self.route(method, path, body, token is not None)
        if status >= 400:
            raise urllib.error.HTTPError(request.full_url, status, "error text that must not be shown", {}, io.BytesIO(b"{}"))
        return Response(status, payload)

    def writes(self):
        return [r for r in self.requests if r["method"] != "GET"]

    def tokens(self):
        return {r["token"] for r in self.requests}

    def route(self, method, path, body, authed):
        match = re.fullmatch(r"/repos/([^/]+)/([^/]+)(/.*)?", path)
        if not match or match.group(1) != OWNER or match.group(2) not in self.repos:
            return 404, None
        repo, rest = self.repos[match.group(2)], match.group(3) or ""
        if method == "GET" and not authed and not any(re.fullmatch(p, path) for p in self.PUBLIC_GETS):
            return 403, None
        if method == "GET" and self.deny_admin_reads and authed and rest.startswith(("/vulnerability-alerts", "/automated-security-fixes", "/actions")):
            return 403, None
        return self.dispatch(method, rest, body, authed, repo)

    def dispatch(self, method, rest, body, authed, repo):
        if rest == "":
            if method == "GET":
                payload = dict(repo["settings"], is_template=repo["is_template"], description=repo["description"], name="x")
                if authed:
                    payload["security_and_analysis"] = copy.deepcopy(repo["security_and_analysis"])
                return 200, payload
            if method == "PATCH":
                for key, value in body.items():
                    if key == "security_and_analysis":
                        for feature, setting in value.items():
                            repo["security_and_analysis"][feature] = dict(setting)
                    elif key == "is_template":
                        repo["is_template"] = value
                    else:
                        repo["settings"][key] = value
                return 200, {}
        flags = {"/vulnerability-alerts": "vulnerability_alerts", "/automated-security-fixes": "automated_security_fixes",
                 "/private-vulnerability-reporting": "private_vulnerability_reporting"}
        if rest in flags:
            key = flags[rest]
            if method == "PUT":
                repo[key] = True
                return 204, None
            if rest == "/vulnerability-alerts":
                return (204, None) if repo[key] else (404, None)
            if rest == "/automated-security-fixes":
                return (200, {"enabled": True, "paused": False}) if repo[key] else (404, None)
            return 200, {"enabled": repo[key]}
        blocks = {"/actions/permissions": "actions", "/actions/permissions/selected-actions": "selected", "/actions/permissions/workflow": "workflow",
                  "/actions/permissions/fork-pr-contributor-approval": "fork", "/actions/permissions/artifact-and-log-retention": "retention"}
        if rest in blocks:
            key = blocks[rest]
            if method == "PUT":
                repo[key].update(body)
                return 204, None
            return 200, copy.deepcopy(repo[key])
        if rest == "/rulesets":
            if method == "GET":
                return 200, [{k: r[k] for k in ("id", "name", "target", "enforcement")} for r in repo["rulesets"]]
            if method == "POST":
                repo["next_id"] += 1
                created = dict(copy.deepcopy(body), id=repo["next_id"])
                repo["rulesets"].append(created)
                return 201, created
        found = re.fullmatch(r"/rulesets/(\d+)", rest)
        if found:
            current = next((r for r in repo["rulesets"] if r["id"] == int(found.group(1))), None)
            if current is None:
                return 404, None
            if method == "GET":
                return 200, copy.deepcopy(current)
            if method == "PUT":
                current.update(copy.deepcopy(body))
                return 200, copy.deepcopy(current)
        if rest == "/environments" and method == "GET":
            return 200, {"total_count": 0, "environments": []}
        found = re.fullmatch(r"/collaborators/([^/]+)", rest)
        if found:
            login = found.group(1)
            if method == "GET":
                return (204, None) if login in repo["collaborators"] else (404, None)
            if method == "PUT":
                if login in repo["collaborators"]:
                    return 204, None
                repo["invitations"].add(login)
                return 201, {"id": 1}
        if rest == "/collaborators" and method == "GET":
            return 200, [{"login": "x"} for _ in repo["collaborators"]]
        if rest.startswith("/invitations") and method == "GET":
            return 200, [{"invitee": {"login": login}} for login in sorted(repo["invitations"])]
        return 404, None
