"""Contract rules for operator scripts (CR-18 design section 4; acceptance S-6 and S-11). Used by operator-contract.sh.

Reads tracked paths on stdin and prints findings as path:line: message. Rules, for files under scripts/operator/:
no eval, exec, os.system, os.popen, os.exec*, os.spawn*, shell=True, or pty; subprocess only in the process module;
sudo only in setup and facts; no Terraform; no OCI call with a verb other than list, get, or inspect; no download
piped to a shell. Static checks cannot see dynamic values, so operator_lib.process enforces the same at run time.
"""
import ast
import re
import sys

PREFIX = "scripts/operator/"
# hostfacts.py only reads the name of the group "sudo" from /etc/group; it starts no command (operator_lib.process refuses sudo
# unless the facts script passes an exact allowed command).
SUDO_ALLOWED = frozenset({"scripts/operator/setup", "scripts/operator/facts", "scripts/operator/lib/operator_lib/hostfacts.py"})
SUBPROCESS_ALLOWED = frozenset({"scripts/operator/lib/operator_lib/process.py"})
READ_VERBS = frozenset({"list", "get", "inspect"})
_OS_BANNED = frozenset({"system", "popen", "posix_spawn", "posix_spawnp"})
_OS_PREFIXES = ("exec", "spawn")
_SUDO = re.compile(r"(?<![\w-])sudo(?![\w-])")
_TERRAFORM = re.compile(r"(?<![\w-])(?:terraform|tofu)(?![\w-])")
_EVAL = re.compile(r"(?<![\w-])eval(?![\w-])")
_PIPE_TO_SHELL = re.compile(r"\b(?:curl|wget)\b[^|\n]*\|\s*(?:sudo\s+)?(?:ba|z|da|k)?sh\b")
_OCI = re.compile(r"(?<![\w./-])oci\s+([^\n|;&]*)")


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


def scan_python(path, text):
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
                found.append((line, "sudo is allowed only in setup and facts"))
    return found


def _strip_comment(line):
    stripped = line.lstrip()
    if stripped.startswith("#"):
        return ""
    return re.sub(r"\s#.*$", "", line)


def scan_shell(path, text):
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
            found.append((number, "sudo is allowed only in setup and facts"))
        for match in _OCI.finditer(line):
            tokens = []
            for word in match.group(1).split():
                if word.startswith("-") or word.startswith(("$", "\"", "'")):
                    break
                tokens.append(word)
            if tokens and tokens[-1] not in READ_VERBS:
                found.append((number, "OCI call with a verb other than list, get, or inspect"))
    return found


def scan(path, text):
    if _is_python(path, text):
        return sorted(set(scan_python(path, text)))
    if _is_shell(path, text):
        return sorted(set(scan_shell(path, text)))
    return []


def main(stdin=sys.stdin, out=sys.stdout):
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
        for line, message in scan(path, text):
            out.write(f"{path}:{line}: {message}\n")
            bad = True
    if not applicable:
        return 77
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
