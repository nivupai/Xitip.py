# xitip (Python)

Information Theoretic Inequality Prover — a Pythonic port of the **core**
of [Xitip.jl](https://github.com/nivupai/Xitip.jl): the parser, the
exact-rational solver, and the proof/counterexample certificate machinery.

Decides whether an expression over entropies and mutual informations of
discrete random variables follows from the basic properties of Shannon
entropy, optionally under constraints such as Markov chains, independence,
or functional dependence. Every answer is exact (no floating point
tolerance decides the verdict — coefficients are exact `fractions.Fraction`
values) and comes with a certificate: a proof that writes the expression as
a non-negative combination of basic inequalities, or a counterexample.

Not ported from the original: the Lean export (`lean.jl`) and the Makie
plotting extension — this port covers the prover engine, the CLI, and
certificate printing only.

## Install

```bash
pip install -e .
```

## Use

```python
>>> from xitip import prove, explain
>>> prove("I(X;Y|Z) <= I(X;Y)", "H(Z) = 0")
True
>>> print(explain("H(X,Y) <= H(X) + H(Y)"))
TRUE
Proof of  H(X) + H(Y) - H(X,Y) >= 0:
     1 * ( I(X;Y) >= 0 )
```

## Syntax

```
H(X,Y|Z)                  (conditional) joint entropy
I(X;Y;Z|W)  I(X:Y)        (conditional, multivariate) mutual information
2 H(X) - 0.5 I(X;Y) >= 1  linear combinations; relations <= >= =
X/Y/Z                     Markov chain
X.Y.Z                     mutual independence
X:Y,Z                     X is a function of Y,Z
# ...                     comment
```

## CLI

```bash
xitip "I(X;Y|Z) <= I(X;Y)" "H(Z) = 0"
xitip --steps "H(X,Y) <= H(X) + H(Y)"
```

## Tests

```bash
pip install pytest
pytest tests/
```
