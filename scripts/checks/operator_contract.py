"""Contract rules for operator scripts (CR-18 design section 4; acceptance S-6 and S-11). Used by operator-contract.sh.

Reads tracked paths on stdin and prints findings as path:line: message. Rules, for files under scripts/operator/:
no eval, exec, os.system, os.popen, os.exec*, os.spawn*, shell=True, or pty; subprocess only in the process module;
no sudo (CR-57 O-8, O-9: the sudo-based setup and facts --privileged are gone); no Terraform; no OCI call with a verb other than list, get, or inspect; no download
piped to a shell. Static checks cannot see dynamic values, so operator_lib.process enforces the same at run time.

Endpoints (CR-57 PA-22, PA-A15, design I-9 and I-10). When the policy is enforced, every endpoint is a literal and its host is listed
in `operator_endpoints` of config/project.yaml. operator-contract.sh reads that file from the BASE commit (GATE_BASE_REF, SC-20) and
passes it as --config FILE. The rules: a URL literal whose host is not listed fails; a URL whose host is built at run time (an f-string,
`+`, `%`, or `.format` after a scheme) fails; `HttpClient(...)` takes a literal or a module constant that is a literal; and the network
modules (urllib.request, http.client, socket, and the like) are imported only in operator_lib/httpclient.py, so one client is the one
place an endpoint is used. The policy is enforced when `operator_paths` is not empty, and then a missing `operator_endpoints` fails
closed (a missing or empty `operator_paths` enforces nothing here; PC-8 judges that key). Without a configuration file nothing is enforced (a repository without operator paths: the generic default). The hosts that
fail are never printed.
"""
import ast
import re
import sys

PREFIX = "scripts/operator/"
CONFIG_PATH = "config/project.yaml"
HTTP_CLIENT = "scripts/operator/lib/operator_lib/httpclient.py"
NETWORK_MODULES = frozenset({"urllib.request", "http.client", "socket", "ssl", "ftplib", "smtplib", "telnetlib", "poplib", "imaplib",
                             "xmlrpc.client", "requests", "httpx", "aiohttp", "paramiko"})
# hostfacts.py only reads the name of the group "sudo" from /etc/group; it starts no command (operator_lib.process has no sudo).
SUDO_ALLOWED = frozenset({"scripts/operator/lib/operator_lib/hostfacts.py"})
SUBPROCESS_ALLOWED = frozenset({"scripts/operator/lib/operator_lib/process.py"})
READ_VERBS = frozenset({"list", "get", "inspect"})
_OS_BANNED = frozenset({"system", "popen", "posix_spawn", "posix_spawnp"})
_OS_PREFIXES = ("exec", "spawn")
_SUDO = re.compile(r"(?<![\w-])sudo(?![\w-])")
_TERRAFORM = re.compile(r"(?<![\w-])(?:terraform|tofu)(?![\w-])")
_EVAL = re.compile(r"(?<![\w-])eval(?![\w-])")
_PIPE_TO_SHELL = re.compile(r"\b(?:curl|wget)\b[^|\n]*\|\s*(?:sudo\s+)?(?:ba|z|da|k)?sh\b")
_OCI = re.compile(r"(?<![\w./-])oci\s+([^\n|;&]*)")
_URL = re.compile(r"(?i)(?<![\w+.-])(?:https?|ssh|git|ftp|wss?)://([^/\s\"'<>@?#\\)\0]*)")
_HOLE = "\0"


def _is_python(path, text):
    first = text.split("\n", 1)[0]
    return path.endswith(".py") or (first.startswith("#!") and "python" in first)


def _is_shell(path, text):
    first = text.split("\n", 1)[0]
    return path.endswith((".sh", ".bash")) or (first.startswith("#!") and re.search(r"[/ ](?:ba|da|z|k)?sh\b", first) is not None)


def _os_banned(name):
    return name in _OS_BANNED or name.startswith(_OS_PREFIXES)


def _docstrings(tree):
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                ids.add(id(first.value))
    return ids


def _oci_list_finding(node):
    items = node.elts
    if not items or not (isinstance(items[0], ast.Constant) and items[0].value == "oci"):
        return None
    tokens = []
    for item in items[1:]:
        if not (isinstance(item, ast.Constant) and isinstance(item.value, str)):
            return None  # a dynamic element: the run-time check decides
        if item.value.startswith("-"):
            break
        tokens.append(item.value)
    if tokens and tokens[-1] not in READ_VERBS:
        return "OCI call with a verb other than list, get, or inspect"
    return None


def _hole_text(node):
    """The text of a string expression with a NUL where a value is built at run time, or None when it is not a string expression."""
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else None
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) and isinstance(v.value, str) else _HOLE for v in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _hole_text(node.left), _hole_text(node.right)
        if left is None and right is None:
            return None
        return (_HOLE if left is None else left) + (_HOLE if right is None else right)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        left = _hole_text(node.left)
        return None if left is None else re.sub(r"%[-#0 +]*[0-9]*(?:\.[0-9]+)?[sdrif]", _HOLE, left)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format":
        base = _hole_text(node.func.value)
        return None if base is None else re.sub(r"\{[^{}]*\}", _HOLE, base)
    return None


