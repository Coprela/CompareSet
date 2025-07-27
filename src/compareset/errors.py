"""Custom exceptions used across CompareSet."""

__all__ = ["InvalidDimensionsError"]


class InvalidDimensionsError(Exception):
    """Raised when PDF pages have invalid sizes."""

    pass
