"""Core abstractions for procedurally generated hard-problem families.

See docs/ARCHITECTURE.md for the full contract. Key principles:
- Instances are data; text is a view (render is separate from generate).
- generate(seed, **knobs) is a pure, deterministic function.
- All responses (chat answers, program stdout) flow through the same
  parse -> score funnel.
- This package imports no eval-harness code.
"""

from __future__ import annotations

import importlib
import json
import re
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any


class ParseError(Exception):
    """Raised by Family.parse when no answer can be extracted from a response."""


@dataclass(frozen=True)
class Instance:
    """A single generated problem instance. JSON-serializable by contract.

    All fields in `difficulty`, `data`, `answer`, and `aux` must survive a
    json.dumps/loads round trip unchanged (use lists, not tuples).
    """

    family: str
    family_version: str
    seed: int
    difficulty: dict[str, Any]
    data: dict[str, Any]
    answer: Any
    aux: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)

    @staticmethod
    def from_json(s: str) -> "Instance":
        return Instance(**json.loads(s))


@dataclass(frozen=True)
class Score:
    """Result of scoring one parsed response against one instance.

    value:   gradated score in [0, 1]; 1.0 is perfect.
    label:   one of "optimal", "valid_suboptimal", "invalid", "correct",
             "incorrect", "parse_error" (families may add labels; document them).
    correct: headline binary judgment (family defines the threshold).
    detail:  family-specific diagnostics (ratios, lengths, digit counts...).
    """

    value: float
    label: str
    correct: bool
    detail: dict[str, Any] = field(default_factory=dict)


_ANSWER_RE = re.compile(r"^\s*\**ANSWER\s*:\s*(.*?)\s*\**\s*$", re.IGNORECASE)


def extract_answer_line(response: str) -> str:
    """Extract the payload of the last 'ANSWER: <payload>' line in a response.

    Lenient by design: tolerates leading whitespace, markdown bold markers,
    case variation, and code fences around the line. The *last* match wins,
    so models may think out loud before answering.

    Raises ParseError if no ANSWER line is found.
    """
    payload = None
    for line in response.splitlines():
        line = line.strip().strip("`")
        m = _ANSWER_RE.match(line)
        if m:
            payload = m.group(1).strip()
    if payload is None:
        raise ParseError("no 'ANSWER:' line found in response")
    return payload


class Family(ABC):
    """A problem family: generator + renderer + parser + scorer + reference solver.

    Subclasses must set class attributes:
      name:              family identifier, matches module name (e.g. "tsp")
      version:           generator version string; bump on any behavior change
      difficulty_params: dict mapping knob name -> default sweep (list of values)

    Invariants (tested per family; see docs/ARCHITECTURE.md section 5):
      I1 determinism, I2 json round-trip, I3 solve->format->parse->score is
      perfect, I4 corrupted answers score < 1.0, I6 no global random state.
    """

    name: str
    version: str
    difficulty_params: dict[str, list[Any]]

    @abstractmethod
    def generate(self, seed: int, **difficulty: Any) -> Instance:
        """Deterministically generate one instance. Pure function of args."""

    @abstractmethod
    def render(self, instance: Instance) -> str:
        """Render the full prompt text, including answer-format instructions.

        Prompts must instruct the model to end with a line 'ANSWER: <payload>'.
        """

    @abstractmethod
    def parse(self, response: str) -> Any:
        """Extract a candidate answer from raw response text.

        Should use extract_answer_line() and then parse the payload.
        Raises ParseError on failure; never raises anything else.
        """

    @abstractmethod
    def score(self, instance: Instance, parsed: Any) -> Score:
        """Score a parsed answer. Must not raise on any parse() output."""

    @abstractmethod
    def solve(self, instance: Instance) -> Any:
        """Reference solver. Returns an answer in the same form parse() returns,
        so that score(instance, solve(instance)) is perfect (invariant I3)."""

    def format_answer(self, parsed: Any) -> str:
        """Render a parsed answer back into an 'ANSWER: ...' line (for I3 tests).

        Default works for str/int/float; families with structured answers
        (paths, assignments, tours) must override to match their prompt spec.
        """
        return f"ANSWER: {parsed}"

    def score_response(self, instance: Instance, response: str) -> Score:
        """The single scoring funnel for all execution conditions."""
        try:
            parsed = self.parse(response)
        except ParseError as e:
            return Score(0.0, "parse_error", False, {"error": str(e)})
        return self.score(instance, parsed)


KNOWN_FAMILIES = ("tsp", "maze", "sat", "argmax", "chaos", "automata")


def get_family(name: str) -> Family:
    """Resolve a family by name via lazy import (no shared registry file).

    Each module hard_problems.families.<name> exposes a FAMILY singleton.
    """
    if name not in KNOWN_FAMILIES:
        raise KeyError(f"unknown family {name!r}; known: {KNOWN_FAMILIES}")
    mod = importlib.import_module(f"hard_problems.families.{name}")
    return mod.FAMILY
