"""Ported from Xitip.jl's test/prover.jl."""
import pytest

from xitip import XitipError, prove


def test_basic_shannon_inequalities():
    assert prove("H(X) >= 0")
    assert prove("I(X;Y) >= 0")
    assert prove("I(X;Y|Z) >= 0")
    assert prove("H(X,Y) <= H(X) + H(Y)")
    assert prove("H(X|Y) <= H(X)")
    assert prove("H(X,Y) = H(X) + H(Y|X)")                 # chain rule
    assert prove("I(X;Y) = H(X) + H(Y) - H(X,Y)")
    assert prove("I(X;Y,Z) = I(X;Y) + I(X;Z|Y)")            # chain rule for I
    assert prove("H(X,Y,Z) <= H(X,Y) + H(Y,Z) - H(Y)") == prove("I(X;Z|Y) >= 0")
    assert prove("2 H(X,Y,Z) <= H(X,Y) + H(Y,Z) + H(X,Z)")  # Han's inequality


def test_not_provable():
    assert not prove("H(X) >= 1")
    assert not prove("H(X) <= H(Y)")
    assert not prove("I(X;Y|Z) <= I(X;Y)")
    assert not prove("I(X;Y|Z) >= I(X;Y)")
    assert not prove("I(X;Y;Z) >= 0")                # can be negative
    assert not prove("H(X,Y) = H(X) + H(Y)")
    # Zhang-Yeung and Ingleton: valid resp. invalid, but not Shannon-type
    assert not prove("2I(C;D) <= I(A;B) + I(A;C,D) + 3I(C;D|A) + I(C;D|B)")
    assert not prove("I(A;B) <= I(A;B|C) + I(A;B|D) + I(C;D)")


def test_constraints():
    assert prove("I(X;Y|Z) <= I(X;Y)", "H(Z) = 0")
    assert prove("I(X;Z) <= I(X;Y)", "X/Y/Z")           # data processing
    assert prove("I(A;D) <= I(B;C)", "A/B/C/D")
    assert prove("I(X;Y) = 0", "X.Y")
    assert prove("X.Y.Z", "I(X;Y,Z) = 0", "I(Y;Z) = 0")
    assert prove("H(X,Y) = H(Y)", "X:Y")
    assert prove("X:Y,Z", "H(X|Y,Z) = 0")
    assert prove("H(X) >= 1", "H(X) >= 2")
    assert prove("H(X) >= 1", "H(X) = 2")
    assert not prove("H(X) >= 3", "H(X) = 2")
    assert prove("H(X) <= 2.5", "H(X,Y) <= 2.5")
    assert prove("X/Y/Z", "X/Y/Z")                      # inquiry equals constraint
    assert prove("X/Y/Z", "I(X;Z|Y) = 0")               # statements as inquiries
    assert prove("A/B/C/D", "I(A;C|B) = 0", "I(A,B;D|C) = 0")
    assert not prove("A/B/C/D", "I(A;C|B) = 0")
    assert not prove("X/Y/Z")
    assert not prove("X.Y")
    assert not prove("X:Y")
    # constraints must not be stronger than they should be
    assert not prove("H(Y) = 0", "X/Y/Z")
    assert not prove("I(X;Y) = 0", "X/Y/Z")
    assert not prove("H(X) = 0", "X.Y")
    assert not prove("H(X) = 0", "X:Y")
    assert not prove("H(Y|X) = 0", "X:Y")
    with pytest.raises(XitipError):
        prove("H(X) >= 0", "H(X) = 1", "H(X) = 2")
    with pytest.raises(XitipError):
        prove("H(X) >= 0", "0 >= 1")


def test_exact_arithmetic():
    # 0.1 + 0.2 != 0.3 in floating point
    assert prove("0.1 H(X) + 0.2 H(X) >= 0.3 H(X)")
    assert prove("0.1 H(X) + 0.2 H(X) = 0.3 H(X)")
    assert prove("H(X) >= 1.00000001", "H(X) = 1.00000001")
    assert not prove("H(X) >= 1.00000001", "H(X) = 1")
    assert prove(".5 H(X) <= H(X)")


def test_degenerate_inputs():
    assert prove("1 >= 0")
    assert not prove("0 >= 1")
    assert prove("2 = 2")
    assert prove("H(X) - H(X) = 0")
    assert prove("H(X|X) = 0")
    assert prove("I(X;X) = H(X)")


def test_larger_problems():
    for n in range(5, 9):
        v = [f"X{i}" for i in range(1, n + 1)]
        assert prove("H(" + ",".join(v) + ") <= " + " + ".join(f"H({x})" for x in v))
        assert not prove("I(X1;X2) <= I(X1;X2|" + ",".join(v[2:]) + ")")
    # the simplex method agrees where it is fast enough
    for n in range(5, 7):
        v = [f"X{i}" for i in range(1, n + 1)]
        e = ("I(X1;X2) <= I(X1;X2|X3) + I(X1;X2|X4) + I(X3;X4) + H(" +
             ",".join(v[4:]) + ")")
        assert prove(e) == prove(e, method="simplex")
