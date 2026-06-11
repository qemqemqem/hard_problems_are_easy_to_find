"""Tests for the maze family, covering the ARCHITECTURE.md section 5 doctrine:
determinism (I1), json round-trip (I2), independent-solver cross-check, I3
self-consistency, corruption suite (I4), garbage robustness, rejection rules,
difficulty smoke test (I5), and golden-instance snapshots.
"""

import dataclasses
import heapq
import json
import random
from pathlib import Path

import pytest

from hard_problems.core import Instance
from hard_problems.families.maze import FAMILY, _bfs_path, _random_grid

GOLDEN_DIR = Path(__file__).parent / "goldens" / "maze"
SIZES = FAMILY.difficulty_params["size"]
DENSITY = FAMILY.difficulty_params["density"][0]

_DELTAS = {"U": (-1, 0), "D": (1, 0), "L": (0, -1), "R": (0, 1)}


def _dijkstra_opt(grid, start, goal):
    """Independent shortest-path length (Dijkstra, not BFS). Lives in the test
    file on purpose: two implementations must agree on ground truth."""
    size = len(grid)
    start, goal = tuple(start), tuple(goal)
    dist = {start: 0}
    pq = [(0, start)]
    while pq:
        d, (r, c) = heapq.heappop(pq)
        if (r, c) == goal:
            return d
        if d > dist[(r, c)]:
            continue
        for dr, dc in _DELTAS.values():
            nr, nc = r + dr, c + dc
            if 0 <= nr < size and 0 <= nc < size and grid[nr][nc] == 0:
                if d + 1 < dist.get((nr, nc), float("inf")):
                    dist[(nr, nc)] = d + 1
                    heapq.heappush(pq, (d + 1, (nr, nc)))
    return None


def _simulate(grid, start, path):
    """Walk a move string; return the final [r, c], or None on any illegal move."""
    size = len(grid)
    r, c = start
    for move in path:
        dr, dc = _DELTAS[move]
        r, c = r + dr, c + dc
        if not (0 <= r < size and 0 <= c < size) or grid[r][c] == 1:
            return None
    return [r, c]


class TestDeterminism:
    def test_same_seed_same_instance(self):
        a = FAMILY.generate(99, size=10, density=DENSITY)
        b = FAMILY.generate(99, size=10, density=DENSITY)
        assert a == b

    def test_different_seeds_differ(self):
        a = FAMILY.generate(1, size=10, density=DENSITY)
        b = FAMILY.generate(2, size=10, density=DENSITY)
        assert a.data != b.data


class TestRoundTrip:
    @pytest.mark.parametrize("size", SIZES)
    def test_json_round_trip(self, size):
        inst = FAMILY.generate(7, size=size, density=DENSITY)
        assert Instance.from_json(inst.to_json()) == inst


class TestGroundTruth:
    @pytest.mark.parametrize("size", [6, 10])
    @pytest.mark.parametrize("seed", [0, 1, 2])
    def test_bfs_matches_independent_dijkstra(self, seed, size):
        inst = FAMILY.generate(seed, size=size, density=DENSITY)
        opt = _dijkstra_opt(inst.data["grid"], inst.data["start"], inst.data["goal"])
        assert inst.aux["opt_length"] == opt

    @pytest.mark.parametrize("size", SIZES)
    def test_answer_is_legal_optimal_path(self, size):
        inst = FAMILY.generate(13, size=size, density=DENSITY)
        end = _simulate(inst.data["grid"], inst.data["start"], inst.answer)
        assert end == inst.data["goal"]
        assert len(inst.answer) == inst.aux["opt_length"]


class TestI3SelfConsistency:
    @pytest.mark.parametrize("size", SIZES)
    def test_reference_solution_scores_perfect(self, size):
        inst = FAMILY.generate(5, size=size, density=DENSITY)
        response = FAMILY.format_answer(FAMILY.solve(inst))
        s = FAMILY.score_response(inst, response)
        assert s.value == 1.0 and s.correct and s.label == "optimal"


