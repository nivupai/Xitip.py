"""Recursive-descent parser.

    statement    := <empty> | relation | markov_chain | mutual_indep | function_of
    relation     := expr REL expr
    markov_chain := var_list '/' var_list '/' var_list ('/' var_list)*
    mutual_indep := var_list '.' var_list ('.' var_list)*
    function_of  := var_list ':' var_list
    expr         := [SIGN] term (SIGN term)*
    term         := NUM quantity | quantity | NUM
    quantity     := 'H' '(' var_list ['|' var_list] ')'
                  | 'I' '(' var_list (colon var_list)+ ['|' var_list] ')'
    colon        := ':' | ';'
    var_list     := NAME (',' NAME)*
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from .errors import SyntaxError_
from .lexer import Token, tokenize

VarList = list[str]


@dataclass(frozen=True)
class Quantity:
    parts: list[VarList]     # H: one part; I: two or more parts
    cond: VarList


@dataclass(frozen=True)
class Term:
    coef: Fraction
    quantity: Quantity | None   # None = constant term


@dataclass(frozen=True)
class Relation:
    left: list[Term]
    rel: str            # "eq" "le" "ge"
    right: list[Term]


@dataclass(frozen=True)
class MarkovChain:
    parts: list[VarList]


@dataclass(frozen=True)
class MutualIndependence:
    parts: list[VarList]


@dataclass(frozen=True)
class FunctionOf:
    func: VarList
    of: VarList


Statement = Relation | MarkovChain | MutualIndependence | FunctionOf

RELATIONS = {"=": "eq", "<=": "le", ">=": "ge"}
RELATION_TEXT = {"eq": "=", "le": "<=", "ge": ">="}


class _Parser:
    def __init__(self, toks: list[Token]):
        self.toks = toks
        self.pos = 0

    def peek(self) -> Token:
        return self.toks[self.pos]

    def advance(self) -> Token:
        t = self.toks[self.pos]
        if t.kind != "eof":
            self.pos += 1
        return t

    def islit(self, s: str) -> bool:
        t = self.peek()
        return t.kind == "lit" and t.text == s

    def iscolon(self) -> bool:
        return self.islit(":") or self.islit(";")

    def unexpected(self, expecting: str):
        t = self.peek()
        raise SyntaxError_(f"unexpected {_describe(t)}, expecting {expecting}",
                            t.col, t.len)

    def expect_lit(self, s: str, expecting: str | None = None):
        if not self.islit(s):
            self.unexpected(expecting or f"'{s}'")
        self.advance()


def _describe(t: Token) -> str:
    if t.kind == "eof":
        return "end of input"
    if t.kind == "name":
        return f"name '{t.text}'"
    if t.kind == "num":
        return f"number {t.text}"
    return f"'{t.text}'"


def _parse_number(s: str) -> Fraction:
    if "." not in s:
        return Fraction(int(s))
    int_part, frac = s.split(".", 1)
    return Fraction(int(int_part + frac), 10 ** len(frac))


def _parse_var_list(p: _Parser) -> VarList:
    if p.peek().kind != "name":
        p.unexpected("a variable name")
    names = [p.advance().text]
    while p.islit(","):
        p.advance()
        if p.peek().kind != "name":
            p.unexpected("a variable name")
        names.append(p.advance().text)
    return names


def _parse_quantity(p: _Parser) -> Quantity:
    kw = p.advance().text       # "H" or "I"
    p.expect_lit("(")
    parts = [_parse_var_list(p)]
    if kw == "I":
        if not p.iscolon():
            p.unexpected("',', ';' or ':'")
        while p.iscolon():
            p.advance()
            parts.append(_parse_var_list(p))
    cond: VarList = []
    if p.islit("|"):
        p.advance()
        cond = _parse_var_list(p)
    p.expect_lit(")", "',', '|' or ')'" if kw == "H" else "',', ';', '|' or ')'")
    return Quantity(parts, cond)


def _isquantity(t: Token) -> bool:
    return t.kind == "lit" and t.text in ("H", "I")


def _parse_term(p: _Parser, sign: int) -> Term:
    t = p.peek()
    if t.kind == "num":
        coef = sign * _parse_number(p.advance().text)
        if _isquantity(p.peek()):
            return Term(coef, _parse_quantity(p))
        return Term(coef, None)
    elif _isquantity(t):
        return Term(Fraction(sign), _parse_quantity(p))
    p.unexpected("a number, H(...) or I(...)")
    raise AssertionError("unreachable")


def _readsign(p: _Parser) -> int:
    return -1 if p.advance().text == "-" else 1


def _parse_expr(p: _Parser) -> list[Term]:
    sign = _readsign(p) if p.peek().kind == "sign" else 1
    terms = [_parse_term(p, sign)]
    while p.peek().kind == "sign":
        sign = _readsign(p)
        terms.append(_parse_term(p, sign))
    return terms


def _parse_relation(p: _Parser) -> Relation:
    left = _parse_expr(p)
    if p.peek().kind != "rel":
        p.unexpected("'+', '-', '<=', '>=' or '='")
    rel = RELATIONS[p.advance().text]
    right = _parse_expr(p)
    return Relation(left, rel, right)


def _parse_var_statement(p: _Parser) -> Statement:
    first = _parse_var_list(p)
    t = p.peek()
    if p.islit("/") or p.islit("."):
        sep = t.text
        parts = [first]
        while p.islit(sep):
            p.advance()
            parts.append(_parse_var_list(p))
        if sep == "/":
            if len(parts) < 3:
                p.unexpected("'/'")
            return MarkovChain(parts)
        return MutualIndependence(parts)
    elif p.islit(":"):
        p.advance()
        return FunctionOf(first, _parse_var_list(p))
    p.unexpected("',', '/', '.' or ':'")
    raise AssertionError("unreachable")


def parse_statement(line: str) -> Statement | None:
    """Parse one line. Returns ``None`` for empty or comment-only lines."""
    p = _Parser(tokenize(line))
    if p.peek().kind == "eof":
        return None
    stmt = _parse_var_statement(p) if p.peek().kind == "name" else _parse_relation(p)
    if p.peek().kind != "eof":
        p.unexpected("end of input")
    return stmt


def parse_statements(lines) -> tuple[list[Statement], list[str]]:
    """Parse all lines, dropping empty/comment-only ones, keeping source text."""
    from .errors import XitipError

    stmts: list[Statement] = []
    sources: list[str] = []
    for row, line in enumerate(lines, start=1):
        try:
            stmt = parse_statement(line)
        except SyntaxError_ as e:
            msg = (f"syntax error, {e.msg}\n"
                   f"in row {row} col {e.col}:\n\n"
                   f"    {line}\n"
                   f"    {' ' * (e.col - 1)}{'^' * max(1, e.len)}")
            raise SyntaxError_(msg, e.col, e.len) from None
        if stmt is not None:
            stmts.append(stmt)
            sources.append(line.split("#", 1)[0].strip())
    if not stmts:
        raise XitipError("no information expression given")
    return stmts, sources


def parse_lines(lines) -> list[Statement]:
    return parse_statements(lines)[0]
