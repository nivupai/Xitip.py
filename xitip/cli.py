"""Command line interface."""
from __future__ import annotations

import sys

from .api import count_variables, explain, format_result, print_proof
from .errors import SyntaxError_, XitipError

USAGE = """\
usage: xitip [options] EXPR [CONSTRAINT ...] [-]

Information Theoretic Inequality Prover. Checks whether the first
expression is a Shannon-type consequence of the remaining ones. Expressions
are read from STDIN (one per line) if none are given or the last argument
is '-'.

Syntax:
  H(X,Y|Z)                  (conditional) joint entropy
  I(X;Y;Z|W)  I(X:Y)        (conditional, multivariate) mutual information
  2 H(X) - 0.5 I(X;Y) >= 1  linear combinations; relations <= >= =
  X/Y/Z                     Markov chain
  X.Y.Z                     mutual independence
  X:Y,Z                     X is a function of Y,Z
  # ...                     comment

Options:
  -p, --proof     print the proof, or the counterexample if there is none
  -s, --steps     print the proof as a step-by-step derivation
  -c, --count     print the number of distinct random variables instead
      --simplex   decide with the exact simplex method only (slow, for
                  cross-checking)
  -q, --quiet     print nothing, only set the exit code
  -v, --version   print the version
  -h, --help      print this message

Exit codes:
  0  TRUE (or --count succeeded)
  1  FALSE or a non-Shannon-type inequality
  2  error (syntax error, contradictory constraints, ...)
  3  internal error
"""

VERSION_STRING = "0.1.0"


def main(args: list[str] | None = None, out=sys.stdout, err=sys.stderr) -> int:
    """Run the command line interface and return the exit code."""
    if args is None:
        args = sys.argv[1:]
    count = proof = steps = quiet = False
    use_stdin = len(args) == 0
    method = "auto"
    exprs: list[str] = []
    for a in args:
        if a in ("-h", "--help"):
            print(USAGE, end="", file=out)
            return 0
        elif a in ("-v", "--version"):
            print(f"xitip-py {VERSION_STRING}", file=out)
            return 0
        elif a in ("-c", "--count"):
            count = True
        elif a in ("-p", "--proof"):
            proof = True
        elif a in ("-s", "--steps"):
            steps = True
        elif a in ("-q", "--quiet"):
            quiet = True
        elif a == "--simplex":
            method = "simplex"
        elif a == "-":
            use_stdin = True
        elif a.startswith("--") or (a.startswith("-") and len(a) > 1
                                     and a[1].isalpha() and not any(c in a for c in "(;|")):
            print(f"ERROR: unknown option {a}\n\n{USAGE}", file=err)
            return 2
        else:
            exprs.append(a)

    use_stdin = use_stdin or not exprs
    if use_stdin:
        exprs.extend(line.rstrip("\n") for line in sys.stdin)

    def say(*msg):
        if not quiet:
            print(*msg, file=out)

    try:
        if count:
            say(count_variables(*exprs))
            return 0
        result = explain(*exprs, method=method)
        if steps and not quiet:
            print_proof(result, file=out)
        elif proof and not quiet:
            print(format_result(result), file=out)
        elif result.verdict:
            say("The information expression is TRUE.")
        else:
            say("The information expression is either:\n"
                "    1. FALSE, or\n"
                "    2. a non-Shannon type inequality")
        return 0 if result.verdict else 1
    except (XitipError, SyntaxError_) as e:
        if not quiet:
            print(f"ERROR: {e}", file=err)
        return 2
    except Exception as e:  # pragma: no cover - defensive, like the Julia CLI
        if not quiet:
            print(f"INTERNAL ERROR: {e}", file=err)
        return 3


if __name__ == "__main__":
    sys.exit(main())
