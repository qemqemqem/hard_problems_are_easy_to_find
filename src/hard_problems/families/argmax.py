"""Argmax of an explicit multimodal function over an integer domain.

Family "argmax" (PROBLEMS.md 3.2): the cleanest inverse-problem framing.
Evaluating f at one point is a single substitution; finding the argmax
requires global search over the whole domain. The function is a sum of
n_modes sinusoids plus a quadratic trend:

    f(x) = sum_i a_i*sin(b_i*x/N + c_i) + d*(x/N - e)^2,   x in {0..N-1}

Why this distribution is hard: with up to a dozen incommensurate
frequencies the landscape is densely multimodal, so local reasoning
(gradient following, inspecting a few sample points) does not locate the
global maximum — only exhaustive (or very careful) search does, while a
brute-force loop is three lines of Python.

All coefficients are rounded to 3 decimals so the rendered formula is
exact, and f is evaluated in plain float64 with math.sin, term by term,
left to right: data["formula"] is byte-for-byte faithful to the evaluation
order (the tests eval() that string as an independent implementation).
Ground truth is brute-force evaluation over the whole domain at
generation time only.

Rejection rule (ARCHITECTURE.md section 3, criterion 3): the argmax must
be unique with margin >= MARGIN over the runner-up; otherwise fresh
coefficients are drawn from the same seeded stream (deterministic
regeneration).

Stdlib only; all randomness via random.Random(seed) (invariant I6).
"""

from __future__ import annotations

import math
import random
import re

from hard_problems.core import (
    Family,
    Instance,
    ParseError,
    Score,
    extract_answer_line,
)

MARGIN = 1e-6  # required gap between the maximum and the runner-up
_MAX_ATTEMPTS = 100

# Coefficient ranges (each draw rounded to 3 decimals).
_A_RANGE = (0.5, 2.0)  # sinusoid amplitudes
_B_RANGE = (3.0, 40.0)  # angular frequencies over the unit-scaled domain
_C_RANGE = (0.0, 6.283)  # phases, ~[0, 2*pi)
_D_RANGE = (-3.0, 3.0)  # quadratic-trend weight
_E_RANGE = (0.0, 1.0)  # quadratic-trend center (unit-scaled)


def _evaluate(modes: list[list[float]], d: float, e: float, domain_size: int, x: int) -> float:
    """Evaluate f at integer x in plain float64.

    Term order and operation order match the rendered formula exactly
    (left-to-right sum; b*x/N, not b*(x/N)), so eval() of data["formula"]
    reproduces these bits.
    """
    total = 0.0
    for a, b, c in modes:
        total += a * math.sin(b * x / domain_size + c)
    total += d * (x / domain_size - e) ** 2
    return total


def _formula(modes: list[list[float]], d: float, e: float, domain_size: int) -> str:
    terms = [f"{a}*sin({b}*x/{domain_size} + {c})" for a, b, c in modes]
    terms.append(f"{d}*(x/{domain_size} - {e})^2")
    return "f(x) = " + " + ".join(terms)


def _unique_argmax(values: list[float]) -> tuple[int, float, float, int] | None:
    """Return (x_max, f_max, f_min, x_second), or None if the maximum does
    not beat the runner-up by at least MARGIN (the rejection rule)."""
    x_max = max(range(len(values)), key=values.__getitem__)
    x_second = max((x for x in range(len(values)) if x != x_max), key=values.__getitem__)
    if values[x_max] - values[x_second] < MARGIN:
        return None
    return x_max, values[x_max], min(values), x_second


_INT_RE = re.compile(r"(?:x\s*=\s*)?([+-]?\d+)", re.IGNORECASE)


class ArgmaxFamily(Family):
    name = "argmax"
    version = "1.0"
    difficulty_params = {"domain_size": [100, 1000, 10000], "n_modes": [3, 6, 12]}

    def generate(self, seed: int, domain_size: int, n_modes: int) -> Instance:
        if domain_size < 2:
            raise ValueError(f"domain_size must be >= 2, got {domain_size}")
        if n_modes < 1:
            raise ValueError(f"n_modes must be >= 1, got {n_modes}")
        rng = random.Random(seed)
        for _ in range(_MAX_ATTEMPTS):
            modes = [
                [
                    round(rng.uniform(*_A_RANGE), 3),
                    round(rng.uniform(*_B_RANGE), 3),
                    round(rng.uniform(*_C_RANGE), 3),
                ]
                for _ in range(n_modes)
            ]
            d = round(rng.uniform(*_D_RANGE), 3)
            e = round(rng.uniform(*_E_RANGE), 3)
            values = [_evaluate(modes, d, e, domain_size, x) for x in range(domain_size)]
            stats = _unique_argmax(values)
            if stats is not None:
                break
        else:  # pragma: no cover - margin failures are vanishingly rare
            raise RuntimeError(f"no unique-argmax instance after {_MAX_ATTEMPTS} attempts")
        x_max, f_max, f_min, x_second = stats
        return Instance(
            family=self.name,
            family_version=self.version,
            seed=seed,
            difficulty={"domain_size": domain_size, "n_modes": n_modes},
            data={
                "coeffs": {"modes": modes, "d": d, "e": e},
                "domain_size": domain_size,
                "formula": _formula(modes, d, e, domain_size),
            },
            answer=x_max,
            aux={"f_max": f_max, "f_min": f_min, "x_second": x_second},
        )

    def render(self, instance: Instance) -> str:
        n = instance.data["domain_size"]
        return (
            f"Find the integer x in {{0, 1, ..., {n - 1}}} that maximizes the "
            "function\n\n"
            f"{instance.data['formula']}\n\n"
            "where sin is the standard sine in radians, evaluated in ordinary "
            "double-precision (IEEE-754 float64) arithmetic.\n\n"
            "End your response with exactly one line containing only the "
            "maximizing integer:\n"
            "ANSWER: <integer>\n"
        )

    def parse(self, response: str) -> int:
        payload = extract_answer_line(response)
        m = _INT_RE.fullmatch(payload.strip().rstrip("."))
        if m is None:
            raise ParseError(f"expected an integer payload, got {payload!r}")
        return int(m.group(1))

    def score(self, instance: Instance, parsed: int) -> Score:
        n = instance.data["domain_size"]
        if not isinstance(parsed, int) or not 0 <= parsed < n:
            return Score(0.0, "invalid", False, {"x": parsed, "domain_size": n})
        coeffs = instance.data["coeffs"]
        f_x = _evaluate(coeffs["modes"], coeffs["d"], coeffs["e"], n, parsed)
        f_max = instance.aux["f_max"]
        f_min = instance.aux["f_min"]
        value = max(0.0, min(1.0, (f_x - f_min) / (f_max - f_min)))
        ok = parsed == instance.answer
        return Score(
            value,
            "correct" if ok else "incorrect",
            ok,
            {"f_xhat": f_x, "f_max": f_max, "regret": f_max - f_x},
        )

    def solve(self, instance: Instance) -> int:
        return instance.answer

    def format_answer(self, parsed: int) -> str:
        return f"ANSWER: {parsed}"


FAMILY = ArgmaxFamily()
