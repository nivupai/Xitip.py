"""Errors raised by Xitip."""


class XitipError(Exception):
    """Invalid input or unsolvable problem (reported to the user)."""


class SyntaxError_(Exception):
    """Syntax error; ``msg`` includes the offending line and a marker.

    Named ``SyntaxError_`` to avoid shadowing the builtin ``SyntaxError``;
    re-exported as ``SyntaxError`` from :mod:`xitip`.
    """

    def __init__(self, msg: str, col: int, length: int):
        super().__init__(msg)
        self.msg = msg
        self.col = col
        self.len = length

    def __str__(self) -> str:
        return self.msg
