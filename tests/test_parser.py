"""Ported from Xitip.jl's test/parser.jl."""
import pytest

from xitip import SyntaxError, XitipError, count_variables, prove


def test_syntax():
    assert prove("I(X:Y) >= 0") == prove("I(X;Y) >= 0")
    assert prove("H(X) >= 0 # comment")
    assert prove("H(X) >= 0\r")                       # CRLF input
    assert prove("I (X;Y) >= 0")                      # blank before '('
    assert prove("H(X) == H(X)")
    assert prove("-H(X) <= 0")
    assert prove("", "# only comments", "H(X) >= 0")  # first statement
    assert prove("H(H1, I1) >= H(H1)")                # names starting with H/I
    with pytest.raises(XitipError):
        prove("")
    with pytest.raises(XitipError):
        prove(*["# nothing"])
    for bad in ["I(X;;Y) >= 0", "H(X) >=", "H(X) > 0", "X/Y", "H(X)>=1e-3",
                "I(X) >= 0", "H(X;Y) >= 0", "2 X >= 0", "H() >= 0", "H(X) >= 0)"]:
        with pytest.raises(SyntaxError):
            prove(bad)
    try:
        prove("I(X;;Y|Z) <= I(X;Y)")
        e = None
    except SyntaxError as exc:
        e = exc
    assert e.col == 5 and e.len == 1
    assert "in row 1 col 5" in e.msg
    try:
        prove("H(X)>=0", "H(Y) >= %")
        e = None
    except SyntaxError as exc:
        e = exc
    assert "in row 2 col 9" in e.msg


def test_count_variables():
    assert count_variables("1 >= 0") == 0
    assert count_variables("H(X) >= 0") == 1
    assert count_variables("I(X;Y|Z) <= I(X;Y)") == 3
    assert count_variables("I(X;Y|Z) <= I(X;Y)", "H(W) = 0") == 4
    assert count_variables("", "# comment", "A/B/C/D") == 4
    # more than MAX_VARS is fine for counting
    assert count_variables("H(" + ",".join(f"X{i}" for i in range(1, 41)) + ") >= 0") == 40


def test_too_many_variables():
    with pytest.raises(XitipError):
        prove("H(" + ",".join(f"X{i}" for i in range(1, 32)) + ") >= 0")
