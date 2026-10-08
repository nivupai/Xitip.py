"""Ported from Xitip.jl's test/quantities.jl."""
import io

from xitip import Proof, explain, print_proof
from xitip.parser import parse_statements
from xitip.quantities import name_quantity
from xitip.relations import Problem


def named(expr: str):
    stmts, sources = parse_statements([expr + " >= 0"])
    P = Problem.build(stmts, sources)
    return name_quantity(P.inquiries[0].coefs, P.var_names)


def test_recognising_information_quantities():
    assert named("H(X)") == "H(X)"
    assert named("H(X,Y)") == "H(X,Y)"
    assert named("H(X,Y) - H(Y)") == "H(X|Y)"
    assert named("H(X,Y,Z) - H(Z)") == "H(X,Y|Z)"
    assert named("H(X) + H(Y) - H(X,Y)") == "I(X;Y)"
    assert named("H(X,Z) + H(Y,Z) - H(Z) - H(X,Y,Z)") == "I(X;Y|Z)"
    assert named("H(X,W) + H(Y,Z,W) - H(W) - H(X,Y,Z,W)") == "I(X;Y,Z|W)"
    # the same quantities written directly
    assert named("H(X|Y)") == "H(X|Y)"
    assert named("I(X;Y|Z)") == "I(X;Y|Z)"
    assert named("I(X,Y;Z|W)") == "I(X,Y;Z|W)"
    # positive multiples keep the factor
    assert named("2 H(X,Z) + 2 H(Y,Z) - 2 H(Z) - 2 H(X,Y,Z)") == "2 I(X;Y|Z)"
    assert named("0.5 H(X) + 0.5 H(Y) - 0.5 H(X,Y)") == "1/2 I(X;Y)"

    # not single quantities
    assert named("H(X) - H(Y)") is None               # Y is not a subset of X
    assert named("H(X) + H(Y)") is None
    assert named("H(X) + H(Y) - H(X,Y) + 1") is None   # constant term
    assert named("H(X) + H(Y) + H(Z) - H(X,Y,Z)") is None
    assert named("-H(X)") is None                      # negative multiple
    assert named("-I(X;Y)") is None
    assert named("H(X) + H(Y) + H(Z) - H(X,Y) - H(X,Z) - H(Y,Z) + H(X,Y,Z)") is None
    assert named("0") is None
    assert named("H(X) + H(Y) - H(X,Y,Z)") is None      # not the union
    assert named("H(X) + H(X,Y) - H(Y)") is None        # overlapping sets
    assert named("H(X,Y) - 1") is None                  # constant term
    assert named("H(X) + H(Y) - H(X,Y) + 2 H(Z)") is None  # extra term

    # shown in proofs next to the raw form
    buf = io.StringIO()
    print_proof(explain("H(X,Y,Z) <= H(X,Y) + H(Z)"), file=buf)
    out = buf.getvalue()
    assert "E = H(Z) + H(X,Y) - H(X,Y,Z)  =  I(X,Y;Z)" in out
    assert "[ H(Y) + H(Z) - H(Y,Z) ]" in out
    assert "+  I(Y;Z)" in out
    # an expression that is not a single quantity shows only the raw form
    buf = io.StringIO()
    print_proof(explain("I(X;Z) <= I(X;Y)", "X/Y/Z"), file=buf)
    out = buf.getvalue()
    assert "E = -H(Z) + H(Y) + H(X,Z) - H(X,Y)\n" in out
    assert "[ -H(Z) + H(X,Z) + H(Z,Y) - H(X,Z,Y) ]" in out
    assert "+  I(X;Y|Z)" in out

    # naming costs nothing noticeable on a large problem
    certs = explain("H(X1,X2,X3,X4,X5,X6) <= H(X1)+H(X2)+H(X3)+H(X4)+H(X5)+H(X6)").certificates
    assert len(certs) == 1 and isinstance(certs[0], Proof)
