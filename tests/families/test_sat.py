"""Tests for the sat family, per the testing doctrine in ARCHITECTURE.md §5."""

import itertools
import random
from pathlib import Path

import pytest

from hard_problems.core import Instance
from hard_problems.families.sat import FAMILY, MAX_VARS, MIN_VARS, _sample_clauses

GOLDEN_DIR = Path(__file__).parent / "goldens" / "sat"
N_VARS_SWEEP = FAMILY.difficulty_params["n_vars"]


def brute_force(n_vars, clauses):
    """Independent ground truth: full truth-table enumeration (test-only).

    Returns a satisfying assignment (list of bools) or None.
    """
    for bits in itertools.product([False, True], repeat=n_vars):
        if all(
            any((lit > 0) == bits[abs(lit) - 1] for lit in clause)
            for clause in clauses
        ):
            return list(bits)
    return None


def satisfies_all(clauses, assignment):
    return all(
        any((lit > 0) == assignment[abs(lit) - 1] for lit in clause)
        for clause in clauses
    )


def first_instance(predicate, n_vars=10, max_seed=200):
    """Deterministically locate an instance with a given property."""
    for seed in range(max_seed):
        inst = FAMILY.generate(seed, n_vars=n_vars)
        if predicate(inst):
            return inst
    raise AssertionError(f"no matching instance in seeds 0..{max_seed - 1}")


@pytest.fixture(scope="module")
def sat_instance():
    return first_instance(lambda i: i.answer["sat"])


@pytest.fixture(scope="module")
def unsat_instance():
    return first_instance(lambda i: not i.answer["sat"])


class TestDeterminism:  # I1
    def test_same_seed_same_instance(self):
        for seed in (0, 1, 99):
            assert FAMILY.generate(seed, n_vars=10) == FAMILY.generate(seed, n_vars=10)

    def test_different_seeds_differ(self):
        instances = {FAMILY.generate(s, n_vars=10).to_json() for s in range(10)}
        assert len(instances) == 10


class TestRoundTrip:  # I2
    def test_json_round_trip_all_levels(self):
        for n_vars in N_VARS_SWEEP:
            inst = FAMILY.generate(3, n_vars=n_vars)
            assert Instance.from_json(inst.to_json()) == inst


class TestSolverCrossCheck:
    def test_dpll_matches_truth_table(self):
        """DPLL vs independent truth-table enumeration, on many seeds."""
        for n_vars in (6, 8, 10):
            for seed in range(20):
                inst = FAMILY.generate(seed, n_vars=n_vars)
                bf = brute_force(n_vars, inst.data["clauses"])
                assert (bf is not None) == inst.answer["sat"], (n_vars, seed)
                if inst.answer["sat"]:
                    # The returned certificate must itself verify.
                    assert satisfies_all(
                        inst.data["clauses"], inst.answer["assignment"]
                    ), (n_vars, seed)


class TestSelfConsistency:  # I3
    def test_reference_solution_scores_perfect(self):
        for n_vars in N_VARS_SWEEP:
            for seed in range(5):
                inst = FAMILY.generate(seed, n_vars=n_vars)
                response = "Thinking...\n" + FAMILY.format_answer(FAMILY.solve(inst))
                score = FAMILY.score_response(inst, response)
                assert score.value == 1.0 and score.correct, (n_vars, seed)
                assert score.label == "correct"


class TestCorruptedAnswers:  # I4
    def test_flipped_bit_is_invalid_even_though_instance_is_sat(self, sat_instance):
        """A broken certificate scores invalid even on a satisfiable instance."""
        inst = sat_instance
        good = inst.answer["assignment"]
        for i in range(len(good)):
            flipped = good[:i] + [not good[i]] + good[i + 1 :]
            if not satisfies_all(inst.data["clauses"], flipped):
                break
        else:
            raise AssertionError("every single-bit flip still satisfies (degenerate)")
        score = FAMILY.score(inst, {"sat": True, "assignment": flipped})
        assert score.value == 0.0 and not score.correct
        assert score.label == "invalid"
        assert score.detail["claimed"] == "sat" and score.detail["truth"] == "sat"
        assert score.detail["violated_clauses"]

    def test_claim_unsat_on_sat_instance(self, sat_instance):
        score = FAMILY.score(sat_instance, {"sat": False})
        assert score.value == 0.0 and not score.correct
        assert score.label == "incorrect"
        assert score.detail == {"claimed": "unsat", "truth": "sat"}

    def test_claim_sat_on_unsat_instance(self, unsat_instance):
        n = unsat_instance.data["n_vars"]
        score = FAMILY.score(unsat_instance, {"sat": True, "assignment": [False] * n})
        assert score.value == 0.0 and not score.correct
        assert score.label == "invalid"
        assert score.detail["truth"] == "unsat"

    def test_wrong_length_assignment_is_invalid(self, sat_instance):
        short = sat_instance.answer["assignment"][:-1]
        score = FAMILY.score(sat_instance, {"sat": True, "assignment": short})
        assert score.value == 0.0 and score.label == "invalid"


