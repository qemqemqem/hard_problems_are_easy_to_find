"""Chaotic-map iteration family ("chaos").

Task: iterate a chaotic map for exactly k steps and report the final x
coordinate to 4 decimal places. Verification is a string comparison;
solving by pure thinking requires k rounds of digit-exact arithmetic.

Pinned ground-truth semantics
-----------------------------
Ground truth is IEEE-754 binary64 arithmetic (plain Python floats) with the
EXACT operation order written below, evaluated left to right as Python does.
The renderer shows the same expressions, so a program reproduces the
trajectory bit-for-bit (invariant I6: only +, -, * on float64 -- exact,
platform-independent semantics; no libm calls).

    logistic (r = 3.9):        x = 3.9 * x * (1.0 - x)
    henon (a = 1.4, b = 0.3):  x, y = 1.0 - 1.4 * x * x + y, 0.3 * x

Note the Henon update is simultaneous: both right-hand sides use the OLD x.
`3.9 * x * (1.0 - x)` associates as `(3.9 * x) * (1.0 - x)` and
`1.0 - 1.4 * x * x + y` as `(1.0 - ((1.4 * x) * x)) + y`.

Why this distribution is hard (admission criterion 1)
-----------------------------------------------------
Both maps are run at canonical chaotic parameter values (logistic r = 3.9,
Henon a = 1.4, b = 0.3). A positive Lyapunov exponent lambda means an error
of size e in the model's running state grows like e * exp(lambda * k), so
holding 4 output decimals requires roughly lambda * k / ln(10) extra digits
of working precision -- per-step precision demands grow linearly in the
depth knob k, and per-step arithmetic slips compound exponentially.
`aux["lyapunov_nominal"]` stores nominal literature values [unverified]:
~0.494 for the logistic map at r = 3.9 and ~0.419 for the Henon map. They
are used only for plot overlays (theory-vs-measurement horizons), never for
scoring.

Initial conditions and rejection rules (admission criterion 3)
--------------------------------------------------------------
- x0 is drawn with exactly 6 decimal places: randint(100000, 899999) / 1e6,
  i.e. x0 in [0.1, 0.9). For henon, y0 = randint(-300000, 300000) / 1e6
  (similarly 6-decimal, small: |y0| <= 0.3, inside the attractor basin).
- logistic: no rejection needed -- for x0 in (0, 1), 3.9 * x * (1 - x) stays
  in (0, 0.975], so trajectories are bounded by construction.
- henon: reject (resample from the same seeded stream) any initial condition
  whose trajectory leaves |x| <= 10 within the k requested steps (escape to
  infinity outside the attractor basin).

Scoring degrades gracefully (admission criterion 5): value = (number of
leading correct decimal places, 0..4) / 4 via absolute-error thresholds;
headline `correct` iff the 4-decimal strings match exactly.
"""

from __future__ import annotations

import math
import random
from typing import Any

from hard_problems.core import (
    Family,
    Instance,
    ParseError,
    Score,
    extract_answer_line,
)

LOGISTIC_R = 3.9
HENON_A = 1.4
HENON_B = 0.3

#: Nominal literature values [unverified]; plot overlays only, never scoring.
LYAPUNOV_NOMINAL = {"logistic": 0.494, "henon": 0.419}

_DIVERGENCE_BOUND = 10.0
_MAX_REJECTIONS = 1000


def trajectory(system: str, x0: float, y0: float, k: int) -> list[float]:
    """Reference solver: the pinned ground-truth iteration (module docstring).

    Returns [x_0, x_1, ..., x_k]. y is tracked internally for henon
    (pass y0=0.0 for logistic, where it is ignored).
    """
    x, y = x0, y0
    xs = [x]
    for _ in range(k):
        if system == "logistic":
            x = 3.9 * x * (1.0 - x)
        elif system == "henon":
            x, y = 1.0 - 1.4 * x * x + y, 0.3 * x
        else:
            raise ValueError(f"unknown system {system!r}")
        xs.append(x)
    return xs


def _diverges(xs: list[float]) -> bool:
    """Rejection predicate: trajectory left the sane range |x| <= 10."""
    return any(abs(x) > _DIVERGENCE_BOUND for x in xs)


