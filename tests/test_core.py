"""Tests for hard_problems.core: the shared contract every family builds on."""

import pytest

from hard_problems.core import (
    Family,
    Instance,
    ParseError,
    Score,
    extract_answer_line,
    get_family,
)


class TestExtractAnswerLine:
    def test_basic(self):
        assert extract_answer_line("blah\nANSWER: 42\n") == "42"

    def test_last_answer_wins(self):
        text = "ANSWER: 1\nwait, reconsidering...\nANSWER: 2"
        assert extract_answer_line(text) == "2"

    def test_case_and_whitespace_lenient(self):
        assert extract_answer_line("  answer:   hello world  ") == "hello world"

    def test_markdown_bold(self):
        assert extract_answer_line("**ANSWER: 7**") == "7"

    def test_code_fence_backticks(self):
        assert extract_answer_line("`ANSWER: 1,2,3`") == "1,2,3"

    def test_missing_raises(self):
        with pytest.raises(ParseError):
            extract_answer_line("I have no idea.")

    def test_empty_payload_ok(self):
        assert extract_answer_line("ANSWER:") == ""


class TestInstanceRoundTrip:
    def test_json_round_trip(self):
        inst = Instance(
            family="dummy",
            family_version="1.0",
            seed=7,
            difficulty={"n": 3},
            data={"items": [1, 2, 3]},
            answer=[1, 2, 3],
            aux={"optimum": 6},
        )
        assert Instance.from_json(inst.to_json()) == inst

    def test_frozen(self):
        inst = Instance("d", "1.0", 0, {}, {}, None)
        with pytest.raises(Exception):
            inst.seed = 1  # type: ignore[misc]


class _EchoFamily(Family):
    """Minimal in-test family used to exercise the base-class funnel."""

    name = "echo"
    version = "1.0"
    difficulty_params = {"n": [1]}

    def generate(self, seed, **difficulty):
        return Instance(self.name, self.version, seed, dict(difficulty),
                        {"value": seed}, str(seed))

    def render(self, instance):
        return f"Say {instance.answer}. End with 'ANSWER: <value>'."

    def parse(self, response):
        return extract_answer_line(response)

    def score(self, instance, parsed):
        ok = parsed == instance.answer
        return Score(1.0 if ok else 0.0, "correct" if ok else "incorrect", ok)

    def solve(self, instance):
        return instance.answer


class TestScoreResponseFunnel:
    def test_correct_path(self):
        fam = _EchoFamily()
        inst = fam.generate(5)
        s = fam.score_response(inst, "thinking...\nANSWER: 5")
        assert s.correct and s.value == 1.0

    def test_parse_error_is_scored_not_raised(self):
        fam = _EchoFamily()
        inst = fam.generate(5)
        s = fam.score_response(inst, "no answer here")
        assert s.label == "parse_error" and s.value == 0.0 and not s.correct

    def test_i3_self_consistency(self):
        fam = _EchoFamily()
        inst = fam.generate(9)
        rendered = fam.format_answer(fam.solve(inst))
        assert fam.score_response(inst, rendered).value == 1.0


class TestRegistry:
    def test_unknown_family_rejected(self):
        with pytest.raises(KeyError):
            get_family("not_a_family")
