"""Euclidean Traveling Salesman Problem family (docs/PROBLEMS.md section 1.1).

Distribution & hardness: n points drawn uniformly at random with integer
coordinates in [0, 1000]^2, Euclidean metric. Uniform random Euclidean
instances are the standard hard-on-average TSP distribution (the
Beardwood-Halton-Hammersley regime): the search space is (n-1)!/2 tours and
no known polynomial algorithm is exact. Ground truth is the *exact* optimum
via Held-Karp dynamic programming, so n is capped at HELD_KARP_MAX_N=16
(O(2^n n^2) is milliseconds-to-seconds there; beyond it we refuse rather
than ship "probably optimal" answers — ARCHITECTURE.md admission criterion 2).

Rejection rule (admission criterion 3): duplicate points are resampled, so
all n points are distinct.

aux stores the optimum plus two classical-baseline tour lengths
(nearest-neighbor from point 0, and 2-opt applied to that tour) so analysis
can ask "does the model beat greedy?".

Scoring is gradated: a valid tour scores opt_length / tour_length in (0, 1];
it is `correct` iff its length is optimal up to 1e-9 relative tolerance.
"""

from __future__ import annotations

import math
import random
from typing import Any

from hard_problems.core import Family, Instance, ParseError, Score, extract_answer_line

HELD_KARP_MAX_N = 16
COORD_MAX = 1000
_REL_TOL = 1e-9


def _sample_points(rng: Any, n: int) -> list[list[int]]:
    """Draw n distinct integer points in [0, COORD_MAX]^2.

    Rejection rule: a draw that duplicates an earlier point is discarded and
    redrawn (duplicates would make the metric degenerate).
    """
    points: list[list[int]] = []
    seen: set[tuple[int, int]] = set()
    while len(points) < n:
        p = (rng.randint(0, COORD_MAX), rng.randint(0, COORD_MAX))
        if p in seen:
            continue
        seen.add(p)
        points.append([p[0], p[1]])
    return points


def _tour_length(points: list[list[int]], tour: list[int]) -> float:
    """Total length of the cyclic tour (includes the closing edge back to start)."""
    n = len(tour)
    return sum(
        math.dist(points[tour[i]], points[tour[(i + 1) % n]]) for i in range(n)
    )


def _held_karp(points: list[list[int]]) -> list[int]:
    """Exact TSP by Held-Karp dynamic programming, O(2^n * n^2).

    dp[mask][j] = length of the shortest path that starts at point 0, visits
    exactly the points in bitmask `mask`, and ends at point j. Returns the
    optimal tour as point indices starting at 0 (closing edge implied).
    """
    n = len(points)
    dist = [[math.dist(p, q) for q in points] for p in points]
    size = 1 << n
    inf = float("inf")
    dp = [[inf] * n for _ in range(size)]
    parent = [[-1] * n for _ in range(size)]
    dp[1][0] = 0.0
    for mask in range(1, size):
        if not mask & 1:
            continue  # every partial path starts at point 0
        for last in range(n):
            here = dp[mask][last]
            if here == inf:
                continue
            for nxt in range(1, n):
                if mask >> nxt & 1:
                    continue
                cand = here + dist[last][nxt]
                new_mask = mask | (1 << nxt)
                if cand < dp[new_mask][nxt]:
                    dp[new_mask][nxt] = cand
                    parent[new_mask][nxt] = last
    full = size - 1
    _, best_last = min((dp[full][j] + dist[j][0], j) for j in range(1, n))
    rev = []
    mask, j = full, best_last
    while j != 0:
        rev.append(j)
        mask, j = mask ^ (1 << j), parent[mask][j]
    return [0] + rev[::-1]


def _nearest_neighbor(points: list[list[int]]) -> list[int]:
    """Greedy baseline: start at 0, always move to the nearest unvisited point
    (ties broken by lowest index, for determinism)."""
    tour = [0]
    unvisited = set(range(1, len(points)))
    while unvisited:
        here = points[tour[-1]]
        nxt = min(unvisited, key=lambda j: (math.dist(here, points[j]), j))
        tour.append(nxt)
        unvisited.remove(nxt)
    return tour