class ChaosFamily(Family):
    name = "chaos"
    version = "1.0"
    difficulty_params = {"system": ["logistic", "henon"], "k": [2, 4, 8, 16, 32]}

    def generate(self, seed: int, system: str = "logistic", k: int = 8) -> Instance:
        if system not in ("logistic", "henon"):
            raise ValueError(f"unknown system {system!r}")
        rng = random.Random(seed)
        rejected = 0
        for _ in range(_MAX_REJECTIONS):
            x0 = rng.randint(100_000, 899_999) / 1e6
            y0 = rng.randint(-300_000, 300_000) / 1e6 if system == "henon" else 0.0
            xs = trajectory(system, x0, y0, k)
            if not _diverges(xs):
                break
            rejected += 1
        else:
            raise RuntimeError(f"no bounded {system} trajectory after {_MAX_REJECTIONS} draws")

        data: dict[str, Any] = {"system": system, "k": k, "x0": x0}
        if system == "logistic":
            data["r"] = LOGISTIC_R
        else:
            data["a"] = HENON_A
            data["b"] = HENON_B
            data["y0"] = y0

        return Instance(
            family=self.name,
            family_version=self.version,
            seed=seed,
            difficulty={"system": system, "k": k},
            data=data,
            answer=format(xs[-1], ".4f"),
            aux={
                "lyapunov_nominal": LYAPUNOV_NOMINAL[system],
                "trajectory_first_digits": [format(x, ".4f") for x in xs[:9]],
                "x_final": xs[-1],
                "rejected_initial_conditions": rejected,
            },
        )

    def render(self, instance: Instance) -> str:
        d = instance.data
        k = d["k"]
        if d["system"] == "logistic":
            system_lines = (
                f"Consider the logistic map with r = {d['r']}:\n"
                "\n"
                "    x = 3.9 * x * (1.0 - x)\n"
                "\n"
                f"Start from x_0 = {d['x0']:.6f} and apply the update exactly {k} times\n"
                f"to obtain x_{k}."
            )
        else:
            system_lines = (
                f"Consider the Henon map with a = {d['a']}, b = {d['b']}. Both components\n"
                "update simultaneously (the right-hand sides use the OLD x):\n"
                "\n"
                "    x, y = 1.0 - 1.4 * x * x + y, 0.3 * x\n"
                "\n"
                f"Start from x_0 = {d['x0']:.6f}, y_0 = {d['y0']:.6f} and apply the update\n"
                f"exactly {k} times to obtain x_{k}."
            )
        return (
            f"{system_lines}\n"
            "\n"
            "All arithmetic is IEEE-754 double precision (standard Python floats),\n"
            "with each expression evaluated left to right exactly as written above.\n"
            "\n"
            f"Report x_{k} rounded to exactly 4 decimal places (round-half-even,\n"
            "i.e. Python's format(x, '.4f')).\n"
            "\n"
            "End your response with a single line of the form:\n"
            "ANSWER: <x value to 4 decimal places>\n"
            "For example: ANSWER: 0.4316\n"
        )

    def parse(self, response: str) -> str:
        """Return the float-looking payload as a stripped string.

        Kept as a string so score() can compare the 4-decimal rendering
        exactly; a trailing sentence period is tolerated.
        """
        payload = extract_answer_line(response).strip().rstrip(".").strip()
        if not payload:
            raise ParseError("empty answer payload")
        try:
            float(payload)
        except ValueError:
            raise ParseError(f"payload {payload!r} is not a number")
        return payload

    def score(self, instance: Instance, parsed: str) -> Score:
        try:
            value = float(parsed)
        except (TypeError, ValueError):
            return Score(0.0, "incorrect", False, {"abs_error": None, "digits": 0})
        if not math.isfinite(value):
            return Score(0.0, "incorrect", False, {"abs_error": None, "digits": 0})
        # Truth is the canonical 4-decimal answer (what the prompt asks for).
        truth = float(instance.answer)
        err = abs(value - truth)
        correct = format(value, ".4f") == instance.answer
        if correct or err < 5e-5:
            digits = 4
        elif err < 5e-4:
            digits = 3
        elif err < 5e-3:
            digits = 2
        elif err < 5e-2:
            digits = 1
        else:
            digits = 0
        return Score(
            value=digits / 4.0,
            label="correct" if correct else "incorrect",
            correct=correct,
            detail={"abs_error": err, "digits": digits},
        )

    def solve(self, instance: Instance) -> str:
        return instance.answer

    def format_answer(self, parsed: str) -> str:
        return f"ANSWER: {parsed}"


FAMILY = ChaosFamily()
