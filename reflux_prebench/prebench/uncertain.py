"""Uncertainty primitives.

Every physical quantity used by the pre-bench model carries three things that must
never be separated from its value:

  * a range (not a point),
  * a provenance status (where the number came from), and
  * a citation string.

This is a direct implementation of the programme rule "do not hide several unknowns
inside one fitted number".  A quantity with status UNMEASURED is not allowed to be
quietly promoted to a design constant: the report renders it as an interval and the
closure logic propagates its full width.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Sequence

import numpy as np


class Status(str, Enum):
    """Provenance of a quantity.  Ordered from strongest to weakest evidence."""

    #: Measured on this programme's own bench.  Nothing has this status yet.
    MEASURED = "MEASURED"
    #: Taken from external peer-reviewed or standards literature.
    PUBLISHED = "PUBLISHED"
    #: Computed from other entries in this table by a declared formula.
    DERIVED = "DERIVED"
    #: A model-internal result from this programme's own simulations.  Not evidence
    #: about urine, ureters, or children.
    SIMULATED = "SIMULATED"
    #: A modelling choice with no evidential support.  Must be swept, never trusted.
    ASSUMED = "ASSUMED"
    #: Genuinely unknown.  Bracket is deliberately wide and usually log-uniform.
    UNMEASURED = "UNMEASURED"

    @property
    def is_evidence(self) -> bool:
        return self in (Status.MEASURED, Status.PUBLISHED)


class Shape(str, Enum):
    """How to sample inside a bracket."""

    UNIFORM = "uniform"
    LOGUNIFORM = "loguniform"
    TRIANGULAR = "triangular"
    POINT = "point"


@dataclass(frozen=True)
class Q:
    """A bracketed quantity.

    ``lo``/``hi`` are hard bounds, ``nom`` is the value a point-estimate model would
    have used.  ``nom`` exists only so that the report can show how far a single-number
    answer sits from the honest interval; no decision rule may read ``nom`` alone.
    """

    name: str
    lo: float
    nom: float
    hi: float
    units: str
    status: Status
    source: str
    shape: Shape = Shape.UNIFORM
    note: str = ""

    def __post_init__(self) -> None:
        if not (self.lo <= self.nom <= self.hi):
            raise ValueError(f"{self.name}: need lo <= nom <= hi, got {self.lo}, {self.nom}, {self.hi}")
        if self.shape is Shape.LOGUNIFORM and self.lo <= 0:
            raise ValueError(f"{self.name}: log-uniform bracket needs lo > 0")

    # -- sampling ---------------------------------------------------------------
    def sample(self, rng: np.random.Generator, n: int) -> np.ndarray:
        if self.shape is Shape.POINT or self.lo == self.hi:
            return np.full(n, self.nom, dtype=float)
        if self.shape is Shape.LOGUNIFORM:
            return np.exp(rng.uniform(math.log(self.lo), math.log(self.hi), n))
        if self.shape is Shape.TRIANGULAR:
            return rng.triangular(self.lo, self.nom, self.hi, n)
        return rng.uniform(self.lo, self.hi, n)

    @property
    def decades(self) -> float:
        """Width of the bracket in decades; a crude 'how ignorant are we' score."""
        if self.lo <= 0 or self.hi <= 0:
            return float("nan")
        return math.log10(self.hi / self.lo)

    def fmt(self, sig: int = 3) -> str:
        def f(x: float) -> str:
            if x == 0:
                return "0"
            if abs(x) < 1e-3 or abs(x) >= 1e5:
                return f"{x:.{sig-1}e}"
            return f"{x:.{max(0, sig - 1 - int(math.floor(math.log10(abs(x)))))}f}"

        if self.lo == self.hi:
            return f"{f(self.nom)} {self.units}"
        return f"{f(self.lo)} – {f(self.hi)} {self.units} (nom {f(self.nom)})"


@dataclass
class Registry:
    """Ordered table of every quantity the model is allowed to use."""

    entries: dict[str, Q] = field(default_factory=dict)

    def add(self, q: Q) -> Q:
        if q.name in self.entries:
            raise KeyError(f"duplicate quantity {q.name}")
        self.entries[q.name] = q
        return q

    def __getitem__(self, name: str) -> Q:
        return self.entries[name]

    def by_status(self, status: Status) -> list[Q]:
        return [q for q in self.entries.values() if q.status is status]

    def unmeasured_load_bearing(self) -> list[Q]:
        """Unknowns wide enough to dominate any conclusion drawn from them."""
        out = []
        for q in self.entries.values():
            if q.status in (Status.UNMEASURED, Status.ASSUMED) and q.lo > 0 and q.decades >= 0.5:
                out.append(q)
        return sorted(out, key=lambda q: -q.decades)


def pct(a: np.ndarray, p: float) -> float:
    return float(np.percentile(a, p))


def interval(a: np.ndarray, mass: float = 0.90) -> tuple[float, float]:
    """Central credible interval of a Monte Carlo sample."""
    tail = (1.0 - mass) / 2.0 * 100.0
    return pct(a, tail), pct(a, 100.0 - tail)


def sweep(fn: Callable[..., np.ndarray], *args: np.ndarray) -> np.ndarray:
    return fn(*args)


def corners(values: Sequence[Sequence[float]]) -> list[tuple[float, ...]]:
    """Full factorial of the supplied level lists (used for worst-corner analysis)."""
    out: list[tuple[float, ...]] = [()]
    for levels in values:
        out = [prev + (v,) for prev in out for v in levels]
    return out
