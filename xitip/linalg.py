"""Exact linear algebra and the exact (two-phase) simplex method."""
from __future__ import annotations

from fractions import Fraction


def exact_solve(M: list[list[Fraction]], rhs: list[Fraction]) -> list[Fraction] | None:
    """Solve ``M y = rhs`` exactly by Gauss-Jordan elimination.

    ``M`` may be non-square or singular; free variables are set to zero.
    Returns ``None`` if the system is inconsistent.
    """
    R = len(M)
    C = len(M[0]) if R else 0
    aug = [row[:] + [rhs[i]] for i, row in enumerate(M)]
    pivots: list[int] = []
    row = 0
    for col in range(C):
        if row >= R:
            break
        p = None
        for i in range(row, R):
            if aug[i][col] != 0:
                p = i
                break
        if p is None:
            continue
        if p != row:
            aug[row], aug[p] = aug[p], aug[row]
        piv = aug[row][col]
        aug[row] = [x / piv for x in aug[row]]
        for i in range(R):
            if i == row:
                continue
            f = aug[i][col]
            if f != 0:
                aug[i] = [a - f * b for a, b in zip(aug[i], aug[row])]
        pivots.append(col)
        row += 1
    for i in range(row, R):
        if aug[i][-1] != 0:
            return None
    y = [Fraction(0)] * C
    for i, col in enumerate(pivots):
        y[col] = aug[i][-1]
    return y


# ---------------------------------------------------------------------------
# Exact two-phase simplex method
# ---------------------------------------------------------------------------

MAX_DEGENERATE = 50   # consecutive degenerate pivots before switching to Bland's rule


def simplex(A: list[list[Fraction]], b: list[Fraction],
            c: list[Fraction]) -> tuple[str, Fraction]:
    """Solve ``min c.x s.t. A x = b, x >= 0`` with the two-phase tableau
    simplex method in exact arithmetic.

    Returns ``(status, value)`` with status one of "optimal", "infeasible"
    or "unbounded".
    """
    m = len(A)
    n = len(A[0]) if m else 0

    # Phase 1: tableau [A I | b] with b >= 0 and artificial basis.
    W = [[Fraction(0)] * (n + m + 1) for _ in range(m)]
    for i in range(m):
        s = Fraction(-1) if b[i] < 0 else Fraction(1)
        for j in range(n):
            W[i][j] = s * A[i][j]
        W[i][n + i] = Fraction(1)
        W[i][-1] = s * b[i]
    basis = list(range(n, n + m))
    cost1 = [Fraction(0)] * n + [Fraction(1)] * m
    _, infeas = _run_simplex(W, basis, cost1, n + m)
    if infeas > 0:
        return ("infeasible", Fraction(0))

    # Drive the (zero valued) artificial variables out of the basis. Rows
    # where that is impossible are linearly dependent and can be dropped.
    keep = [True] * m
    for i in range(m):
        if basis[i] <= n - 1:
            continue
        j = next((j for j in range(n) if W[i][j] != 0), None)
        if j is None:
            keep[i] = False
        else:
            _pivot(W, None, basis, i, j)
    cols = list(range(n)) + [n + m]
    W = [[row[j] for j in cols] for i, row in enumerate(W) if keep[i]]
    basis = [basis[i] for i in range(m) if keep[i]]

    # Phase 2
    return _run_simplex(W, basis, c, n)


def _run_simplex(W: list[list[Fraction]], basis: list[int],
                  cost: list[Fraction], ncols: int) -> tuple[str, Fraction]:
    m = len(W)
    last = len(W[0]) if m else 0
    # Reduced costs; z[-1] is minus the objective value.
    z = [Fraction(0)] * last
    for j in range(ncols):
        z[j] = cost[j]
    for i in range(m):
        cb = cost[basis[i]]
        if cb == 0:
            continue
        for j in range(last):
            z[j] -= cb * W[i][j]
    degenerate = 0
    while True:
        # Entering column: the most negative reduced cost (Dantzig's rule)
        # needs far fewer pivots than Bland's rule (lowest index with
        # negative reduced cost), but can cycle at degenerate vertices.
        # After a run of degenerate pivots, use Bland's rule until the
        # objective improves again; this guarantees termination.
        q = -1
        if degenerate >= MAX_DEGENERATE:
            q = next((j for j in range(ncols) if z[j] < 0), -1)
        else:
            zmin = Fraction(0)
            for j in range(ncols):
                if z[j] < zmin:
                    q, zmin = j, z[j]
        if q == -1:
            return ("optimal", -z[-1])
        # Leaving row: minimum ratio (ties: lowest basis index, Bland's rule).
        r = -1
        best = Fraction(0)
        for i in range(m):
            if W[i][q] <= 0:
                continue
            ratio = W[i][-1] / W[i][q]
            if r == -1 or ratio < best or (ratio == best and basis[i] < basis[r]):
                r, best = i, ratio
        if r == -1:
            return ("unbounded", Fraction(0))
        degenerate = degenerate + 1 if best == 0 else 0
        _pivot(W, z, basis, r, q)


