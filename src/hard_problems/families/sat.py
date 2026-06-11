"""Random 3-SAT at the satisfiability phase transition.

Family "sat" (PROBLEMS.md 1.2): decide satisfiability of a random 3-CNF
formula with clause-to-variable ratio ~4.27, the empirically hardest region
for random 3-SAT (Mitchell, Selman & Levesque, AAAI 1992; Crawford & Auton
1996). Instances are NOT filtered by outcome: at the phase transition both
SAT and UNSAT occur and both are kept — the claim/certificate asymmetry is
the point of the family (PROBLEMS.md cross-cutting note 1):

- A "SAT" claim must come with a full assignment, verified against every
  clause in linear time. A bad certificate scores 0.0 / "invalid" even when
  the instance is actually satisfiable.
- An "UNSAT" claim is checked against ground truth from the reference DPLL
  solver (run at generation time only).

Rejection rules (ARCHITECTURE.md section 3, criterion 3):
- each clause must use 3 distinct variables (this excludes both duplicate
  literals and tautological "x OR NOT x" clauses);
- duplicate clauses (same literals, in any order) are rejected.

n_vars is capped at MAX_VARS=24 so the reference DPLL always terminates
fast. Clauses use DIMACS-style integer literals: +v / -v, 1-indexed.
Stdlib only; all randomness via random.Random(seed) (invariant I6).
"""

from __future__ import annotations

import math
import random
import re
from typing import Any

from hard_problems.core import (
    Family,
    Instance,
    ParseError,
    Score,
    extract_answer_line,
)

MIN_VARS = 4  # below this, ratio 4.27 asks for more distinct clauses than exist
MAX_VARS = 24  # keeps the reference DPLL fast at generation time


def _sample_clauses(rng: random.Random, n_vars: int, n_clauses: int) -> list[list[int]]:
    """Sample n_clauses distinct, non-degenerate 3-clauses by rejection.

    A candidate clause is three uniformly random literals; it is rejected if
    its variables are not distinct (covers duplicate literals and tautologies)
    or if the same clause (literals sorted by variable) was already drawn.
    """
    clauses: list[list[int]] = []
    seen: set[tuple[int, ...]] = set()
    while len(clauses) < n_clauses:
        lits = [rng.choice((-1, 1)) * rng.randint(1, n_vars) for _ in range(3)]
        if len({abs(lit) for lit in lits}) < 3:
            continue  # duplicate literal or tautological clause
        clause = sorted(lits, key=abs)
        key = tuple(clause)
        if key in seen:
            continue  # duplicate clause
        seen.add(key)
        clauses.append(clause)
    return clauses


def _clause_satisfied(clause: list[int], assignment: list[bool]) -> bool:
    """True iff some literal in the clause is satisfied by the assignment."""
    return any((lit > 0) == assignment[abs(lit) - 1] for lit in clause)


def _simplify(clauses: list[list[int]], lit: int) -> list[list[int]] | None:
    """Assert literal `lit`: drop satisfied clauses, shrink the rest.

    Returns the simplified clause list, or None if an empty clause appears
    (conflict).
    """
    out = []
    for clause in clauses:
        if lit in clause:
            continue
        reduced = [l for l in clause if l != -lit]
        if not reduced:
            return None
        out.append(reduced)
    return out


def _dpll(clauses: list[list[int]], assignment: dict[int, bool]) -> dict[int, bool] | None:
    """DPLL: unit propagation, pure-literal elimination, then branch on the
    first literal of the first clause. Returns a (possibly partial)
    satisfying assignment {var: value} or None if unsatisfiable."""
    # Unit propagation.
    while True:
        units = [c[0] for c in clauses if len(c) == 1]
        if not units:
            break
        lit = units[0]
        assignment[abs(lit)] = lit > 0
        clauses = _simplify(clauses, lit)
        if clauses is None:
            return None
    # Pure-literal elimination.
    literals = {lit for clause in clauses for lit in clause}
    for lit in sorted(l for l in literals if -l not in literals):
        assignment[abs(lit)] = lit > 0
        clauses = _simplify(clauses, lit)  # cannot conflict: -lit never occurs
    if not clauses:
        return assignment
    # Branch.
    lit = clauses[0][0]
    for choice in (lit, -lit):
        simplified = _simplify(clauses, choice)
        if simplified is not None:
            result = _dpll(simplified, {**assignment, abs(choice): choice > 0})
            if result is not None:
                return result
    return None


def _solve_3sat(clauses: list[list[int]], n_vars: int) -> list[bool] | None:
    """Reference solver: full assignment as a bool list, or None if UNSAT.

    Variables left unconstrained by DPLL are assigned False.
    """
    partial = _dpll([list(c) for c in clauses], {})
    if partial is None:
        return None
    return [partial.get(v, False) for v in range(1, n_vars + 1)]


def _lit_str(lit: int) -> str:
    return f"NOT x{-lit}" if lit < 0 else f"x{lit}"


_PAIR_RE = re.compile(r"x(\d+)=(T|F|TRUE|FALSE)", re.IGNORECASE)