class TestCorruption:
    """I4: systematically corrupted answers score < 1.0 with the right label.

    Scoring must judge validity + length only — many optimal paths exist —
    so the suite checks labels/values, never equality with the stored path.
    """

    def _inst(self):
        return FAMILY.generate(4, size=10, density=DENSITY)

    def test_truncated_path_is_invalid(self):
        inst = self._inst()
        s = FAMILY.score(inst, inst.answer[:-1])
        assert s.label == "invalid" and s.value == 0.0 and not s.correct
        assert s.detail["reason"] == "ended_off_goal"
        assert s.detail["ended_at"] != inst.data["goal"]

    def test_detour_is_valid_suboptimal(self):
        inst = self._inst()
        first = inst.answer[0]
        inverse = {"U": "D", "D": "U", "L": "R", "R": "L"}[first]
        detoured = first + inverse + inst.answer  # step out, step back, then solve
        s = FAMILY.score(inst, detoured)
        opt = inst.aux["opt_length"]
        assert s.label == "valid_suboptimal" and not s.correct
        assert s.value == pytest.approx(opt / (opt + 2))

    def test_off_grid_move_is_invalid(self):
        inst = self._inst()
        s = FAMILY.score(inst, "U" + inst.answer)  # U from (0,0) leaves the grid
        assert s.label == "invalid" and s.value == 0.0
        assert s.detail["reason"] == "off_grid" and s.detail["step"] == 0

    def test_wall_hit_is_invalid(self):
        # Hand-built 2x2 maze with a wall at (0,1): R hits it immediately.
        inst = Instance(
            family="maze",
            family_version=FAMILY.version,
            seed=0,
            difficulty={"size": 2, "density": 0.25},
            data={"grid": [[0, 1], [0, 0]], "start": [0, 0], "goal": [1, 1]},
            answer="DR",
            aux={"opt_length": 2},
        )
        s = FAMILY.score(inst, "RD")
        assert s.label == "invalid" and s.value == 0.0
        assert s.detail["reason"] == "hit_wall" and s.detail["position"] == [0, 1]


class TestGarbageResponses:
    @pytest.mark.parametrize(
        "response",
        [
            "",
            "Just go down and to the right, you can't miss it.",
            "ANSWER:",
            "ANSWER: 1,2,3",
            "ANSWER: RIGHT DOWN DOWN",
        ],
    )
    def test_parse_error_not_exception(self, response):
        inst = FAMILY.generate(0, size=6, density=DENSITY)
        s = FAMILY.score_response(inst, response)
        assert s.label == "parse_error" and s.value == 0.0 and not s.correct

    def test_lenient_spacing_case_and_commas(self):
        assert FAMILY.parse("ANSWER: r r, d D") == "RRDD"


class TestRejectionRules:
    def test_start_and_goal_never_walls(self):
        for seed in range(20):
            grid = FAMILY.generate(seed, size=6, density=DENSITY).data["grid"]
            assert grid[0][0] == 0 and grid[5][5] == 0

    def test_shortest_path_at_least_size(self):
        for seed in range(20):
            inst = FAMILY.generate(seed, size=10, density=DENSITY)
            assert inst.aux["opt_length"] >= 10

    def test_rejection_loop_fires_on_unsolvable_first_draw(self):
        # Find a seed whose *first* drawn grid is rejected (mirrors generate()'s
        # single-stream draw order), then check generate() still succeeds.
        for seed in range(500):
            first = _random_grid(random.Random(seed), 6, DENSITY)
            path = _bfs_path(first, (0, 0), (5, 5))
            if path is None or len(path) < 6:
                inst = FAMILY.generate(seed, size=6, density=DENSITY)
                assert inst.data["grid"] != first
                assert inst.aux["opt_length"] >= 6
                return
        pytest.fail("no seed with a rejected first draw found in 500 tries")

    @pytest.mark.parametrize("kwargs", [{"size": 1}, {"density": 1.0}, {"density": -0.1}])
    def test_bad_parameters_raise(self, kwargs):
        with pytest.raises(ValueError):
            FAMILY.generate(0, **{"size": 6, "density": DENSITY, **kwargs})


class TestDifficultySmoke:
    def test_opt_length_grows_with_size(self):
        means = []
        for size in SIZES:
            opts = [
                FAMILY.generate(seed, size=size, density=DENSITY).aux["opt_length"]
                for seed in range(5)
            ]
            means.append(sum(opts) / len(opts))
        assert means == sorted(means) and means[0] < means[-1]


class TestGoldens:
    @pytest.mark.parametrize("size", SIZES)
    def test_golden_snapshot(self, size):
        golden = json.loads((GOLDEN_DIR / f"size{size:02d}.json").read_text())
        regen = FAMILY.generate(seed=golden["seed"], **golden["difficulty"])
        assert dataclasses.asdict(regen) == golden
