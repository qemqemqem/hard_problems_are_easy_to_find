"""Tests for the automata family, per the testing doctrine in docs/ARCHITECTURE.md §5.

Covers: I1 determinism, I2 json round-trip, solver cross-checks (independent
naive reimplementation, rule-90 XOR property, rule-110 published single-seed
evolution), I3 self-consistency through score_response, I4 corrupted-answer
suite, garbage robustness, rejection rules, I5 difficulty smoke test, and
golden snapshots per difficulty level.
"""

import itertools
import json
import random
from pathlib import Path

import pytest

from hard_problems.core import Instance, ParseError, get_family
from hard_problems.families.automata import FAMILY, evolve, rule_table

GOLDEN_DIR = Path(__file__).parent / "goldens" / "automata"

ALL_ROWS = [
    dict(zip(FAMILY.difficulty_params, combo))
    for combo in itertools.product(*FAMILY.difficulty_params.values())
]

all_rows = pytest.mark.parametrize(
    "difficulty", ALL_ROWS, ids=lambda d: f"w{d['width']}-k{d['k']}-r{d['rule']}"
)


def naive_evolve(state: str, rule: int, steps: int) -> str:
    """Independent naive reimplementation: int lists, arithmetic rule lookup."""
    cells = [int(c) for c in state]
    w = len(cells)
    for _ in range(steps):
        nxt = []
        for i in range(w):
            left, center, right = cells[i - 1], cells[i], cells[(i + 1) % w]
            n = 4 * left + 2 * center + right
            nxt.append((rule // (2**n)) % 2)
        cells = nxt
    return "".join(str(c) for c in cells)


def test_registry_resolves_singleton():
    assert get_family("automata") is FAMILY


@all_rows
def test_determinism_same_seed(difficulty):
    assert FAMILY.generate(7, **difficulty) == FAMILY.generate(7, **difficulty)


@all_rows
def test_determinism_different_seeds_differ(difficulty):
    initials = {FAMILY.generate(s, **difficulty).data["initial"] for s in range(5)}
    assert len(initials) == 5


@all_rows
def test_json_round_trip(difficulty):
    inst = FAMILY.generate(7, **difficulty)
    assert Instance.from_json(inst.to_json()) == inst


@all_rows
def test_solver_cross_check_naive(difficulty):
    for seed in (0, 11, 42):
        inst = FAMILY.generate(seed, **difficulty)
        d = inst.data
        assert naive_evolve(d["initial"], d["rule"], d["steps"]) == inst.answer


@pytest.mark.parametrize("rule", [30, 90])
def test_solver_cross_check_other_rules(rule):
    for seed in (0, 5):
        inst = FAMILY.generate(seed, width=20, k=8, rule=rule)
        d = inst.data
        assert naive_evolve(d["initial"], rule, d["steps"]) == inst.answer


def test_rule_110_table_is_the_published_one():
    assert rule_table(110) == {
        "111": "0", "110": "1", "101": "1", "100": "0",
        "011": "1", "010": "1", "001": "1", "000": "0",
    }


def test_rule_110_known_single_seed_evolution():
    # Published rule-110 evolution from a single 1 (Wolfram/MathWorld): the
    # pattern grows leftward as 1 -> 11 -> 111 -> 1101. Width 11 is large
    # enough that the cyclic boundary does not interfere within 3 steps.
    state = "00000100000"
    assert (state := evolve(state, 110, 1)) == "00001100000"
    assert (state := evolve(state, 110, 1)) == "00011100000"
    assert (state := evolve(state, 110, 1)) == "00110100000"


def test_rule_90_is_xor_of_neighbors():
    for seed in range(5):
        inst = FAMILY.generate(seed, width=20, k=1, rule=90)
        initial, final = inst.data["initial"], inst.answer
        w = len(initial)
        for i in range(w):
            expected = int(initial[(i - 1) % w]) ^ int(initial[(i + 1) % w])
            assert final[i] == str(expected)


@all_rows
def test_i3_self_consistency(difficulty):
    inst = FAMILY.generate(9, **difficulty)
    prompt = FAMILY.render(inst)
    assert "ANSWER:" in prompt and "CYCLIC" in prompt
    assert inst.data["initial"] in prompt
    # The rule is given as an explicit table, never as a bare rule number.
    assert "rule 110" not in prompt.lower()
    assert prompt.count("->") >= 8
    response = FAMILY.format_answer(FAMILY.solve(inst))
    score = FAMILY.score_response(inst, response)
    assert score.value == 1.0 and score.correct and score.label == "correct"


class TestCorruptedAnswers:
    """I4: systematic corruption modes score < 1.0 with the right label."""

    @pytest.fixture
    def inst(self):
        return FAMILY.generate(3, width=20, k=8, rule=110)

    def _score(self, inst, payload):
        return FAMILY.score_response(inst, f"ANSWER: {payload}")

    def test_flip_one_cell(self, inst):
        ans = inst.answer
        flipped = ans[:7] + ("1" if ans[7] == "0" else "0") + ans[8:]
        s = self._score(inst, flipped)
        assert not s.correct and s.label == "incorrect"
        assert s.value == pytest.approx(19 / 20)
        assert s.detail["hamming_correct"] == 19

    def test_truncated_bitstring(self, inst):
        s = self._score(inst, inst.answer[:-1])
        assert not s.correct and s.label == "invalid" and s.value == 0.0

    def test_extended_bitstring(self, inst):
        s = self._score(inst, inst.answer + "0")
        assert not s.correct and s.label == "invalid" and s.value == 0.0

    def test_flip_all_cells(self, inst):
        flipped = "".join("1" if c == "0" else "0" for c in inst.answer)
        s = self._score(inst, flipped)
        assert not s.correct and s.label == "incorrect" and s.value == 0.0
        assert s.detail["hamming_correct"] == 0


def test_parse_tolerates_internal_spaces():
    inst = FAMILY.generate(3, width=10, k=2, rule=110)
    spaced = " ".join(inst.answer)
    score = FAMILY.score_response(inst, f"ANSWER: {spaced}")
    assert score.correct and score.value == 1.0


@pytest.mark.parametrize(
    "garbage",
    [
        "",
        "I cannot simulate this in my head.",
        "ANSWER:",
        "ANSWER: 01021",
        "ANSWER: hello",
    ],
    ids=["empty", "prose", "empty-payload", "bad-digit", "word"],
)
def test_garbage_responses_are_parse_errors(garbage):
    inst = FAMILY.generate(1, width=10, k=2, rule=110)
    score = FAMILY.score_response(inst, garbage)
    assert score.label == "parse_error" and score.value == 0.0 and not score.correct


def test_parse_raises_parse_error_directly():
    with pytest.raises(ParseError):
        FAMILY.parse("ANSWER: 0110x")


class TestRejectionRules:
    # Seed 399 is the first seed whose initial width-10 draw from
    # random.Random(seed) is degenerate (found by deterministic scan).
    DEGENERATE_SEED = 399

    def test_degenerate_first_draw_is_resampled(self):
        rng = random.Random(self.DEGENERATE_SEED)
        first_draw = "".join(str(rng.randint(0, 1)) for _ in range(10))
        assert first_draw in ("0" * 10, "1" * 10)  # guards the magic seed
        inst = FAMILY.generate(self.DEGENERATE_SEED, width=10, k=2, rule=110)
        assert inst.data["initial"] != first_draw
        assert inst.aux["rejected_initial_states"] >= 1

    def test_all_generated_initials_are_non_degenerate(self):
        for seed in range(50):
            inst = FAMILY.generate(seed, width=10, k=1, rule=110)
            initial = inst.data["initial"]
            assert "0" in initial and "1" in initial


class TestDifficultySmoke:
    """I5: k is the depth knob; the dynamics do not collapse immediately."""

    def test_depth_knob_changes_the_answer(self):
        inst = FAMILY.generate(0, width=20, k=1, rule=110)
        initial = inst.data["initial"]
        states = [evolve(initial, 110, k) for k in (0, 1, 2, 4, 8, 16, 32)]
        assert len(set(states)) >= 4

    def test_rule_30_propagates_single_cell_perturbations(self):
        inst = FAMILY.generate(0, width=40, k=16, rule=30)
        initial = inst.data["initial"]
        flipped = initial[:20] + ("1" if initial[20] == "0" else "0") + initial[21:]
        a = evolve(initial, 30, 16)
        b = evolve(flipped, 30, 16)
        assert sum(x != y for x, y in zip(a, b)) >= 5


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
