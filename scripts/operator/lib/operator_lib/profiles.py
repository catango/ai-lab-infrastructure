"""Machine profiles (design section 3.3): architecture, OS, and resource limits per operator machine, no identifiers.
The tests and the CI job size their limits from the strictest profile."""
import re
import tomllib

from .sanitize import scrub

_NAME = re.compile(r"[a-z][a-z0-9_]{0,30}")
_ARCH = frozenset({"x86-64", "arm64"})
_OS = re.compile(r"(?:ubuntu-[0-9]{2}\.[0-9]{2}|debian-[0-9]{1,2})(?:-minimal)?")
_INTS = {"memory_mb": (64, 1_048_576), "cpu_threads": (1, 256), "disk_gb": (1, 65_536), "bandwidth_mbit": (1, 100_000)}
_STRINGS = ("arch", "os")


class ProfileError(Exception):
    pass


def _entry(name, entry):
    if not _NAME.fullmatch(name) or not isinstance(entry, dict):
        raise ProfileError("invalid machine entry")
    for key, value in entry.items():
        if key in _INTS:
            low, high = _INTS[key]
            if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
                raise ProfileError(f"invalid value for {key}")
        elif key in _STRINGS:
            if not isinstance(value, str) or scrub(value) != value:
                raise ProfileError(f"invalid value for {key}")
            if (key == "arch" and value not in _ARCH) or (key == "os" and not _OS.fullmatch(value)):
                raise ProfileError(f"invalid value for {key}")
        else:
            raise ProfileError("unknown key in a machine entry")
    return dict(entry)


def load_profiles(path):
    try:
        with open(path, "rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        raise ProfileError("the machine-profile file could not be read") from None
    machines = data.get("machines")
    if set(data) != {"machines"} or not isinstance(machines, dict) or not machines:
        raise ProfileError("the file must hold a [machines.<name>] table for each machine and nothing else")
    return {name: _entry(name, entry) for name, entry in machines.items()}


def strictest(profiles):
    """The smallest value of each limit that any machine defines. Memory must be known for at least one machine."""
    result = {}
    for key in _INTS:
        values = [entry[key] for entry in profiles.values() if key in entry]
        if values:
            result[key] = min(values)
    if "memory_mb" not in result:
        raise ProfileError("no machine defines memory_mb")
    return result