def _endpoint_findings(text, allowed):
    """Messages for the URLs of one string expression (a NUL marks a run-time part)."""
    found = []
    for match in _URL.finditer(text):
        host = match.group(1).split(":")[0].lower()
        if text[match.end():match.end() + 1] == _HOLE or (not host and match.end() < len(text)):
            found.append("an endpoint host is built at run time; endpoints are literals (PA-22)")
        elif host and host not in allowed:
            found.append("an endpoint host is not listed in operator_endpoints (PA-22)")
    return found


def _module_constants(tree):
    names = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            names[node.targets[0].id] = node.value.value
    return names


def scan_python_endpoints(path, tree, docs, allowed):
    """Endpoint findings of one Python file (see the module docstring)."""
    found = []
    constants = _module_constants(tree)
    seen = set()
    for node in ast.walk(tree):
        line = getattr(node, "lineno", 1)
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            modules = [node.module or ""] + [f"{node.module}.{alias.name}" for alias in node.names]
        else:
            modules = []
        if path != HTTP_CLIENT and any(m in NETWORK_MODULES or m.split(".")[0] in {"socket", "requests", "httpx", "aiohttp", "paramiko"}
                                       for m in modules):
            found.append((line, "network modules are used only in operator_lib/httpclient.py (PA-22)"))
        if isinstance(node, (ast.JoinedStr, ast.BinOp, ast.Call, ast.Constant)) and id(node) not in docs:
            text = _hole_text(node)
            if text is not None and id(node) not in seen:
                for child in ast.walk(node):
                    seen.add(id(child))
                found.extend((line, message) for message in _endpoint_findings(text, allowed))
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            if name == "HttpClient":
                argument = node.args[0] if node.args else next((k.value for k in node.keywords if k.arg == "base"), None)
                literal = isinstance(argument, ast.Constant) and isinstance(argument.value, str)
                constant = isinstance(argument, ast.Name) and argument.id in constants
                if path != HTTP_CLIENT and not (literal or constant):
                    found.append((line, "HttpClient takes a literal or a module constant that is a literal: endpoints are literals (PA-22)"))
    return found


def scan_python(path, text, allowed=None):
    try:
        tree = ast.parse(text)
    except SyntaxError as error:
        return [(error.lineno or 1, "syntax error: the file cannot be checked")]
    found = []
    docs = _docstrings(tree)
    for node in ast.walk(tree):
        line = getattr(node, "lineno", 1)
        if isinstance(node, ast.Call):
            func = node.func
            if (isinstance(func, ast.Name) and func.id in ("eval", "exec")) or (isinstance(func, ast.Attribute) and func.attr in ("eval", "exec")):
                found.append((line, "eval or exec is not allowed"))
            if isinstance(func, ast.Name) and func.id == "__import__" and node.args and isinstance(node.args[0], ast.Constant) \
                    and node.args[0].value in ("subprocess", "pty") and not (node.args[0].value == "subprocess" and path in SUBPROCESS_ALLOWED):
                found.append((line, "dynamic import of subprocess or pty is not allowed"))
            for keyword in node.keywords:
                if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                    found.append((line, "shell=True is not allowed"))
        elif isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "os" and _os_banned(node.attr):
                found.append((line, f"os.{node.attr} is not allowed"))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root == "pty" or (root == "subprocess" and path not in SUBPROCESS_ALLOWED):
                    found.append((line, f"import of {root} is not allowed here (commands run through operator_lib.process)"))
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root == "pty" or (root == "subprocess" and path not in SUBPROCESS_ALLOWED):
                found.append((line, f"import of {root} is not allowed here (commands run through operator_lib.process)"))
            if root == "os":
                for alias in node.names:
                    if _os_banned(alias.name):
                        found.append((line, f"os.{alias.name} is not allowed"))
        elif isinstance(node, (ast.List, ast.Tuple)):
            message = _oci_list_finding(node)
            if message:
                found.append((line, message))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
            value = node.value
            if _TERRAFORM.fullmatch(value) or re.match(r"(?:terraform|tofu)\s", value):
                found.append((line, "Terraform calls are not allowed in operator scripts"))
            if _SUDO.search(value) and path not in SUDO_ALLOWED:
                found.append((line, "sudo is not allowed in operator scripts"))
    if allowed is not None:
        found.extend(scan_python_endpoints(path, tree, docs, allowed))
    return found


def _strip_comment(line):
    stripped = line.lstrip()
    if stripped.startswith("#"):
        return ""
    return re.sub(r"\s#.*$", "", line)