def _two_opt(points: list[list[int]], tour: list[int]) -> list[int]:
    """2-opt local search: repeatedly reverse a segment whenever doing so
    shortens the tour, until no improving reversal exists. Point 0 stays first."""
    tour = list(tour)
    n = len(tour)
    dist = lambda a, b: math.dist(points[a], points[b])  # noqa: E731
    improved = True
    while improved:
        improved = False
        for i in range(1, n - 1):
            for j in range(i + 1, n):
                a, b = tour[i - 1], tour[i]
                c, d = tour[j], tour[(j + 1) % n]
                if dist(a, c) + dist(b, d) < dist(a, b) + dist(c, d) - 1e-12:
                    tour[i : j + 1] = tour[i : j + 1][::-1]
                    improved = True
    return tour


class TSPFamily(Family):
    name = "tsp"
    version = "1.0"
    difficulty_params = {"n": [5, 8, 11, 14]}

    def generate(self, seed: int, n: int = 8) -> Instance:
        if not 3 <= n <= HELD_KARP_MAX_N:
            raise ValueError(
                f"n must be in [3, {HELD_KARP_MAX_N}] (exact Held-Karp ground "
                f"truth only; see module docstring), got {n}"
            )
        rng = random.Random(seed)
        points = _sample_points(rng, n)
        opt_tour = _held_karp(points)
        nn_tour = _nearest_neighbor(points)
        return Instance(
            family=self.name,
            family_version=self.version,
            seed=seed,
            difficulty={"n": n},
            data={"points": points},
            answer=opt_tour,
            aux={
                # opt_length is recomputed with _tour_length so it is
                # bit-identical to what score() recomputes for the same tour.
                "opt_length": _tour_length(points, opt_tour),
                "nn_length": _tour_length(points, nn_tour),
                "two_opt_length": _tour_length(points, _two_opt(points, nn_tour)),
            },
        )

    def render(self, instance: Instance) -> str:
        points = instance.data["points"]
        lines = [
            "Traveling Salesman Problem.",
            "",
            f"There are {len(points)} points in the plane, listed as "
            "'index: (x, y)' with integer coordinates. Distances are Euclidean.",
            "",
        ]
        lines += [f"  {i}: ({x}, {y})" for i, (x, y) in enumerate(points)]
        lines += [
            "",
            "Find the shortest cyclic tour that visits every point exactly once "
            "and returns to its starting point.",
            "",
            "Report the tour as a comma-separated list of point indices. It must "
            "start with 0, contain every index exactly once, and not repeat 0 at "
            "the end (the closing edge back to 0 is implied). End your response "
            "with a single line of the form:",
            "",
            "ANSWER: 0,5,2,...",
        ]
        return "\n".join(lines)

    def parse(self, response: str) -> list[int]:
        payload = extract_answer_line(response)
        tokens = payload.replace(",", " ").split()
        if not tokens:
            raise ParseError("empty tour")
        try:
            return [int(t) for t in tokens]
        except ValueError as e:
            raise ParseError(f"non-integer token in tour: {e}") from None

    def score(self, instance: Instance, parsed: list[int]) -> Score:
        points = instance.data["points"]
        n = len(points)
        opt = instance.aux["opt_length"]
        if sorted(parsed) != list(range(n)) or parsed[0] != 0:
            return Score(
                0.0,
                "invalid",
                False,
                {
                    "reason": "not a permutation of 0..n-1 starting at 0",
                    "opt_length": opt,
                },
            )
        tour_length = _tour_length(points, parsed)
        optimal = tour_length <= opt * (1 + _REL_TOL)
        detail = {
            "tour_length": tour_length,
            "opt_length": opt,
            "ratio": tour_length / opt,
            "beats_nn": tour_length <= instance.aux["nn_length"] + _REL_TOL,
            "beats_two_opt": tour_length <= instance.aux["two_opt_length"] + _REL_TOL,
        }
        if optimal:
            return Score(1.0, "optimal", True, detail)
        return Score(opt / tour_length, "valid_suboptimal", False, detail)

    def solve(self, instance: Instance) -> list[int]:
        return list(instance.answer)

    def format_answer(self, parsed: list[int]) -> str:
        return "ANSWER: " + ",".join(str(i) for i in parsed)


FAMILY = TSPFamily()
