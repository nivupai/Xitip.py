"""Recognising information quantities.

An expression such as  -H(Z) + H(X,Z) + H(Y,Z) - H(X,Y,Z)  is easier to
read as  I(X;Y|Z). Both the statement being proven and the remainder of
each proof step are matched against the shapes

    H(A)                            one term
    H(A) - H(B)        = H(A\\B|B)         for B subset A
    H(A) + H(B) - H(A|B)            = I(A;B)           for disjoint A, B
    H(A) + H(B) - H(AuB) - H(A&B)   = I(A\\D;B\\D|D)     for D = A&B

which needs no search: the sets are read off the terms themselves.
"""
from __future__ import annotations

from fractions import Fraction
from math import gcd
from functools import reduce

from .generators import setname


def format_coef(c: Fraction) -> str:
    return str(c.numerator) if c.denominator == 1 else f"{c.numerator}/{c.denominator}"


def name_quantity(coefs: dict, names: list[str]) -> str | None:
    """Recognise `coefs` as a positive multiple of a single information
    quantity, e.g. "2 I(X;Y|Z)". None if it is not one (or has a constant
    term).
    """
    terms = [(k, v) for k, v in coefs.items() if v != 0]
    if not terms or len(terms) > 4:
        return None
    if any(k == 0 for k, _ in terms):
        return None

    denom = reduce(lambda a, b: a * b // gcd(a, b), (v.denominator for _, v in terms), 1)
    ints = [v.numerator * (denom // v.denominator) for _, v in terms]
    g = reduce(gcd, (abs(i) for i in ints), 0) or 1
    factor = Fraction(denom, g)
    scaled = [(k, int(v * factor)) for k, v in terms]

    plus = sorted(k for k, v in scaled if v == 1)
    minus = sorted(k for k, v in scaled if v == -1)
    if len(plus) + len(minus) != len(scaled):
        return None

    name = _shape_name(plus, minus, names)
    if name is None:
        return None
    scale = Fraction(1, 1) / factor
    if scale == 1:
        return name
    return format_coef(scale) + " " + name


def signed_name(coefs: dict, names: list[str]) -> str | None:
    """Like name_quantity, but also recognising the negation of a quantity,
    which is what an equality constraint used in reverse is: "-I(W;Y|X)".
    """
    name = name_quantity(coefs, names)
    if name is not None:
        return name
    negated = name_quantity({k: -v for k, v in coefs.items()}, names)
    return None if negated is None else "-" + negated


def _shape_name(plus: list[int], minus: list[int], names: list[str]) -> str | None:
    def set_(mask: int) -> str:
        return setname(mask, names)

    def cond(U: int) -> str:
        return "" if U == 0 else "|" + set_(U)

    if len(plus) == 1 and not minus:                       # H(A)
        return f"H({set_(plus[0])})"
    elif len(plus) == 1 and len(minus) == 1:                # H(A\B|B)
        A, B = plus[0], minus[0]
        if not (B & ~A == 0 and B != A):
            return None
        return f"H({set_(A & ~B)}{cond(B)})"
    elif len(plus) == 2 and len(minus) == 1:                # I(A;B)
        A, B = plus
        if not (A & B == 0 and minus[0] == A | B):
            return None
        return f"I({set_(A)};{set_(B)})"
    elif len(plus) == 2 and len(minus) == 2:                # I(A\D;B\D|D)
        A, B = plus
        D = A & B
        if not (D != 0 and minus == sorted([A | B, D])):
            return None
        return f"I({set_(A & ~D)};{set_(B & ~D)}{cond(D)})"
    return None
