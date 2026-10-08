"""Public API: prove, explain, and the Proof / Counterexample / Result types."""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from fractions import Fraction

from .decide import decide, implied, simplify_certificate
from .errors import XitipError
from .generators import Generator, count_elemental, describe as describe_generator, setname
from .parser import Quantity, Relation, Term, RELATION_TEXT, parse_statements
from .quantities import format_coef, name_quantity, signed_name
from .relations import Problem, LinRel, add_term, negate
from .variables import variables as _variables


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _format_coefs(coefs: dict, names: list[str]) -> str:
    parts = []
    for S, c in sorted(coefs.items(), key=lambda p: (p[0] == 0, bin(p[0]).count("1"), p[0])):
        if c == 0:
            continue
        sign = ("-" if c < 0 else "") if not parts else (" - " if c < 0 else " + ")
        mag = abs(c)
        num = "" if (mag == 1 and S != 0) else format_coef(mag) + ("" if S == 0 else " ")
        parts.append(sign + num + ("" if S == 0 else f"H({setname(S, names)})"))
    if not parts:
        parts.append("0")
    return "".join(parts)


def format_linrel(r: LinRel, names: list[str]) -> str:
    return _format_coefs(r.coefs, names) + (" = 0" if r.equality else " >= 0")


# ---------------------------------------------------------------------------
# Certificates
# ---------------------------------------------------------------------------

@dataclass
class ProofStep:
    """One step of a step-by-step proof: `coefficient` times the
    non-negative quantity `name` is split off the expression, leaving
    `remainder`.
    """
    coefficient: Fraction
    name: str                # "I(X;Y|Z)"
    label: str                # "I(X;Y|Z)" or "C1" for a constraint
    source: str                # "constraint 1: X/Y/Z" for a constraint, else ""
    expansion: str             # the quantity written with entropies
    remainder: str             # what is left of the expression after this step
    remainder_name: str        # the remainder as one quantity, if it is one
    named: str                 # the quantity under a name, if it has one
    justification: str         # ">= 0" or "= 0"
    quantity: dict              # the same, by subset bitmask (0 = constant)


@dataclass
class Proof:
    """Why an information expression is Shannon-type: it equals a
    non-negative combination of elemental inequalities and constraints,
    plus a non-negative constant.
    """
    expression: str
    expression_name: str
    terms: list[tuple[Fraction, str]]
    constant: Fraction
    steps: list[ProofStep]
    coefficients: dict


@dataclass
class TermValue:
    """One quantity of the statement that was refuted, as it stands at the
    counterexample.
    """
    coefficient: Fraction
    quantity: str
    value: Fraction
    side: str                 # "left" or "right"
    expansion: str
    substitution: str


@dataclass
class Counterexample:
    """Why an information expression could not be proven: entropy values
    `h` satisfying every elemental inequality and every constraint, but not
    the expression itself.
    """
    expression: str
    var_names: list[str]
    entropies: list[Fraction]     # h[S], indexed by subset bitmask (1..D-1)
    value: Fraction
    direction: bool
    statement: str
    terms: list[TermValue]
    relation: str


Certificate = Proof | Counterexample


@dataclass
class Result:
    """The verdict of explain() together with its certificates."""
    verdict: bool
    certificates: list[Certificate]

    def __bool__(self) -> bool:
        return self.verdict


def chop_relation(s: str) -> str:
    return re.sub(r" = 0$", "", re.sub(r" >= 0$", "", s))


def make_proof(y: list[Fraction], gens: list[Generator], r: LinRel,
               names: list[str], sources: list[str]) -> Proof:
    used = [j for j in range(len(gens)) if y[j] != 0]
    used.sort(key=lambda j: (gens[j].kind != "constraint", -y[j], j))
    terms: list[tuple[Fraction, str]] = []
    steps: list[ProofStep] = []
    nconstraints = 0
    remainder = {k: v for k, v in r.coefs.items() if v != 0}
    for j in used:
        g, c = gens[j], y[j]
        quantity = dict(g.a)
        if g.b != 0:
            quantity[0] = g.b
        for k, v in quantity.items():
            remainder[k] = remainder.get(k, Fraction(0)) - c * v
            if remainder[k] == 0:
                del remainder[k]
        name = describe_generator(g, names, sources)
        terms.append((c, name))
        is_constraint = g.kind == "constraint"
        bare = name if is_constraint else chop_relation(name)
        nconstraints += 1 if is_constraint else 0
        steps.append(ProofStep(
            coefficient=c,
            name=bare,
            label=f"C{nconstraints}" if is_constraint else bare,
            source=bare if is_constraint else "",
            expansion=_format_coefs(quantity, names),
            remainder=_format_coefs(remainder, names),
            remainder_name=name_quantity(remainder, names) or "",
            named=signed_name(quantity, names) or "",
            justification="= 0" if g.equality else ">= 0",
            quantity=quantity,
        ))
    return Proof(
        expression=format_linrel(r, names),
        expression_name=name_quantity(r.coefs, names) or "",
        terms=terms,
        constant=y[len(gens)],
        steps=steps,
        coefficients={k: v for k, v in r.coefs.items() if v != 0},
    )


