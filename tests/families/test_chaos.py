"""Tests for the chaos family, per the testing doctrine in docs/ARCHITECTURE.md §5.

Covers: I1 determinism, I2 json round-trip, solver cross-check (independent
in-test reimplementation + hand-computed cases), I3 self-consistency through
score_response, I4 corrupted-answer suite, garbage robustness, rejection
rules, I5 difficulty smoke test, and golden snapshots per difficulty level.
"""

import itertools
import json
from pathlib import Path

import pytest

from hard_problems.core import Instance, ParseError, get_family
from hard_problems.families import chaos
from hard_problems.families.chaos import FAMILY, trajectory

GOLDEN_DIR = Path(__file__).parent / "goldens" / "chaos"

ALL_ROWS = [
    dict(zip(FAMILY.difficulty_params, combo))
    for combo in itertools.product(*FAMILY.difficulty_params.values())
]

all_rows = pytest.mark.parametrize(
    "difficulty", ALL_ROWS, ids=lambda d: f"{d['system']}-k{d['k']}"
)


def independent_final_x(data: dict) -> float:
    """Independent reimplementation of the pinned iteration, written from the
    spec in the chaos module docstring (IEEE-754 float64, exact op order)."""
    if data["system"] == "logistic":
        x = data["x0"]
        for _ in range(data["k"]):
            x = 3.9 * x * (1.0 - x)
        return x
    x, y = data["x0"], data["y0"]
    for _ in range(data["k"]):
        x_next = 1.0 - 1.4 * x * x + y
        y_next = 0.3 * x
        x, y = x_next, y_next
    return x


def test_registry_resolves_singleton():
    assert get_family("chaos") is FAMILY


@all_rows
def test_determinism_same_seed(difficulty):
    assert FAMILY.generate(7, **difficulty) == FAMILY.generate(7, **difficulty)


@all_rows
def test_determinism_different_seeds_differ(difficulty):
    x0s = {FAMILY.generate(s, **difficulty).data["x0"] for s in range(5)}
    assert len(x0s) == 5


@all_rows
def test_json_round_trip(difficulty):
    inst = FAMILY.generate(7, **difficulty)
    assert Instance.from_json(inst.to_json()) == inst


@all_rows
def test_solver_cross_check(difficulty):
    """Module answer agrees bit-for-bit with the in-test reimplementation."""
    for seed in (0, 11, 42):
        inst = FAMILY.generate(seed, **difficulty)
        xf = independent_final_x(inst.data)
        assert xf == inst.aux["x_final"]
        assert format(xf, ".4f") == inst.answer


def test_hand_computed_logistic_one_step():
    # 3.9 * 0.5 * (1 - 0.5) = 0.975, exact in float64 (multiplications by 0.5
    # are exact, and 3.9/4 shares the significand of 0.975).
    assert trajectory("logistic", 0.5, 0.0, 1) == [0.5, 0.975]


def test_hand_computed_henon_one_step():
    # x1 = 1 - 1.4*0.5^2 + 0.0, y is the old x scaled by 0.3.
    x1 = 1.0 - 1.4 * 0.5 * 0.5
    assert trajectory("henon", 0.5, 0.0, 1)[-1] == x1
    # Same operation order as the pinned semantics: 1.4 * x * x, not x**2.
    assert trajectory("henon", 0.5, 0.0, 2)[-1] == 1.0 - 1.4 * x1 * x1 + 0.3 * 0.5


def test_initial_conditions_have_six_decimals():
    for system in ("logistic", "henon"):
        inst = FAMILY.generate(13, system=system, k=4)
        x0 = inst.data["x0"]
        # x0 is exactly representable by its own 6-decimal rendering.
        assert float(format(x0, ".6f")) == x0
        assert 0.1 <= x0 < 0.9
        if system == "henon":
            y0 = inst.data["y0"]
            assert float(format(y0, ".6f")) == y0
            assert abs(y0) <= 0.3


@all_rows
def test_i3_self_consistency(difficulty):
    inst = FAMILY.generate(9, **difficulty)
    prompt = FAMILY.render(inst)
    assert "ANSWER:" in prompt
    assert f"{inst.data['x0']:.6f}" in prompt
    response = FAMILY.format_answer(FAMILY.solve(inst))
    score = FAMILY.score_response(inst, response)
    assert score.value == 1.0 and score.correct and score.label == "correct"


