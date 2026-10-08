"""Linear relations over joint entropies.

A relation is stored as  sum coefs[S] * H(S) + coefs[0]  >= 0  (or = 0),
where S is the bitmask of a non-empty subset of the random variables and
key 0 holds the constant term.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from .errors import XitipError
from .parser import (FunctionOf, MarkovChain, MutualIndependence, Relation,
                      Statement, Term)
from .variables import variables

MAX_VARS = 30


@dataclass(frozen=True)
class LinRel:
    coefs: dict[int, Fraction]
    equality: bool
    row: int = 0     # the line the statement came from (0 if unknown)


def negate(r: LinRel) -> LinRel:
    return LinRel({k: -v for k, v in r.coefs.items()}, r.equality, r.row)


def _inc(d: dict[int, Fraction], k: int, v: Fraction) -> None:
    d[k] = d.get(k, Fraction(0)) + v


def _subset(index: dict[str, int], vl: list[str]) -> int:
    s = 0
    for v in vl:
        s |= 1 << (index[v] - 1)
    return s


def add_term(d: dict[int, Fraction], index: dict[str, int], t: Term, scale: int) -> None:
    coef = scale * t.coef
    if t.quantity is None:
        _inc(d, 0, coef)
        return
    # Multivariate (conditional) mutual information as the alternating sum
    # of conditional entropies over non-empty subsets T of the parts:
    #
    #   I(X1:...:Xk|Y) = - sum_T (-1)^|T| H(T|Y),   H(T|Y) = H(T,Y) - H(Y)
    #
    # For k=1 this is just H(X1|Y).
    q = t.quantity
    parts = [_subset(index, vl) for vl in q.parts]
    c = _subset(index, q.cond)
    k = len(parts)
    if k > MAX_VARS:
        raise XitipError(f"Too many parts in mutual information! "
                          f"At most {MAX_VARS} are allowed.")
    for s_mask in range(1, (1 << k)):
        a, sign = 0, -1
        for i in range(k):
            if s_mask & (1 << i):
                a |= parts[i]
                sign = -sign
        _inc(d, a | c, sign * coef)
    if c != 0:
        _inc(d, c, -coef)


def _linrels_relation(index, r: Relation) -> list[LinRel]:
    # l <= r  =>  -l + r >= 0;   l >= r  =>  l - r >= 0;   l = r  =>  l - r = 0
    ls = -1 if r.rel == "le" else 1
    d: dict[int, Fraction] = {}
    for t in r.left:
        add_term(d, index, t, ls)
    for t in r.right:
        add_term(d, index, t, -ls)
    return [LinRel(d, r.rel == "eq")]


def _linrels_mutual_independence(index, mi: MutualIndependence) -> list[LinRel]:
    # 0 = H(a) + H(b) + ... - H(a,b,...)
    d: dict[int, Fraction] = {}
    all_ = 0
    for vl in mi.parts:
        s = _subset(index, vl)
        all_ |= s
        _inc(d, s, Fraction(1))
    _inc(d, all_, Fraction(-1))
    return [LinRel(d, True)]


def _linrels_markov_chain(index, mc: MarkovChain) -> list[LinRel]:
    # For each link: 0 = I(a:c|b) = H(a,b) + H(c,b) - H(b) - H(a,b,c), where
    # a accumulates all preceding variables.
    rels = []
    a = 0
    for i in range(len(mc.parts) - 2):
        a |= _subset(index, mc.parts[i])
        b = _subset(index, mc.parts[i + 1])
        c = _subset(index, mc.parts[i + 2])
        d: dict[int, Fraction] = {}
        _inc(d, a | b, Fraction(1))
        _inc(d, c | b, Fraction(1))
        _inc(d, b, Fraction(-1))
        _inc(d, a | b | c, Fraction(-1))
        rels.append(LinRel(d, True))
    return rels


def _linrels_function_of(index, fo: FunctionOf) -> list[LinRel]:
    # 0 = H(func|of) = H(func,of) - H(of)
    f, o = _subset(index, fo.func), _subset(index, fo.of)
    d: dict[int, Fraction] = {}
    _inc(d, f | o, Fraction(1))
    _inc(d, o, Fraction(-1))
    return [LinRel(d, True)]


def linrels(index, stmt: Statement) -> list[LinRel]:
    if isinstance(stmt, Relation):
        return _linrels_relation(index, stmt)
    if isinstance(stmt, MutualIndependence):
        return _linrels_mutual_independence(index, stmt)
    if isinstance(stmt, MarkovChain):
        return _linrels_markov_chain(index, stmt)
    if isinstance(stmt, FunctionOf):
        return _linrels_function_of(index, stmt)
    raise TypeError(f"unknown statement type {type(stmt)!r}")


@dataclass(frozen=True)
class Problem:
    var_names: list[str]
    inquiries: list[LinRel]       # the statement to prove (first line)
    constraints: list[LinRel]     # all further lines
    sources: list[str]            # the text each statement came from

    @staticmethod
    def build(stmts: list[Statement], sources: list[str] | None = None) -> "Problem":
        if sources is None:
            sources = [""] * len(stmts)
        names = variables(stmts)
        if len(names) > MAX_VARS:
            raise XitipError(f"Too many variables! At most {MAX_VARS} are allowed.")
        index = {v: i + 1 for i, v in enumerate(names)}

        def clean(r: LinRel, row: int) -> LinRel:
            return LinRel({k: v for k, v in r.coefs.items() if v != 0},
                           r.equality, row)

        rels = [[clean(r, row) for r in linrels(index, s)]
                for row, s in enumerate(stmts, start=1)]
        inquiries = rels[0] if rels else []
        constraints = [r for group in rels[1:] for r in group]
        return Problem(names, inquiries, constraints, sources)