def scan_shell(path, text, allowed=None):
    found = []
    for number, raw in enumerate(text.split("\n"), 1):
        line = _strip_comment(raw) if number > 1 else raw if not raw.startswith("#!") else ""
        if not line.strip():
            continue
        if _EVAL.search(line):
            found.append((number, "eval is not allowed"))
        if _PIPE_TO_SHELL.search(line):
            found.append((number, "a download must not be piped to a shell"))
        if _TERRAFORM.search(line):
            found.append((number, "Terraform calls are not allowed in operator scripts"))
        if _SUDO.search(line) and path not in SUDO_ALLOWED:
            found.append((number, "sudo is not allowed in operator scripts"))
        if allowed is not None and re.search(r"(?<![\w-])(?:curl|wget)(?![\w-])", line):
            if not _URL.search(line.replace("$", _HOLE)):
                found.append((number, "a download without a literal endpoint (PA-22)"))
            for message in _endpoint_findings(re.sub(r"\$\{?\w*\}?", _HOLE, line), allowed):
                found.append((number, message))
        for match in _OCI.finditer(line):
            tokens = []
            for word in match.group(1).split():
                if word.startswith("-") or word.startswith(("$", "\"", "'")):
                    break
                tokens.append(word)
            if tokens and tokens[-1] not in READ_VERBS:
                found.append((number, "OCI call with a verb other than list, get, or inspect"))
    return found


def scan(path, text, allowed=None):
    """Findings (line, message) of one file. `allowed` is the set of hosts of operator_endpoints, or None when the policy is not enforced."""
    if _is_python(path, text):
        return sorted(set(scan_python(path, text, allowed)))
    if _is_shell(path, text):
        return sorted(set(scan_shell(path, text, allowed)))
    return []


_LIST_ITEM = re.compile(r"( +)- +([A-Za-z0-9_.][A-Za-z0-9_./*-]*)(?: +#.*)?")
_HOST = re.compile(r"[A-Za-z0-9_.][A-Za-z0-9_.-]*")


def read_list(text, key):
    """The items of a top-level list `key` of config/project.yaml, in the small subset that the file uses: `key: []`, or a block list of
    plain strings. None when the key is absent; ValueError for anything else (a quoted item, flow style, a scalar, a repeated key, a tab,
    an empty block). This check is self-contained: the policy runner of pr-contract carries the checks and nothing else."""
    lines = text.splitlines()
    hits = [i for i, line in enumerate(lines) if re.fullmatch(re.escape(key) + r":(?: .*)?", line)]
    if not hits:
        return None
    if len(hits) > 1 or "\t" in text:
        raise ValueError(key)
    rest = re.sub(r"\s+#.*$", "", lines[hits[0]][len(key) + 1:]).strip()
    if rest == "[]":
        return ()
    if rest:
        raise ValueError(key)
    items = []
    for line in lines[hits[0] + 1:]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        found = _LIST_ITEM.fullmatch(line)
        if found:
            items.append(found.group(2))
        elif line[0] == " ":
            raise ValueError(key)
        else:
            break
    if not items:
        raise ValueError(key)
    return tuple(items)


def load_policy(config_file):
    """(allowed, problem): the set of hosts to enforce, or None when nothing is enforced; problem is a finding text when the policy
    cannot be read and the check fails closed. The file is the configuration of the BASE commit (or the working tree without one)."""
    if config_file is None:
        return None, None
    try:
        with open(config_file, encoding="utf-8") as handle:
            text = handle.read(65537)
        if len(text) > 65536:
            raise ValueError("size")
        paths = read_list(text, "operator_paths")
        hosts = read_list(text, "operator_endpoints")
        if hosts is not None and not all(_HOST.fullmatch(host) for host in hosts):
            raise ValueError("policy")
    except (OSError, UnicodeDecodeError, ValueError):
        return None, "the policy input operator_paths or operator_endpoints cannot be read from the configuration; the endpoint check fails closed"
    if not paths:
        # An explicit empty operator_paths, or no such key (a generated repository: PC-8 judges that key and fails closed on its absence):
        # no operator scripts are judged here, so the generic fixtures keep passing.
        return None, None
    if hosts is None:
        return None, "operator_endpoints is missing while operator_paths is not empty; the endpoint check fails closed (I-10)"
    return {host.lower() for host in hosts}, None


def main(stdin=sys.stdin, out=sys.stdout, argv=()):
    args = list(argv)
    config_file = None
    unreadable = False
    while args:
        flag = args.pop(0)
        if flag == "--config" and args:
            config_file = args.pop(0)
        elif flag == "--config-unreadable":
            unreadable = True
        else:
            out.write("usage: operator_contract.py [--config FILE | --config-unreadable]\n")
            return 2
    allowed, problem = load_policy(config_file)
    if unreadable:
        problem = "the base commit cannot be read; the endpoint check fails closed"
    applicable = False
    bad = False
    for raw in stdin:
        path = raw.rstrip("\n")
        if not path.startswith(PREFIX):
            continue
        try:
            with open(path, "rb") as handle:
                data = handle.read(2_000_000)
            if b"\0" in data:
                continue
            text = data.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if not (_is_python(path, text) or _is_shell(path, text)):
            continue
        applicable = True
        for line, message in scan(path, text, allowed):
            out.write(f"{path}:{line}: {message}\n")
            bad = True
    if not applicable:
        return 77  # no operator script: the policy is not needed, and a configuration without the keys is no finding here
    if problem:
        out.write(f"{CONFIG_PATH}:1: {problem}\n")
        bad = True
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(argv=sys.argv[1:]))
