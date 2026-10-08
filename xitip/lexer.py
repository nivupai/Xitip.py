"""Lexer.

Tokens:  NAME    [A-Za-z][A-Za-z0-9_]*
         NUM     [0-9]+ | [0-9]*\\.[0-9]+
         SIGN    + -
         REL     = == <= >=
         'H' 'I' only when followed by '(' (otherwise they are names)
         everything else is a single character literal

'#' starts a comment; spaces, tabs and CR are ignored.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Token:
    kind: str       # "name" "num" "sign" "rel" "lit" "eof"
    text: str
    col: int        # 1-based column of the first character
    len: int


def _is_blank(c: str) -> bool:
    return c in (" ", "\t", "\r")


def _is_alpha(c: str) -> bool:
    return ("a" <= c <= "z") or ("A" <= c <= "Z")


def _is_name_char(c: str) -> bool:
    return _is_alpha(c) or c.isdigit() or c == "_"


def tokenize(line: str) -> list[Token]:
    n = len(line)
    toks: list[Token] = []
    i = 0
    while i < n:
        c = line[i]
        nxt = line[i + 1] if i + 1 < n else "\0"
        if c == "#":
            break
        elif _is_blank(c):
            i += 1
        elif c in ("H", "I") and _followed_by_paren(line, i + 1, n):
            toks.append(Token("lit", c, i + 1, 1))
            i += 1
        elif _is_alpha(c):
            j = i
            while j + 1 < n and _is_name_char(line[j + 1]):
                j += 1
            toks.append(Token("name", line[i:j + 1], i + 1, j - i + 1))
            i = j + 1
        elif c.isdigit() or (c == "." and nxt.isdigit()):
            j = i
            while j < n and line[j].isdigit():
                j += 1
            if j < n and line[j] == "." and j + 1 < n and line[j + 1].isdigit():
                j += 1
                while j < n and line[j].isdigit():
                    j += 1
            toks.append(Token("num", line[i:j], i + 1, j - i))
            i = j
        elif c in ("+", "-"):
            toks.append(Token("sign", c, i + 1, 1))
            i += 1
        elif c == "=":
            length = 2 if nxt == "=" else 1
            toks.append(Token("rel", "=", i + 1, length))
            i += length
        elif c in ("<", ">") and nxt == "=":
            toks.append(Token("rel", c + "=", i + 1, 2))
            i += 2
        else:
            toks.append(Token("lit", c, i + 1, 1))
            i += 1
    toks.append(Token("eof", "", n + 1, 1))
    return toks


def _followed_by_paren(line: str, j: int, n: int) -> bool:
    while j < n and _is_blank(line[j]):
        j += 1
    return j < n and line[j] == "("
