"""Exception types. Messages are fixed text: they never contain PR text or the token."""


class InputError(Exception):
    """Bad command line or local input (exit 2)."""


class ApiError(Exception):
    """The API failed, was rate limited, or returned something malformed (exit 3)."""


class NotFound(Exception):
    """The API answered 404 for a resource that was asked for by number."""


class LimitExceeded(Exception):
    """A hard cap was reached (changed files); the check fails closed."""
