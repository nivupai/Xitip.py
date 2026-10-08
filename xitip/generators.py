"""Shannon-type LP: generators of the cone of implied inequalities.

Let h be the vector of joint entropies. An inequality  v.h + v0 >= 0  is
Shannon-type (given constraints  a_i.h + b_i >= 0) iff it follows from the
elemental inequalities and the constraints. By the affine Farkas lemma
(for a feasible constraint system) this holds iff there are multipliers
y >= 0 with

    sum y_i a_i = v    and    sum y_i b_i <= v0,

where the a_i range over the elemental inequalities (b_i = 0) and the
constraints (equalities contribute both a_i and -a_i). Hence we solve

    min b.y   s.t.   A y = v,  y >= 0

and the inequality holds iff the LP is feasible and its optimum is <= v0
(or it is unbounded, which only happens for contradictory constraints). A
solution y is a certificate: it expresses the inequality as a non-negative
combination of elemental inequalities and constraints.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from math import comb

from .relations import LinRel, Problem


@dataclass(frozen=True)
class Generator:
    """A generator ``a.h + b >= 0`` of the cone of implied inequalities.

    ``line`` is set on the first generator of an equality constraint (the
    next generator is then its negation). ``kind`` and ``data`` describe
    where the generator comes from, so that certificates can be printed:

    | kind          | data              | meaning                          |
    |---------------|-------------------|----------------------------------|
    | "entropy"     | (i, 0, 0)         | H(X_i | rest) >= 0               |
    | "mutinf"      | (i, j, K)         | I(X_i ; X_j | X_K) >= 0          |
    | "constraint"  | (row, sign, 0)    | constraint row, negated if < 0   |

    ``equality`` records that the constraint was written as an equality, so
    the generator is not merely non-negative but zero.
    """
    a: list[tuple[int, Fraction]]
    b: Fraction
    line: bool
    kind: str
    data: tuple[int, int, int]
    equality: bool = False


def elemental_inequalities(n: int) -> list[Generator]:
    """Elemental inequalities for n random variables:

        H(X_i | X_rest) >= 0               for all i
        I(X_i ; X_j | X_K) >= 0            for all i < j, K subset rest \\ {i,j}

    These generate all Shannon-type inequalities.
    """
    gens: list[Generator] = []
    full = (1 << n) - 1

    def pair(k: int, v: int) -> tuple[int, Fraction]:
        return (k, Fraction(v))

    for i in range(n):
        c = full ^ (1 << i)
        a = [pair(full, 1)]
        if c != 0:
            a.append(pair(c, -1))
        gens.append(Generator(a, Fraction(0), False, "entropy", (i, 0, 0)))

    for i in range(n - 1):
        for j in range(i + 1, n):
            A, B = 1 << i, 1 << j
            rest = full ^ A ^ B
            K = rest
            while True:   # enumerate all subsets K of rest
                a = [pair(A | K, 1), pair(B | K, 1), pair(A | B | K, -1)]
                if K != 0:
                    a.append(pair(K, -1))
                gens.append(Generator(a, Fraction(0), False, "mutinf", (i, j, K)))
                if K == 0:
                    break
                K = (K - 1) & rest
    return gens


def count_elemental(n: int) -> int:
    """Number of elemental inequalities (they come first in `generators`)."""
    if n < 2:
        return n
    return n + (comb(n, 2) << (n - 2))


def generators(P: Problem) -> list[Generator]:
    """All elemental inequalities followed by the constraints of P.

    An equality constraint contributes two generators (itself and its
    negation).
    """
    gens = elemental_inequalities(len(P.var_names))
    for r in P.constraints:
        a = [(k, v) for k, v in r.coefs.items() if k != 0]
        b = r.coefs.get(0, Fraction(0))
        gens.append(Generator(a, b, r.equality, "constraint", (r.row, 1, 0),
                               r.equality))
        if r.equality:
            gens.append(Generator([(k, -v) for k, v in a], -b, False,
                                   "constraint", (r.row, -1, 0), True))
    return gens


def setname(mask: int, names: list[str]) -> str:
    """Names of the variables in the subset `mask`, e.g. "X,Y"."""
    return ",".join(names[i] for i in range(len(names)) if mask & (1 << i))


def describe(g: Generator, names: list[str], sources: list[str] | None = None) -> str:
    """The generator as a readable information expression,
    e.g. "I(X;Y|Z) >= 0". A constraint is named by its number and, if
    `sources` has it, its own text.
    """
    sources = sources or []
    full = (1 << len(names)) - 1
    if g.kind == "entropy":
        i = g.data[0]
        rest = full ^ (1 << i)
        cond = "" if rest == 0 else "|" + setname(rest, names)
        return f"H({names[i]}{cond}) >= 0"
    elif g.kind == "mutinf":
        i, j, K = g.data
        cond = "" if K == 0 else "|" + setname(K, names)
        return f"I({names[i]};{names[j]}{cond}) >= 0"
    # A statement can imply several relations (a Markov chain implies one
    # per link), so this is "from constraint k", not "constraint k".
    row, sign, _ = g.data
    text = f": {sources[row - 1]}" if 0 < row <= len(sources) and sources[row - 1] else ""
    return f"from constraint {row - 1}{', reversed' if sign < 0 else ''}{text}"
