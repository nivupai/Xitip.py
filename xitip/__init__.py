"""
Xitip: Information Theoretic Inequality Prover (core, Python port).

Decides whether an information expression (over entropies and mutual
informations of discrete random variables) follows from the basic
properties of Shannon entropy, optionally under constraints such as Markov
chains, independence or functional dependence.

This is a Pythonic reimplementation of the *core* of Xitip.jl: the parser,
the exact-rational solver (non-negative least squares verified exactly,
falling back to an exact simplex method) and the certificate-printing
proof/counterexample machinery. It does not port the Lean-export or Makie
plotting extensions of the original.

>>> from xitip import prove, explain
>>> prove("I(X;Y|Z) <= I(X;Y)", "H(Z) = 0")
True
>>> print(explain("H(X,Y) <= H(X) + H(Y)"))
TRUE
Proof of  H(X) + H(Y) - H(X,Y) >= 0:
     1 * ( I(X;Y) >= 0 )
"""
from .api import (Certificate, Counterexample, Proof, ProofStep, Result,
                   TermValue, count_variables, explain, format_counterexample,
                   format_proof, format_result, print_proof, prove)
from .errors import SyntaxError_ as SyntaxError
from .errors import XitipError

__version__ = "0.1.0"

__all__ = [
    "prove", "explain", "print_proof", "count_variables",
    "Result", "Proof", "ProofStep", "Counterexample", "TermValue", "Certificate",
    "format_proof", "format_counterexample", "format_result",
    "XitipError", "SyntaxError",
]


def _repr_result(self: Result) -> str:
    return format_result(self)


Result.__str__ = _repr_result
Result.__repr__ = _repr_result
Proof.__str__ = lambda self: format_proof(self)
Counterexample.__str__ = lambda self: format_counterexample(self)
