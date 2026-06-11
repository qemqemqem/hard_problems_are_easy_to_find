"""Elementary cellular automaton simulation family ("automata").

Task: evolve a one-dimensional elementary cellular automaton (CA) with
CYCLIC (wrap-around) boundary for exactly k steps and report the final
bitstring. Verification is a string comparison; solving by pure thinking
requires k synchronous width-cell updates -- the serial-depth knob in its
purest form (PROBLEMS.md section 2.2).

Semantics (exact by construction)
---------------------------------
State: a string of `width` cells, each 0 or 1, on a ring (cell 0's left
neighbor is cell width-1, cell width-1's right neighbor is cell 0). All
cells update simultaneously each step. A cell's next value depends on
(left neighbor, itself, right neighbor) via the standard Wolfram rule
numbering: neighborhood bits read as a 3-bit number n in 0..7, next state =
bit n of the 8-bit rule number. All arithmetic is on small integers --
no float semantics to pin.

The PROMPT shows the rule as an explicit 8-row neighborhood -> next-state
table, never just "rule 110": the bare rule number would test memorized
knowledge of Wolfram numbering, while the table tests execution.

Why this distribution is hard (admission criterion 1)
-----------------------------------------------------
Rule 110 is Turing-complete (Cook 2004, "Universality in Elementary
Cellular Automata"), and rule 30 is the classic pseudo-random chaotic rule;
neither has a known closed-form shortcut, so the answer requires the full
depth-k computation. Rule 90 (next = left XOR right) is linear over GF(2)
and serves as an easier, structured control within the same surface form.
Random initial states avoid the heavily published single-1-seed pictures.

Rejection rules (admission criterion 3)
---------------------------------------
All-zeros and all-ones initial states are rejected (resampled from the same
seeded stream): they are fixed points or immediately collapse for the rules
used here, making the instance trivial.

Scoring degrades gracefully (admission criterion 5): exact match is correct;
otherwise value = fraction of matching cells (Hamming similarity); answers
of the wrong length are "invalid" with value 0.
"""

from __future__ import annotations

import random

from hard_problems.core import (
    Family,
    Instance,
    ParseError,
    Score,
    extract_answer_line,
)

_MAX_REJECTIONS = 1000


def rule_table(rule: int) -> dict[str, str]:
    """The 8-entry lookup for a Wolfram rule number: "lcr" -> next cell."""
    return {format(n, "03b"): str((rule >> n) & 1) for n in range(8)}


def evolve(state: str, rule: int, steps: int) -> str:
    """Reference solver: synchronous update with cyclic boundary."""
    table = rule_table(rule)
    w = len(state)
    for _ in range(steps):
        state = "".join(
            table[state[(i - 1) % w] + state[i] + state[(i + 1) % w]]
            for i in range(w)
        )
    return state


class AutomataFamily(Family):
    name = "automata"
    version = "1.0"
    # Rules 30 and 90 are available knob values; 110 is the default sweep.
    difficulty_params = {"width": [10, 20, 40], "k": [1, 2, 4, 8, 16, 32], "rule": [110]}

    def generate(self, seed: int, width: int = 20, k: int = 8, rule: int = 110) -> Instance:
        if rule not in (110, 30, 90):
            raise ValueError(f"unsupported rule {rule!r}; supported: 110, 30, 90")
        rng = random.Random(seed)
        rejected = 0
        for _ in range(_MAX_REJECTIONS):
            initial = "".join(str(rng.randint(0, 1)) for _ in range(width))
            if "0" in initial and "1" in initial:
                break
            rejected += 1
        else:
            raise RuntimeError(f"no non-degenerate initial state after {_MAX_REJECTIONS} draws")

        return Instance(
            family=self.name,
            family_version=self.version,
            seed=seed,
            difficulty={"width": width, "k": k, "rule": rule},
            data={"rule": rule, "width": width, "steps": k, "initial": initial},
            answer=evolve(initial, rule, k),
            aux={
                "rule_table": rule_table(rule),
                "rejected_initial_states": rejected,
            },
        )

    def render(self, instance: Instance) -> str:
        d = instance.data
        width, k = d["width"], d["steps"]
        table = rule_table(d["rule"])
        # Conventional presentation order: 111 down to 000.
        table_rows = "\n".join(
            f"    {n[0]} {n[1]} {n[2]}  ->  {table[n]}"
            for n in sorted(table, reverse=True)
        )
        return (
            f"Simulate a one-dimensional cellular automaton on a ring of {width} cells.\n"
            "Each cell is 0 or 1. All cells update simultaneously at each step. The\n"
            f"boundary is CYCLIC: cell 0's left neighbor is cell {width - 1}, and cell\n"
            f"{width - 1}'s right neighbor is cell 0.\n"
            "\n"
            "Each cell's next value is determined by its left neighbor, itself, and its\n"
            "right neighbor, according to this table:\n"
            "\n"
            "    L C R  ->  next C\n"
            f"{table_rows}\n"
            "\n"
            f"Initial state (cell 0 first):\n"
            f"    {d['initial']}\n"
            "\n"
            f"Apply exactly {k} steps and report the final state as a string of\n"
            f"{width} bits, cell 0 first.\n"
            "\n"
            "End your response with a single line of the form:\n"
            f"ANSWER: <final state, exactly {width} characters, each 0 or 1>\n"
            "For example: ANSWER: 0110100101\n"
        )

    def parse(self, response: str) -> str:
        """Return the cleaned bitstring (whitespace stripped).

        Length is checked in score(), which knows the instance width.
        """
        payload = extract_answer_line(response)
        cleaned = "".join(payload.split())
        if not cleaned:
            raise ParseError("empty answer payload")
        if any(c not in "01" for c in cleaned):
            raise ParseError(f"payload {payload!r} is not a 0/1 bitstring")
        return cleaned

    def score(self, instance: Instance, parsed: str) -> Score:
        width = instance.data["width"]
        if not isinstance(parsed, str) or len(parsed) != width:
            return Score(0.0, "invalid", False, {"hamming_correct": 0, "width": width})
        if parsed == instance.answer:
            return Score(1.0, "correct", True, {"hamming_correct": width, "width": width})
        matching = sum(a == b for a, b in zip(parsed, instance.answer))
        return Score(
            value=matching / width,
            label="incorrect",
            correct=False,
            detail={"hamming_correct": matching, "width": width},
        )

    def solve(self, instance: Instance) -> str:
        return instance.answer

    def format_answer(self, parsed: str) -> str:
        return f"ANSWER: {parsed}"


FAMILY = AutomataFamily()