def _pivot(W: list[list[Fraction]], z: list[Fraction] | None,
           basis: list[int], r: int, q: int) -> None:
    cols = [j for j in range(len(W[r])) if W[r][j] != 0]
    piv = W[r][q]
    for j in cols:
        W[r][j] /= piv
    for i in range(len(W)):
        if i == r:
            continue
        f = W[i][q]
        if f == 0:
            continue
        for j in cols:
            W[i][j] -= f * W[r][j]
    if z is not None:
        f = z[q]
        if f != 0:
            for j in cols:
                z[j] -= f * W[r][j]
    basis[r] = q


# ---------------------------------------------------------------------------
# Non-negative least squares
# ---------------------------------------------------------------------------

def _norm(v) -> float:
    return sum(x * x for x in v) ** 0.5


def nnls(A: list[list[float]], b: list[float]):
    """Lawson-Hanson active set method for ``min ||A x - b|| s.t. x >= 0``.

    ``A`` is given column-major as a list of columns (each a list of floats)
    for convenience here. Returns ``(x, passive)`` or ``None`` if it does
    not converge (rounding errors).
    """
    m = len(b)
    N = len(A)       # number of columns
    tol = 1e-10 * max(1.0, _norm(b))
    x = [0.0] * N
    passive = [False] * N

    def matvec(cols, xs):
        out = [0.0] * m
        for j, col in enumerate(cols):
            xj = xs[j]
            if xj == 0.0:
                continue
            for i in range(m):
                out[i] += col[i] * xj
        return out

    def dot(u, v):
        return sum(a * b_ for a, b_ in zip(u, v))

    w = [dot(A[j], b) for j in range(N)]
    iters = 0
    while True:
        t, wmax = -1, tol
        for j in range(N):
            if not passive[j] and w[j] > wmax:
                t, wmax = j, w[j]
        if t == -1:
            return x, passive
        passive[t] = True
        while True:
            iters += 1
            if iters > 3 * N:
                return None
            idx = [j for j in range(N) if passive[j]]
            s = _least_squares(A, idx, b, m)
            if s is None:
                return None
            if all(v > 0 for v in s):
                x = [0.0] * N
                for k, j in enumerate(idx):
                    x[j] = s[k]
                break
            candidates = [x[j] / (x[j] - s[k]) for k, j in enumerate(idx) if s[k] <= 0]
            alpha = min(candidates)
            for k, j in enumerate(idx):
                x[j] += alpha * (s[k] - x[j])
                if x[j] <= 1e-12:
                    x[j] = 0.0
                    passive[j] = False
        ax = matvec(A, x)
        resid = [b[i] - ax[i] for i in range(m)]
        w = [dot(A[j], resid) for j in range(N)]


def _least_squares(A, idx, b, m):
    """Least-squares solution of A[:, idx] s ~= b via normal equations."""
    k = len(idx)
    if k == 0:
        return []
    # Build k x k normal-equation matrix and right-hand side.
    AtA = [[sum(A[idx[p]][i] * A[idx[q]][i] for i in range(m)) for q in range(k)]
           for p in range(k)]
    Atb = [sum(A[idx[p]][i] * b[i] for i in range(m)) for p in range(k)]
    return _solve_float(AtA, Atb)


def _solve_float(M: list[list[float]], rhs: list[float]):
    n = len(M)
    aug = [row[:] + [rhs[i]] for i, row in enumerate(M)]
    for col in range(n):
        piv_row = max(range(col, n), key=lambda i: abs(aug[i][col]))
        if abs(aug[piv_row][col]) < 1e-14:
            return None
        aug[col], aug[piv_row] = aug[piv_row], aug[col]
        piv = aug[col][col]
        aug[col] = [v / piv for v in aug[col]]
        for i in range(n):
            if i == col:
                continue
            f = aug[i][col]
            if f != 0:
                aug[i] = [a - f * bb for a, bb in zip(aug[i], aug[col])]
    return [aug[i][-1] for i in range(n)]
