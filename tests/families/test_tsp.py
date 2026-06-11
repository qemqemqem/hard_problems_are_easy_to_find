"""Tests for the TSP family, covering the ARCHITECTURE.md section 5 doctrine:
determinism (I1), json round-trip (I2), brute-force cross-check, I3
self-consistency, corruption suite (I4), garbage robustness, rejection rules,
difficulty smoke test (I5), and golden-instance snapshots.
"""

import dataclasses
import itertools
import json
import math
from pathlib import Path

import pytest

from hard_problems.core import Instance
from hard_problems.families.tsp import (
    FAMILY,
    HELD_KARP_MAX_N,
    _sample_points,
    _tour_length,
)

GOLDEN_DIR = Path(__file__).parent / "goldens" / "tsp"
SWEEP = FAMILY.difficulty_params["n"]


def _brute_force_opt(points):
    """Independent ground truth: try every tour. Lives in the test file on
    purpose (two implementations must agree). Uses its own distance code."""
    n = len(points)
    best = math.inf
    for perm in itertools.permutations(range(1, n)):
        order = [0, *perm]
        total = 0.0
        for a, b in zip(order, order[1:] + order[:1]):
            dx = points[a][0] - points[b][0]
            dy = points[a][1] - points[b][1]
            total += math.sqrt(dx * dx + dy * dy)
        best = min(best, total)
    return best


class TestDeterminism:
    def test_same_seed_same_instance(self):
        assert FAMILY.generate(123, n=8) == FAMILY.generate(123, n=8)

    def test_different_seeds_differ(self):
        a = FAMILY.generate(1, n=8)
        b = FAMILY.generate(2, n=8)
        assert a.data != b.data


class TestRoundTrip:
    @pytest.mark.parametrize("n", SWEEP)
    def test_json_round_trip(self, n):
        inst = FAMILY.generate(7, n=n)
        assert Instance.from_json(inst.to_json()) == inst


class TestGroundTruth:
    @pytest.mark.parametrize("n", [5, 6, 7, 8])
    @pytest.mark.parametrize("seed", [0, 1, 2])
    def test_held_karp_matches_brute_force(self, seed, n):
        inst = FAMILY.generate(seed, n=n)
        brute = _brute_force_opt(inst.data["points"])
        assert inst.aux["opt_length"] == pytest.approx(brute, rel=1e-9)

    @pytest.mark.parametrize("n", SWEEP)
    def test_answer_is_tour_of_optimal_length(self, n):
        inst = FAMILY.generate(11, n=n)
        assert sorted(inst.answer) == list(range(n)) and inst.answer[0] == 0
        assert _tour_length(inst.data["points"], inst.answer) == inst.aux["opt_length"]

    @pytest.mark.parametrize("seed", [0, 1, 2, 3])
    def test_baseline_ordering(self, seed):
        inst = FAMILY.generate(seed, n=11)
        opt, two, nn = (
            inst.aux["opt_length"],
            inst.aux["two_opt_length"],
            inst.aux["nn_length"],
        )
        assert opt <= two * (1 + 1e-9) and two <= nn * (1 + 1e-9)


class TestI3SelfConsistency:
    @pytest.mark.parametrize("n", SWEEP)
    def test_reference_solution_scores_perfect(self, n):
        inst = FAMILY.generate(5, n=n)
        response = FAMILY.format_answer(FAMILY.solve(inst))
        s = FAMILY.score_response(inst, response)
        assert s.value == 1.0 and s.correct and s.label == "optimal"