def _quantity_label(q: Quantity | None) -> str:
    if q is None:
        return ""
    cond = "|" + ",".join(q.cond) if q.cond else ""
    if len(q.parts) == 1:
        return "H(" + ",".join(q.parts[0]) + cond + ")"
    return "I(" + ";".join(",".join(p) for p in q.parts) + cond + ")"


def _expand_with_numbers(coefs: dict, names: list[str], at):
    entries = sorted(coefs.items(), key=lambda p: (p[0] == 0, bin(p[0]).count("1"), p[0]))
    symbols, numbers = [], []
    for S, c in entries:
        if c == 0:
            continue
        sign = ("-" if c < 0 else "") if not symbols else (" - " if c < 0 else " + ")
        mag = abs(c)
        factor = "" if mag == 1 else format_coef(mag) + " "
        symbols.append(sign + factor + (format_coef(mag) if S == 0 else f"H({setname(S, names)})"))
        value = at({S: Fraction(1)})
        numbers.append(sign + factor + format_coef(value))
    return "".join(symbols), "".join(numbers)


def _term_values(statement, names: list[str], at) -> list[TermValue]:
    values: list[TermValue] = []
    if not isinstance(statement, Relation):
        return values
    index = {v: i + 1 for i, v in enumerate(names)}
    for side, terms in (("left", statement.left), ("right", statement.right)):
        for term in terms:
            coefs: dict = {}
            add_term(coefs, index, Term(Fraction(1), term.quantity), 1)
            expansion, substitution = _expand_with_numbers(coefs, names, at)
            values.append(TermValue(
                coefficient=term.coef,
                quantity=_quantity_label(term.quantity),
                value=at(coefs),
                side=side,
                expansion=expansion,
                substitution=substitution,
            ))
    return values


def make_counterexample(z: list[Fraction], r: LinRel, names: list[str], D: int,
                         statement, text: str) -> Counterexample:
    s = -z[D]
    direction = s == 0
    h = [-zv for zv in z[1:D]] if direction else [-zv / s for zv in z[1:D]]

    def at(coefs: dict) -> Fraction:
        total = Fraction(0)
        for S, c in coefs.items():
            if S == 0:
                if not direction:
                    total += c
            else:
                total += c * h[S - 1]
        return total

    return Counterexample(
        expression=format_linrel(r, names),
        var_names=names,
        entropies=h,
        value=at(r.coefs),
        direction=direction,
        statement=text,
        terms=_term_values(statement, names, at),
        relation=RELATION_TEXT[statement.rel] if isinstance(statement, Relation) else "",
    )


# ---------------------------------------------------------------------------
# Printing
# ---------------------------------------------------------------------------

def _side_total(c: Counterexample, side: str) -> Fraction:
    return sum((t.coefficient * t.value for t in c.terms if t.side == side), Fraction(0))


def _term_text(t: TermValue) -> str:
    if not t.quantity:
        return format_coef(t.coefficient)
    prefix = "" if t.coefficient == 1 else format_coef(t.coefficient) + " "
    return prefix + t.quantity


def format_proof(p: Proof) -> str:
    lines = [f"Proof of  {p.expression}:"]
    for c, what in p.terms:
        lines.append(f"    {format_coef(c):>6} * ( {what} )")
    if p.constant != 0:
        lines.append(f"    {format_coef(p.constant):>6}     (constant)")
    return "\n".join(lines)


def format_counterexample(c: Counterexample) -> str:
    lines = [f"No proof of  {c.expression}; it fails for the "
             f"{'direction' if c.direction else 'entropies'}:"]
    n = len(c.var_names)
    for S in range(1, (1 << n)):
        lines.append(f"    H({setname(S, c.var_names)}) = {format_coef(c.entropies[S - 1])}")
    lines.append(f"  which satisfy every elemental inequality and constraint, "
                 f"but give {format_coef(c.value)} < 0.")
    if c.terms:
        lines.append("  There the statement reads")
        rows = []
        for side in ("left", "right"):
            terms = [t for t in c.terms if t.side == side]
            if not terms:
                continue
            total = _side_total(c, side)
            sum_text = " + ".join(format_coef(t.coefficient * t.value) for t in terms)
            label = "left side" if side == "left" else "right side"
            expr = " + ".join(_term_text(t) for t in terms)
            value = format_coef(total) if len(terms) == 1 else f"{sum_text}  =  {format_coef(total)}"
            rows.append((label, expr, value))
        w0 = max(len(r[0]) for r in rows)
        w1 = max(len(r[1]) for r in rows)
        for a, b, cval in rows:
            lines.append(f"    {a.ljust(w0)}  {b.ljust(w1)}  =  {cval}")
        lines.append(f"  so it asks for {format_coef(_side_total(c, 'left'))} "
                     f"{c.relation} {format_coef(_side_total(c, 'right'))}, which is false.")
        lines.append("  where")
        w = (max(len(t.quantity) for t in c.terms),
             max(len(t.expansion) for t in c.terms),
             max(len(t.substitution) for t in c.terms))
        for t in c.terms:
            lines.append(f"    {t.quantity.ljust(w[0])}  =  {t.expansion.ljust(w[1])}  =  "
                         f"{t.substitution.ljust(w[2])}  =  {format_coef(t.value)}")
    if c.direction:
        lines.append("  Any positive multiple of these values fails in the same way.")
    return "\n".join(lines)


