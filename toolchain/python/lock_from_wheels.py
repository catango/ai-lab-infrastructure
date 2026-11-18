#!/usr/bin/env python3
"""Turn a directory of downloaded wheels into the text of a hash-locked requirements file (CR-18 PR 5, operator.lock).

    lock_from_wheels.py <wheel-dir> <requirements.in>  > operator.lock

The wheels come from `pip download --only-binary=:all:` for CPython 3.12 on Linux x86-64. The script reads only file names and
bytes, runs nothing, and writes the lock to standard output, so it cannot overwrite a file. It stops with an error when a wheel
does not fit the target (a pure-Python wheel, or a CPython 3.12 or abi3 wheel built for Linux x86-64), when a top-level pin of
the input file is missing from the wheels, or when two wheels have the same project name.
"""
import hashlib
import os
import re
import sys

sys.dont_write_bytecode = True
_WHEEL = re.compile(r"(?P<name>[A-Za-z0-9_.]+)-(?P<version>[0-9][A-Za-z0-9_.!+]*)(?:-[0-9][A-Za-z0-9_.]*)?-(?P<py>[^-]+)-(?P<abi>[^-]+)-(?P<plat>[^-]+)\.whl")
_PIN = re.compile(r"(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)==(?P<version>[0-9][A-Za-z0-9._!+-]*)")
_LINUX_X86 = re.compile(r"(?:manylinux[0-9a-z_]*|linux)_x86_64(?:\.manylinux[0-9a-z_]*_x86_64)*")
HEADER = """# Hash-locked requirements for the operator profile (CR-18, ADR-011, ADR-005 decision 10).
# Top-level pins: toolchain/python/operator.in. Installed with: pip install --require-hashes --only-binary :all: --no-deps -r this-file
# Closure resolved by `pip download --only-binary=:all:` for CPython 3.12 on Linux x86-64 (Ubuntu 24.04, the operator machines).
# Hashes: the wheel pip chose for each project (pure Python, or built for CPython 3.12 or abi3 on Linux x86-64). Source distributions are not locked.
"""


class LockError(Exception):
    pass


def normalize(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def fits(match):
    py, abi, plat = match["py"], match["abi"], match["plat"]
    if plat == "any" and abi == "none":
        return py.startswith("py3") or py in ("py2.py3", "cp312")
    return bool(_LINUX_X86.fullmatch(plat)) and (abi in ("abi3", "cp312") or (py.startswith("py3") and abi == "none"))


def top_level(text):
    pins = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = _PIN.fullmatch(line)
        if not match:
            raise LockError(f"the input file has a line that is not an exact pin: {line}")
        pins[normalize(match["name"])] = match["version"]
    if not pins:
        raise LockError("the input file has no requirements")
    return pins


def build(wheel_dir, input_text):
    wanted = top_level(input_text)
    found = {}
    for filename in sorted(os.listdir(wheel_dir)):
        if not filename.endswith(".whl"):
            raise LockError(f"not a wheel: {filename}")
        match = _WHEEL.fullmatch(filename)
        if not match or not fits(match):
            raise LockError(f"a wheel does not fit CPython 3.12 on Linux x86-64: {filename}")
        key = normalize(match["name"])
        if key in found:
            raise LockError(f"two wheels for the project {key}")
        with open(os.path.join(wheel_dir, filename), "rb") as handle:
            found[key] = (match["version"], hashlib.sha256(handle.read()).hexdigest())
    for key, version in wanted.items():
        if key not in found or found[key][0] != version:
            raise LockError(f"the top-level pin {key}=={version} is not among the wheels")
    ordered = sorted(found, key=lambda key: (key not in wanted, key))
    return HEADER + "".join(f"\n{key}=={found[key][0]} \\\n    --hash=sha256:{found[key][1]}\n" for key in ordered)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("usage: lock_from_wheels.py <wheel-dir> <requirements.in>", file=sys.stderr)
        return 2
    try:
        with open(argv[1], encoding="utf-8") as handle:
            text = handle.read()
        sys.stdout.write(build(argv[0], text))
    except (LockError, OSError) as error:
        print(f"lock_from_wheels: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