class TestCorruption:
    """I4: systematically corrupted answers score < 1.0 with the right label."""

    def _inst(self):
        return FAMILY.generate(3, n=8)

    def test_swapped_cities_is_valid_suboptimal(self):
        inst = self._inst()
        opt = inst.aux["opt_length"]
        points = inst.data["points"]
        n = len(points)
        for i, j in itertools.combinations(range(1, n), 2):
            tour = list(inst.answer)
            tour[i], tour[j] = tour[j], tour[i]
            if _tour_length(points, tour) > opt * (1 + 1e-9):
                s = FAMILY.score(inst, tour)
                assert s.label == "valid_suboptimal" and not s.correct
                assert 0.0 < s.value < 1.0
                assert s.detail["ratio"] > 1.0
                return
        pytest.fail("no lengthening swap found (degenerate instance?)")

    def test_dropped_city_is_invalid(self):
        inst = self._inst()
        s = FAMILY.score(inst, list(inst.answer)[:-1])
        assert s.label == "invalid" and s.value == 0.0 and not s.correct

    def test_duplicated_city_is_invalid(self):
        inst = self._inst()
        s = FAMILY.score(inst, list(inst.answer) + [inst.answer[1]])
        assert s.label == "invalid" and s.value == 0.0

    def test_tour_not_starting_at_zero_is_invalid(self):
        inst = self._inst()
        rotated = list(inst.answer)[1:] + [0]
        s = FAMILY.score(inst, rotated)
        assert s.label == "invalid" and s.value == 0.0

    def test_out_of_range_index_is_invalid(self):
        inst = self._inst()
        tour = list(inst.answer)
        tour[-1] = len(inst.data["points"])  # index n does not exist
        s = FAMILY.score(inst, tour)
        assert s.label == "invalid" and s.value == 0.0


class TestGarbageResponses:
    @pytest.mark.parametrize(
        "response",
        [
            "",
            "I think the answer is a nice round trip.",
            "ANSWER:",
            "ANSWER: zero, one, two",
            "ANSWER: 0,1,2.5,3",
        ],
    )
    def test_parse_error_not_exception(self, response):
        inst = FAMILY.generate(0, n=5)
        s = FAMILY.score_response(inst, response)
        assert s.label == "parse_error" and s.value == 0.0 and not s.correct

    def test_lenient_separators_accepted(self):
        assert FAMILY.parse("ANSWER: 0, 3 , 1,2") == [0, 3, 1, 2]


class _ScriptedRNG:
    """Stands in for random.Random to force duplicate draws."""

    def __init__(self, values):
        self.values = list(values)
        self.calls = 0

    def randint(self, a, b):
        self.calls += 1
        return self.values.pop(0)


class TestRejectionRules:
    def test_duplicate_points_resampled(self):
        # First two draws give (1,2); the duplicate is rejected and redrawn.
        rng = _ScriptedRNG([1, 2, 1, 2, 3, 4])
        assert _sample_points(rng, 2) == [[1, 2], [3, 4]]
        assert rng.calls == 6  # 2 wasted draws prove the rejection fired

    def test_all_points_distinct(self):
        for seed in range(10):
            points = FAMILY.generate(seed, n=14).data["points"]
            assert len({tuple(p) for p in points}) == len(points)

    @pytest.mark.parametrize("n", [2, HELD_KARP_MAX_N + 1])
    def test_n_out_of_range_raises(self, n):
        with pytest.raises(ValueError):
            FAMILY.generate(0, n=n)


class TestDifficultySmoke:
    def test_opt_length_grows_with_n(self):
        # Uniform points: expected tour length scales ~ sqrt(n) (BHH theorem).
        means = []
        for n in SWEEP:
            opts = [FAMILY.generate(seed, n=n).aux["opt_length"] for seed in range(5)]
            means.append(sum(opts) / len(opts))
        assert means == sorted(means) and means[0] < means[-1]


class TestGoldens:
    @pytest.mark.parametrize("n", SWEEP)
    def test_golden_snapshot(self, n):
        golden = json.loads((GOLDEN_DIR / f"n{n:02d}.json").read_text())
        regen = FAMILY.generate(seed=golden["seed"], **golden["difficulty"])
        assert dataclasses.asdict(regen) == golden