def format_result(r: Result) -> str:
    lines = ["TRUE" if r.verdict else "NOT PROVABLE (false or non-Shannon-type)"]
    for c in r.certificates:
        lines.append(format_proof(c) if isinstance(c, Proof) else format_counterexample(c))
    if not r.certificates:
        lines.append("  (no certificate: decided by the simplex method)")
    return "\n".join(lines)


def print_proof(x, file=sys.stdout) -> None:
    """Print a Proof, Counterexample or Result as a step-by-step
    derivation: each step subtracts one non-negative quantity from the
    expression and shows what is left, until nothing (or a non-negative
    constant) remains.
    """
    if isinstance(x, Result):
        if not x.certificates:
            verdict = "TRUE" if x.verdict else "NOT PROVABLE"
            print(f"{verdict} (no certificate: decided by the simplex method)", file=file)
            return
        for i, c in enumerate(x.certificates):
            if i:
                print(file=file)
            print_proof(c, file=file)
        return
    if isinstance(x, Counterexample):
        print(format_counterexample(x), file=file)
        return
    p = x
    expr = chop_relation(p.expression)
    head = f"Proof of  E >= 0  where  E = {expr}"
    print(head + ("" if not p.expression_name else f"  =  {p.expression_name}"), file=file)
    print(file=file)
    if not p.steps:
        if p.constant == 0:
            print("  E is identically 0, hence E >= 0.", file=file)
        else:
            print(f"  E is the constant {format_coef(p.constant)} >= 0.", file=file)
        return
    print(f"  E  =  {expr}", file=file)
    parts: list[str] = []
    for s in p.steps:
        parts.append(s.label if s.coefficient == 1 else f"{format_coef(s.coefficient)} {s.label}")
        rest = "" if s.remainder == "0" else f"  +  [ {s.remainder} ]"
        print(f"     =  {'  +  '.join(parts)}{rest}", file=file)
    print(file=file)
    print("  where every term is non-negative:", file=file)
    label_width = max(len(s.label) for s in p.steps)
    body_width = max(len(s.expansion) for s in p.steps)
    named_width = max((len(s.named) if s.named != s.label else 0) for s in p.steps)
    for s in p.steps:
        line = f"    {s.label.ljust(label_width)}  =  {s.expansion.ljust(body_width)}"
        named = "" if (not s.named or s.named == s.label) else s.named
        if named_width > 0:
            line += (" " * (named_width + 5)) if not named else f"  =  {named.ljust(named_width)}"
        line += f"  {s.justification}"
        if s.source:
            line += f"   ({s.source})"
        print(line, file=file)
    print(file=file)
    if p.constant == 0:
        print("  so E is a sum of non-negative terms, hence E >= 0.", file=file)
    else:
        print(f"  and the constant {format_coef(p.constant)} >= 0, hence E >= 0.", file=file)


# ---------------------------------------------------------------------------
# prove / explain / count_variables
# ---------------------------------------------------------------------------

def prove(*lines: str, method: str = "auto") -> bool:
    """Check whether the first statement is a Shannon-type consequence of
    the remaining ones (the constraints). False means the statement is
    either false or a non-Shannon-type inequality. Raises XitipError for
    contradictory constraints and SyntaxError_ for invalid input.
    """
    return explain(*lines, method=method).verdict


def explain(*lines: str, method: str = "auto") -> Result:
    """Like prove(), but also returns the exactly verified certificates: a
    Proof for each part of a true statement, or one Counterexample.
    """
    stmts, sources = parse_statements(list(lines))
    P = Problem.build(stmts, sources)
    n = len(P.var_names)
    from .generators import generators as build_generators
    gens = build_generators(P)
    D = 1 << n
    if P.constraints and implied(gens, n, {0: Fraction(-1)}, method):
        raise XitipError("the constraints are contradictory")
    proofs: list[Certificate] = []
    for r in P.inquiries:
        for rel in ((r, negate(r)) if r.equality else (r,)):
            verdict, cert = decide(gens, n, rel.coefs, method)
            if not verdict:
                if cert is None:
                    return Result(False, [])
                z = simplify_certificate(gens, n, rel.coefs, cert, D)
                return Result(False, [make_counterexample(z, rel, P.var_names, D,
                                                           stmts[0], sources[0])])
            if cert is not None:
                proofs.append(make_proof(cert, gens, rel, P.var_names, P.sources))
    return Result(True, proofs)


def count_variables(*lines: str) -> int:
    """Number of distinct random variables in all statements."""
    from .parser import parse_lines
    return len(_variables(parse_lines(list(lines))))
