"""Pure-logic tests for the C1/C-inf condition plumbing in the Inspect adapter.

No Inspect runtime, no sandbox, no network: only program extraction and
sample/preamble construction. End-to-end plumbing is exercised separately via
mockllm smoke runs.
"""

from hard_problems.adapters.inspect_ai import (
    C1_PREAMBLE,
    CINF_PREAMBLE,
    extract_python_program,
    family_samples,
)
from hard_problems.core import get_family


class TestExtractPythonProgram:
    def test_fenced_python_block(self):
        resp = "Here you go:\n```python\nprint('ANSWER: 42')\n```\nDone."
        assert extract_python_program(resp) == "print('ANSWER: 42')"

    def test_bare_fence(self):
        resp = "```\nx = 1\nprint(x)\n```"
        assert extract_python_program(resp) == "x = 1\nprint(x)"

    def test_multiple_blocks_last_wins(self):
        resp = (
            "First attempt:\n```python\nprint('draft')\n```\n"
            "Final version:\n```python\nprint('final')\n```"
        )
        assert extract_python_program(resp) == "print('final')"

    def test_empty_block_skipped(self):
        # A trailing empty fence must not shadow the real program.
        resp = "```python\nprint('real')\n```\n```\n```"
        assert extract_python_program(resp) == "print('real')"

    def test_no_block_no_code(self):
        assert extract_python_program("I cannot solve this problem.") is None

    def test_empty_response(self):
        assert extract_python_program("") is None

    def test_bare_code_heuristic(self):
        resp = "import math\nprint(f'ANSWER: {math.factorial(5)}')"
        assert extract_python_program(resp) == resp

    def test_bare_code_def(self):
        resp = "def solve():\n    return 7\nprint(f'ANSWER: {solve()}')"
        assert extract_python_program(resp) == resp


class TestPreambleInSamples:
    @staticmethod
    def _easiest(name: str) -> dict:
        fam = get_family(name)
        return {k: v[0] for k, v in fam.difficulty_params.items()}

    def test_c1_preamble_appended(self):
        samples = family_samples(
            "argmax", seeds=[1], difficulty=self._easiest("argmax"), preamble=C1_PREAMBLE
        )
        assert len(samples) == 1
        assert C1_PREAMBLE in samples[0].input
        # the family prompt comes first; the preamble is appended after it
        assert not samples[0].input.startswith(C1_PREAMBLE)

    def test_cinf_preamble_appended(self):
        samples = family_samples(
            "argmax", seeds=[1], difficulty=self._easiest("argmax"), preamble=CINF_PREAMBLE
        )
        assert CINF_PREAMBLE in samples[0].input

    def test_no_preamble_by_default(self):
        samples = family_samples("argmax", seeds=[1], difficulty=self._easiest("argmax"))
        assert C1_PREAMBLE not in samples[0].input
        assert CINF_PREAMBLE not in samples[0].input
