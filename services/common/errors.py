"""Safe summaries for exceptions crossing service or report boundaries."""


def safe_exception_class(exc: BaseException) -> str:
    """Return only a bounded exception class identifier, never its message."""
    name = type(exc).__name__
    if not name.isascii() or not name.isidentifier() or len(name) > 64:
        return "Exception"
    return name