class SatFamily(Family):
    name = "sat"
    version = "1.0"
    difficulty_params = {"n_vars": [6, 10, 14, 18, 22], "ratio": [4.27]}

    def generate(self, seed: int, n_vars: int, ratio: float = 4.27) -> Instance:
        if not MIN_VARS <= n_vars <= MAX_VARS:
            raise ValueError(f"n_vars must be in [{MIN_VARS}, {MAX_VARS}], got {n_vars}")
        n_clauses = round(ratio * n_vars)
        if n_clauses > 8 * math.comb(n_vars, 3):
            raise ValueError(
                f"ratio {ratio} demands {n_clauses} distinct clauses but only "
                f"{8 * math.comb(n_vars, 3)} exist over {n_vars} variables"
            )
        rng = random.Random(seed)
        clauses = _sample_clauses(rng, n_vars, n_clauses)
        assignment = _solve_3sat(clauses, n_vars)
        if assignment is None:
            answer: dict[str, Any] = {"sat": False, "assignment": None}
        else:
            assert all(_clause_satisfied(c, assignment) for c in clauses)
            answer = {"sat": True, "assignment": assignment}
        return Instance(
            family=self.name,
            family_version=self.version,
            seed=seed,
            difficulty={"n_vars": n_vars, "ratio": ratio},
            data={"n_vars": n_vars, "clauses": clauses},
            answer=answer,
            aux={"n_clauses": n_clauses, "ratio": ratio},
        )

    def render(self, instance: Instance) -> str:
        n = instance.data["n_vars"]
        clauses = instance.data["clauses"]
        clause_lines = "\n".join(
            f"  {i + 1}. ({' OR '.join(_lit_str(lit) for lit in clause)})"
            for i, clause in enumerate(clauses)
        )
        return (
            f"Decide whether the following 3-SAT formula over variables x1..x{n} "
            f"is satisfiable. The formula is the AND of {len(clauses)} clauses, "
            "each the OR of three literals:\n\n"
            f"{clause_lines}\n\n"
            "If the formula is satisfiable, you MUST provide a satisfying "
            "assignment covering every variable; a bare claim of satisfiability "
            "scores nothing. If it is unsatisfiable, answer UNSAT.\n\n"
            "End your response with exactly one line in one of these two formats:\n"
            f"ANSWER: x1=T x2=F x3=T ... x{n}=F   (one T/F value for each of x1..x{n})\n"
            "ANSWER: UNSAT\n"
        )

    def parse(self, response: str) -> dict[str, Any]:
        payload = extract_answer_line(response)
        cleaned = payload.strip().rstrip(".")
        if cleaned.upper() in ("UNSAT", "UNSATISFIABLE"):
            return {"sat": False}
        cleaned = re.sub(r"\s*=\s*", "=", cleaned)
        assignment: dict[int, bool] = {}
        for token in cleaned.replace(",", " ").split():
            m = _PAIR_RE.fullmatch(token)
            if m is None:
                raise ParseError(f"cannot parse assignment token {token!r}")
            var = int(m.group(1))
            if var in assignment:
                raise ParseError(f"variable x{var} assigned more than once")
            assignment[var] = m.group(2).upper().startswith("T")
        if not assignment:
            raise ParseError("empty answer payload")
        if set(assignment) != set(range(1, len(assignment) + 1)):
            missing = sorted(set(range(1, max(assignment) + 1)) - set(assignment))
            raise ParseError(f"missing variables: x{', x'.join(map(str, missing))}")
        values = [assignment[v] for v in range(1, len(assignment) + 1)]
        return {"sat": True, "assignment": values}

    def score(self, instance: Instance, parsed: dict[str, Any]) -> Score:
        truth = "sat" if instance.answer["sat"] else "unsat"
        if not parsed.get("sat"):
            ok = truth == "unsat"
            return Score(
                1.0 if ok else 0.0,
                "correct" if ok else "incorrect",
                ok,
                {"claimed": "unsat", "truth": truth},
            )
        detail: dict[str, Any] = {"claimed": "sat", "truth": truth}
        assignment = parsed.get("assignment") or []
        n = instance.data["n_vars"]
        if len(assignment) != n:
            detail["error"] = f"assignment has {len(assignment)} values, expected {n}"
            return Score(0.0, "invalid", False, detail)
        # The verification asymmetry: a SAT claim is judged solely by its
        # certificate, even if the instance is actually satisfiable.
        violated = [
            i
            for i, clause in enumerate(instance.data["clauses"])
            if not _clause_satisfied(clause, assignment)
        ]
        detail["violated_clauses"] = violated
        if violated:
            return Score(0.0, "invalid", False, detail)
        return Score(1.0, "correct", True, detail)

    def solve(self, instance: Instance) -> dict[str, Any]:
        return dict(instance.answer)

    def format_answer(self, parsed: dict[str, Any]) -> str:
        if not parsed.get("sat"):
            return "ANSWER: UNSAT"
        pairs = " ".join(
            f"x{i + 1}={'T' if value else 'F'}"
            for i, value in enumerate(parsed["assignment"])
        )
        return f"ANSWER: {pairs}"


FAMILY = SatFamily()
