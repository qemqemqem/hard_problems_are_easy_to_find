"""Grid-maze shortest-path family (docs/PROBLEMS.md section 2.1).

Distribution & hardness: a size x size grid where each cell is independently
a wall with probability `density` (default 0.25 — comfortably below the
~0.41 site-percolation threshold of the square lattice, so connected
instances are common but contain real detours). The problem is in P — BFS is
~10 lines — but solving it in text demands serial spatial state tracking
over at least 2*(size-1) moves, the depth knob of Category 2.

Rejection rules (admission criterion 3), all enforced deterministically by
drawing successive grids from one random.Random(seed) stream until one is
accepted:
  - start (0,0) and goal (size-1, size-1) are forced open, never walls;
  - a path from start to goal must exist;
  - the shortest-path length must be >= size, so instances are never
    trivially short. (Any start-to-goal path needs >= 2*(size-1) moves, so
    for size >= 2 connectivity is the binding filter; the length floor is
    kept explicit because it is part of the family's spec.)

answer is one BFS shortest path as a move string over U/D/L/R; many optimal
paths usually exist, so score() checks validity + length, never equality
with the stored answer. Scoring is gradated: a valid path that reaches the
goal scores opt_length / len(path), and is `correct` iff its length is
exactly the BFS optimum.
"""

from __future__ import annotations

import random
from collections import deque

from hard_problems.core import Family, Instance, ParseError, Score, extract_answer_line

# Move -> (row delta, col delta). Fixed insertion order keeps BFS deterministic.
MOVES = {"U": (-1, 0), "D": (1, 0), "L": (0, -1), "R": (0, 1)}

_MAX_ATTEMPTS = 10_000


def _bfs_path(grid: list[list[int]], start: tuple[int, int], goal: tuple[int, int]) -> str | None:
    """One shortest path from start to goal as a move string, or None if no path.

    Plain BFS with parent pointers; neighbor order follows MOVES, so the
    returned path is deterministic.
    """
    size = len(grid)
    parent: dict[tuple[int, int], tuple[tuple[int, int], str] | None] = {start: None}
    queue = deque([start])
    while queue:
        cell = queue.popleft()
        if cell == goal:
            break
        r, c = cell
        for move, (dr, dc) in MOVES.items():
            nxt = (r + dr, c + dc)
            nr, nc = nxt
            if 0 <= nr < size and 0 <= nc < size and grid[nr][nc] == 0 and nxt not in parent:
                parent[nxt] = (cell, move)
                queue.append(nxt)
    if goal not in parent:
        return None
    moves = []
    cell = goal
    while parent[cell] is not None:
        cell, move = parent[cell]  # type: ignore[misc]
        moves.append(move)
    return "".join(reversed(moves))


def _random_grid(rng: random.Random, size: int, density: float) -> list[list[int]]:
    """Draw one candidate grid (row-major), then force start and goal open."""
    grid = [
        [1 if rng.random() < density else 0 for _ in range(size)] for _ in range(size)
    ]
    grid[0][0] = 0
    grid[size - 1][size - 1] = 0
    return grid


class MazeFamily(Family):
    name = "maze"
    version = "1.0"
    difficulty_params = {"size": [6, 10, 16, 24, 32], "density": [0.25]}

    def generate(self, seed: int, size: int = 10, density: float = 0.25) -> Instance:
        if size < 2:
            raise ValueError(f"size must be >= 2, got {size}")
        if not 0.0 <= density < 1.0:
            raise ValueError(f"density must be in [0, 1), got {density}")
        rng = random.Random(seed)
        start, goal = (0, 0), (size - 1, size - 1)
        for _ in range(_MAX_ATTEMPTS):
            grid = _random_grid(rng, size, density)
            path = _bfs_path(grid, start, goal)
            if path is None or len(path) < size:
                continue  # rejection rules: must be solvable and not trivially short
            return Instance(
                family=self.name,
                family_version=self.version,
                seed=seed,
                difficulty={"size": size, "density": density},
                data={"grid": grid, "start": [0, 0], "goal": [size - 1, size - 1]},
                answer=path,
                aux={"opt_length": len(path)},
            )
        raise RuntimeError(
            f"no acceptable maze in {_MAX_ATTEMPTS} attempts "
            f"(seed={seed}, size={size}, density={density})"
        )

    def render(self, instance: Instance) -> str:
        grid = instance.data["grid"]
        size = len(grid)
        rows = []
        for r in range(size):
            chars = []
            for c in range(size):
                if [r, c] == instance.data["start"]:
                    chars.append("S")
                elif [r, c] == instance.data["goal"]:
                    chars.append("G")
                else:
                    chars.append("#" if grid[r][c] else ".")
            rows.append("".join(chars))
        lines = [
            "Maze shortest-path problem.",
            "",
            f"Below is a {size}x{size} grid maze:",
            "  'S' = start, at row 0, column 0 (top-left)",
            f"  'G' = goal, at row {size - 1}, column {size - 1} (bottom-right)",
            "  '#' = wall (cannot be entered)",
            "  '.' = open cell",
            "",
            *rows,
            "",
            f"Rows are numbered 0 (top) to {size - 1} (bottom); columns 0 (left) "
            f"to {size - 1} (right). Moves: 'U' = row - 1, 'D' = row + 1, "
            "'L' = column - 1, 'R' = column + 1. A move may not enter a wall or "
            "leave the grid.",
            "",
            "Find a SHORTEST sequence of moves from S to G. End your response "
            "with a single line of the form:",
            "",
            "ANSWER: RRDDRD...",
        ]
        return "\n".join(lines)

    def parse(self, response: str) -> str:
        payload = extract_answer_line(response)
        moves = payload.replace(",", "").replace(" ", "").upper()
        if not moves:
            raise ParseError("empty move sequence")
        bad = set(moves) - set(MOVES)
        if bad:
            raise ParseError(f"invalid move characters: {sorted(bad)}")
        return moves

    def score(self, instance: Instance, parsed: str) -> Score:
        grid = instance.data["grid"]
        size = len(grid)
        goal = list(instance.data["goal"])
        opt = instance.aux["opt_length"]
        r, c = instance.data["start"]
        for step, move in enumerate(parsed):
            dr, dc = MOVES[move]
            r, c = r + dr, c + dc
            if not (0 <= r < size and 0 <= c < size):
                return Score(
                    0.0,
                    "invalid",
                    False,
                    {"reason": "off_grid", "step": step, "position": [r, c]},
                )
            if grid[r][c] == 1:
                return Score(
                    0.0,
                    "invalid",
                    False,
                    {"reason": "hit_wall", "step": step, "position": [r, c]},
                )
        if [r, c] != goal:
            return Score(
                0.0,
                "invalid",
                False,
                {"reason": "ended_off_goal", "ended_at": [r, c], "goal": goal},
            )
        detail = {"path_length": len(parsed), "opt_length": opt}
        if len(parsed) == opt:
            return Score(1.0, "optimal", True, detail)
        return Score(opt / len(parsed), "valid_suboptimal", False, detail)

    def solve(self, instance: Instance) -> str:
        return instance.answer

    def format_answer(self, parsed: str) -> str:
        return f"ANSWER: {parsed}"


FAMILY = MazeFamily()