class TestParsing:
    def test_unsat_case_insensitive(self):
        assert FAMILY.parse("ANSWER: unsat") == {"sat": False}
        assert FAMILY.parse("ANSWER: Unsatisfiable.") == {"sat": False}

    def test_assignment_any_order_and_separators(self):
        parsed = FAMILY.parse("ANSWER: x2=F, x1=t x3 = TRUE")
        assert parsed == {"sat": True, "assignment": [True, False, True]}

    def test_garbage_responses_become_parse_error(self, sat_instance):
        garbage = [
            "",
            "I believe it is satisfiable.",
            "ANSWER:",
            "ANSWER: maybe",
            "ANSWER: x1=Q x2=T",
            "ANSWER: x1=T x3=F",  # missing x2
            "ANSWER: x1=T x1=F",  # duplicate
        ]
        for response in garbage:
            score = FAMILY.score_response(sat_instance, response)
            assert score.label == "parse_error", response
            assert score.value == 0.0 and not score.correct


class TestRejectionRules:
    def test_n_vars_cap(self):
        with pytest.raises(ValueError):
            FAMILY.generate(0, n_vars=MAX_VARS + 1)
        with pytest.raises(ValueError):
            FAMILY.generate(0, n_vars=MIN_VARS - 1)

    def test_overconstrained_ratio_rejected(self):
        # Only 32 distinct 3-clauses exist over 4 variables; ratio 10 asks for 40.
        with pytest.raises(ValueError):
            FAMILY.generate(0, n_vars=4, ratio=10.0)

    def test_clause_filters_hold_across_seeds(self):
        for seed in range(30):
            inst = FAMILY.generate(seed, n_vars=6)
            clauses = inst.data["clauses"]
            assert len(clauses) == inst.aux["n_clauses"]
            # No duplicate clauses (canonical form: literals sorted by var).
            assert len({tuple(sorted(c, key=abs)) for c in clauses}) == len(clauses)
            for clause in clauses:
                # 3 distinct variables: no duplicate literals, no tautologies.
                assert len(clause) == 3
                assert len({abs(lit) for lit in clause}) == 3

    def test_sampler_rejections_fire_under_pressure(self):
        # 30 of the 32 possible clauses over 4 vars: with replacement-sampling,
        # both the duplicate-variable filter (only 37.5% of raw draws have 3
        # distinct vars) and the duplicate-clause filter must fire many times
        # for this to return, yet the output must still be clean.
        clauses = _sample_clauses(random.Random(0), n_vars=4, n_clauses=30)
        assert len(clauses) == 30
        assert len({tuple(c) for c in clauses}) == 30
        assert all(len({abs(lit) for lit in c}) == 3 for c in clauses)


class TestDifficulty:  # I5 (weak monotonicity by objective proxy)
    def test_clause_count_tracks_n_vars(self):
        counts = [
            FAMILY.generate(0, n_vars=n).aux["n_clauses"] for n in N_VARS_SWEEP
        ]
        assert counts == sorted(counts) and counts[0] < counts[-1]
        for n_vars, m in zip(N_VARS_SWEEP, counts):
            assert m == round(4.27 * n_vars)  # search space 2^n, ratio pinned


class TestGoldens:
    def test_goldens_regenerate_identically(self):
        files = sorted(GOLDEN_DIR.glob("*.json"))
        assert len(files) == len(N_VARS_SWEEP)
        for path in files:
            stored = Instance.from_json(path.read_text())
            regenerated = FAMILY.generate(stored.seed, **stored.difficulty)
            assert regenerated == stored, path.name


class TestRender:
    def test_render_mentions_every_clause_and_format(self):
        inst = FAMILY.generate(0, n_vars=6)
        prompt = FAMILY.render(inst)
        assert "ANSWER: UNSAT" in prompt and "ANSWER:" in prompt
        assert prompt.count("(") >= inst.aux["n_clauses"]
        assert "x6" in prompt
