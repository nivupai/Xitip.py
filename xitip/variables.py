"""Distinct variable names appearing in a set of statements."""
from .parser import FunctionOf, MarkovChain, MutualIndependence, Quantity, Relation


def _varlists_of(stmt):
    if isinstance(stmt, Relation):
        result = []
        for t in (*stmt.left, *stmt.right):
            if t.quantity is not None:
                result.extend(_varlists_of_quantity(t.quantity))
        return result
    if isinstance(stmt, (MarkovChain, MutualIndependence)):
        return stmt.parts
    if isinstance(stmt, FunctionOf):
        return [stmt.func, stmt.of]
    raise TypeError(f"unknown statement type {type(stmt)!r}")


def _varlists_of_quantity(q: Quantity):
    return [*q.parts, q.cond]


def variables(stmts) -> list[str]:
    """Distinct variable names, in order of first appearance."""
    names: list[str] = []
    seen: set[str] = set()
    for s in stmts:
        for vl in _varlists_of(s):
            for v in vl:
                if v not in seen:
                    seen.add(v)
                    names.append(v)
    return names
