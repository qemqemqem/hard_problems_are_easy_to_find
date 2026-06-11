"""Tests for the argmax family, per the testing doctrine in ARCHITECTURE.md §5."""

import math
from pathlib import Path

import pytest

from hard_problems.core import Instance, ParseError
from hard_problems.families.argmax import FAMILY, MARGIN, _unique_argmax

GOLDEN_DIR = Path(__file__).parent / "goldens" / "argmax"
DOMAIN_SWEEP = FAMILY.difficulty_params["domain_size"]
MODES_SWEEP = FAMILY.difficulty_params["n_modes"]
ALL_LEVELS = [(n, k) for n in DOMAIN_SWEEP for k in MODES_SWEEP]


def independent_eval(formula: str, x: int) -> float:
    """Independent implementation of f: literally evaluate the rendered
    formula string as Python (^2 -> **2). If the module's float64 evaluation
    ever diverges from the string it shows the model, this catches it."""
    expr = formula.split("=", 1)[1].strip().replace("^2", "**2")
    return eval(expr, {"__builtins__": {}}, {"sin": math.sin, "x": x})


class TestDeterminism:  # I1
    def test_same_seed_same_instance(self):
        for seed in (0, 1, 99):
            assert FAMILY.generate(seed, domain_size=100, n_modes=3) == FAMILY.generate(
                seed, domain_size=100, n_modes=3
            )

    def test_different_seeds_differ(self):
        instances = {
            FAMILY.generate(s, domain_size=100, n_modes=3).to_json() for s in range(10)
        }
        assert len(instances) == 10


class TestRoundTrip:  # I2 (floats must survive json exactly)
    def test_json_round_trip_all_levels(self):
        for domain_size, n_modes in ALL_LEVELS:
            inst = FAMILY.generate(3, domain_size=domain_size, n_modes=n_modes)
            assert Instance.from_json(inst.to_json()) == inst


