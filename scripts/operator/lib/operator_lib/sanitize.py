"""Output that is safe to paste (ADR-011 decision 6, design section 4 rule 7).

scrub() removes identifiers from free text. summary_value() lets only classified values through: yes/no,
counts, and sizes. Anything else becomes a placeholder.
"""
import ipaddress
import re
import unicodedata

PLACEHOLDER = "<redacted>"
MAX_COUNT = 10**9
_DROP = {"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"}
_OCID = re.compile(r"\bocid1\.[A-Za-z0-9_.-]+")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
_IPV4 = re.compile(r"(?<![0-9A-Za-z.])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9A-Za-z])")
_IPV6 = re.compile(r"(?<![0-9A-Za-z:])[0-9A-Fa-f:.]*:[0-9A-Fa-f:.]*(?![0-9A-Za-z:])")
_KEY = re.compile(r"[a-z0-9_.-]{1,40}")
_WORDS = frozenset({"yes", "no", "unknown"})
_SIZE = re.compile(r"[0-9]{1,9} ?(?:[KMGT]i?B|B)")


def _drop_controls(text):
    return "".join(ch for ch in text if unicodedata.category(ch) not in _DROP or ch in "\n\t")


def _v6(match):
    try:
        ipaddress.IPv6Address(match.group(0))
    except ValueError:
        return match.group(0)
    return "<ip>"


def scrub(text):
    """Remove OCIDs, email addresses, and IPv4 and IPv6 addresses, and drop control characters."""
    text = _drop_controls(str(text))
    text = _OCID.sub("<ocid>", text)
    text = _EMAIL.sub("<email>", text)
    text = _IPV6.sub(_v6, text)
    text = _IPV4.sub("<ip>", text)
    return text


def summary_value(value):
    """yes/no for a bool, a non-negative count, a size such as '47 GB', or one of yes/no/unknown. Anything else is a placeholder."""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        return str(value) if 0 <= value <= MAX_COUNT else PLACEHOLDER
    if isinstance(value, str):
        if value in _WORDS or _SIZE.fullmatch(value):
            return value
        if value.isascii() and value.isdigit() and len(value) <= 9:
            return value
    return PLACEHOLDER


def summary_lines(mapping):
    lines = []
    for key, value in mapping.items():
        safe_key = key if isinstance(key, str) and _KEY.fullmatch(key) else PLACEHOLDER
        lines.append(f"{safe_key}: {summary_value(value)}")
    return lines
