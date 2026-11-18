"""Token prompt (ADR-011 decision 4, design section 4 rule 9). A token is read with getpass, returned to the caller,
and never printed, logged, read from the environment, or written anywhere by this module."""
import getpass
import re

_TOKEN = re.compile(r"[A-Za-z0-9_]{16,255}")


class TokenError(Exception):
    """The input was empty, missing, or not shaped like a token. The message never contains the input."""


def prompt_token(label, getpass_fn=getpass.getpass):
    try:
        value = getpass_fn(f"{label} token (input is hidden): ")
    except EOFError:
        raise TokenError("no token was entered") from None
    value = value.strip() if isinstance(value, str) else ""
    if not _TOKEN.fullmatch(value):
        raise TokenError("the value is not a plausible token")
    return value