class TestSolverCrossCheck:
    """Brute force IS the solver here, so the cross-check pits the module's
    evaluation against an independent eval of the formula string."""

    def test_formula_string_reproduces_ground_truth(self):
        for seed in range(10):
            inst = FAMILY.generate(seed, domain_size=200, n_modes=4)
            n = inst.data["domain_size"]
            values = [independent_eval(inst.data["formula"], x) for x in range(n)]
            x_max = max(range(n), key=values.__getitem__)
            assert x_max == inst.answer
            assert values[x_max] == inst.aux["f_max"]
            assert min(values) == inst.aux["f_min"]
            x_second = max(
                (x for x in range(n) if x != x_max), key=values.__getitem__
            )
            assert x_second == inst.aux["x_second"]
            # Uniqueness margin verified independently.
            assert values[x_max] - values[x_second] >= MARGIN

    def test_score_evaluation_matches_formula_on_sweep(self):
        for domain_size, n_modes in ALL_LEVELS:
            inst = FAMILY.generate(1, domain_size=domain_size, n_modes=n_modes)
            for x in (0, domain_size // 3, inst.answer, domain_size - 1):
                score = FAMILY.score(inst, x)
                assert score.detail["f_xhat"] == independent_eval(
                    inst.data["formula"], x
                ), (domain_size, n_modes, x)


class TestSelfConsistency:  # I3
    def test_reference_solution_scores_perfect(self):
        for domain_size, n_modes in ALL_LEVELS:
            for seed in range(2):
                inst = FAMILY.generate(seed, domain_size=domain_size, n_modes=n_modes)
                response = "Searching...\n" + FAMILY.format_answer(FAMILY.solve(inst))
                score = FAMILY.score_response(inst, response)
                assert score.value == 1.0 and score.correct
                assert score.label == "correct" and score.detail["regret"] == 0.0


class TestCorruptedAnswers:  # I4
    @pytest.fixture(scope="class")
    def inst(self):
        return FAMILY.generate(0, domain_size=1000, n_modes=6)

    def test_off_by_one_argmax(self, inst):
        x = inst.answer + 1 if inst.answer + 1 < 1000 else inst.answer - 1
        score = FAMILY.score(inst, x)
        assert not score.correct and score.label == "incorrect"
        assert score.value < 1.0 and score.detail["regret"] > 0.0

    def test_runner_up_is_incorrect_with_margin_regret(self, inst):
        score = FAMILY.score(inst, inst.aux["x_second"])
        assert not score.correct and score.label == "incorrect"
        assert score.detail["regret"] >= MARGIN
        assert 0.0 <= score.value < 1.0

    def test_out_of_domain_is_invalid(self, inst):
        for x in (-1, 1000, 10**9):
            score = FAMILY.score(inst, x)
            assert score.value == 0.0 and score.label == "invalid"
            assert not score.correct

    def test_gradation_orders_by_function_value(self, inst):
        # A near-miss with higher f must outscore a point near the minimum.
        values = {x: FAMILY.score(inst, x).value for x in range(1000)}
        assert values[inst.answer] == 1.0
        assert values[inst.aux["x_second"]] > min(values.values())
        assert all(0.0 <= v <= 1.0 for v in values.values())


class TestParsing:
    def test_plain_and_lenient_integers(self):
        assert FAMILY.parse("ANSWER: 42") == 42
        assert FAMILY.parse("thinking\nANSWER: x = 137.") == 137
        assert FAMILY.parse("ANSWER: -3") == -3

    def test_garbage_responses_become_parse_error(self):
        inst = FAMILY.generate(0, domain_size=100, n_modes=3)
        garbage = ["", "no idea", "ANSWER:", "ANSWER: about 12", "ANSWER: 3.7"]
        for response in garbage:
            score = FAMILY.score_response(inst, response)
            assert score.label == "parse_error", response
            assert score.value == 0.0 and not score.correct

    def test_parse_raises_only_parse_error(self):
        with pytest.raises(ParseError):
            FAMILY.parse("ANSWER: twelve")


class TestRejectionRules:
    def test_unique_argmax_helper_rejects_ties(self):
        assert _unique_argmax([0.0, 1.0, 1.0]) is None
        assert _unique_argmax([0.0, 1.0, 1.0 - MARGIN / 2]) is None
        assert _unique_argmax([0.0, 1.0, 0.5]) == (1, 1.0, 0.0, 2)

    def test_generated_instances_respect_margin(self):
        for seed in range(20):
            inst = FAMILY.generate(seed, domain_size=100, n_modes=3)
            f_second = independent_eval(inst.data["formula"], inst.aux["x_second"])
            assert inst.aux["f_max"] - f_second >= MARGIN
            assert inst.aux["x_second"] != inst.answer

    def test_degenerate_knobs_rejected(self):
        with pytest.raises(ValueError):
            FAMILY.generate(0, domain_size=1, n_modes=3)
        with pytest.raises(ValueError):
            FAMILY.generate(0, domain_size=100, n_modes=0)


class TestDifficulty:  # I5 (weak monotonicity by objective proxy)
    def test_knobs_control_search_space_and_modality(self):
        small = FAMILY.generate(0, domain_size=100, n_modes=3)
        big = FAMILY.generate(0, domain_size=10000, n_modes=12)
        # Search space grows with domain_size.
        assert big.data["domain_size"] > small.data["domain_size"]
        # Landscape modality grows with n_modes (one sin term per mode).
        assert small.data["formula"].count("sin") == 3
        assert big.data["formula"].count("sin") == 12
        assert len(big.data["coeffs"]["modes"]) == 12


class TestGoldens:
    def test_goldens_regenerate_identically(self):
        files = sorted(GOLDEN_DIR.glob("*.json"))
        assert len(files) == len(ALL_LEVELS)
        for path in files:
            stored = Instance.from_json(path.read_text())
            regenerated = FAMILY.generate(stored.seed, **stored.difficulty)
            assert regenerated == stored, path.name


class TestRender:
    def test_render_shows_exact_formula_and_domain(self):
        inst = FAMILY.generate(0, domain_size=100, n_modes=3)
        prompt = FAMILY.render(inst)
        assert inst.data["formula"] in prompt
        assert "{0, 1, ..., 99}" in prompt
        assert "ANSWER:" in prompt