class TestCorruptedAnswers:
    """I4: systematic corruption modes score < 1.0 with the right label."""

    @pytest.fixture(params=["logistic", "henon"])
    def inst(self, request):
        return FAMILY.generate(3, system=request.param, k=8)

    def _score(self, inst, payload):
        return FAMILY.score_response(inst, f"ANSWER: {payload}")

    def test_perturb_last_decimal(self, inst):
        corrupted = f"{float(inst.answer) + 1e-4:.4f}"
        assert corrupted != inst.answer
        s = self._score(inst, corrupted)
        assert not s.correct and s.label == "incorrect"
        assert s.detail["digits"] == 3 and s.value == 0.75

    def test_perturb_second_decimal(self, inst):
        corrupted = f"{float(inst.answer) + 0.01:.4f}"
        s = self._score(inst, corrupted)
        assert not s.correct and s.label == "incorrect"
        assert s.detail["digits"] == 1 and s.value == 0.25

    def test_far_off_value(self, inst):
        s = self._score(inst, f"{float(inst.answer) + 1.0:.4f}")
        assert not s.correct and s.label == "incorrect"
        assert s.detail["digits"] == 0 and s.value == 0.0

    def test_sign_flip(self, inst):
        s = self._score(inst, f"{-float(inst.answer):.4f}")
        assert not s.correct and s.label == "incorrect" and s.value < 1.0

    def test_nonfinite_payload(self, inst):
        s = self._score(inst, "nan")
        assert not s.correct and s.value == 0.0


@pytest.mark.parametrize(
    "garbage",
    [
        "",
        "I think it is somewhere around a half.",
        "ANSWER:",
        "ANSWER: zebra",
        "ANSWER: 0.4.3",
    ],
    ids=["empty", "prose", "empty-payload", "word", "malformed-float"],
)
def test_garbage_responses_are_parse_errors(garbage):
    inst = FAMILY.generate(1, system="logistic", k=4)
    score = FAMILY.score_response(inst, garbage)
    assert score.label == "parse_error" and score.value == 0.0 and not score.correct


def test_parse_raises_parse_error_directly():
    with pytest.raises(ParseError):
        FAMILY.parse("ANSWER: not-a-number")


class TestRejectionRules:
    def test_divergence_predicate_flags_escaping_henon_orbit(self):
        # x0 = 2.0 is outside the attractor basin: x2 ~ -28.
        xs = trajectory("henon", 2.0, 0.0, 5)
        assert chaos._diverges(xs)

    def test_generated_trajectories_stay_in_range(self):
        for seed in range(20):
            inst = FAMILY.generate(seed, system="henon", k=32)
            xs = trajectory("henon", inst.data["x0"], inst.data["y0"], 32)
            assert max(abs(x) for x in xs) <= 10.0
            assert inst.aux["rejected_initial_conditions"] >= 0

    def test_logistic_bounded_by_construction(self):
        for seed in range(20):
            inst = FAMILY.generate(seed, system="logistic", k=32)
            xs = trajectory("logistic", inst.data["x0"], 0.0, 32)
            assert all(0.0 < x < 1.0 for x in xs)

    def test_rejection_loop_exhaustion_raises(self, monkeypatch):
        # With an impossible bound every draw is rejected, proving generate()
        # actually consults the divergence predicate in its resample loop.
        monkeypatch.setattr(chaos, "_DIVERGENCE_BOUND", -1.0)
        with pytest.raises(RuntimeError):
            FAMILY.generate(0, system="henon", k=2)


class TestDifficultySmoke:
    """I5: k is the depth knob; chaos amplifies nearby ICs by k=16 (sanity)."""

    def test_logistic_nearby_initial_conditions_diverge(self):
        a = trajectory("logistic", 0.4, 0.0, 32)
        b = trajectory("logistic", 0.4 + 1e-6, 0.0, 32)
        assert abs(a[2] - b[2]) < 1e-4
        assert abs(a[16] - b[16]) > 1e-3
        assert abs(a[32] - b[32]) > 1e-1

    def test_henon_nearby_initial_conditions_diverge(self):
        a = trajectory("henon", 0.3, 0.0, 32)
        b = trajectory("henon", 0.3 + 1e-6, 0.0, 32)
        assert abs(a[2] - b[2]) < 1e-4
        assert abs(a[32] - b[32]) > 1e-2


GOLDEN_FILES = sorted(GOLDEN_DIR.glob("*.json"))


def test_goldens_cover_every_difficulty_row():
    def canon(rows):
        return sorted(json.dumps(d, sort_keys=True) for d in rows)

    diffs = [json.loads(p.read_text())["difficulty"] for p in GOLDEN_FILES]
    assert canon(diffs) == canon(ALL_ROWS)


@pytest.mark.parametrize("path", GOLDEN_FILES, ids=lambda p: p.stem)
def test_golden_regenerates_from_seed(path):
    golden = Instance(**json.loads(path.read_text()))
    regenerated = FAMILY.generate(golden.seed, **golden.difficulty)
    assert regenerated == golden
