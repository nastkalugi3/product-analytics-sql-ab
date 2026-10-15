"""Cheap structure checks for the notebooks (they are executed by run_all.sh)."""

import ast
import json
from pathlib import Path

import pytest

NB_DIR = Path(__file__).resolve().parents[1] / "notebooks"
NOTEBOOKS = sorted(NB_DIR.glob("*.ipynb"))


def _cells(path):
    return json.loads(path.read_text(encoding="utf-8"))["cells"]


def test_three_notebooks():
    assert [p.name[:2] for p in NOTEBOOKS] == ["01", "02", "03"]


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_code_cells_are_valid_python(path):
    for cell in _cells(path):
        if cell["cell_type"] == "code":
            ast.parse("".join(cell["source"]))


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_required_sections_and_seed(path):
    cells = _cells(path)
    headers = [
        line
        for c in cells
        if c["cell_type"] == "markdown"
        for line in "".join(c["source"]).splitlines()
        if line.startswith("## ")
    ]
    text = "\n".join(headers).lower()
    for word in ("goal", "data", "sources"):
        assert word in text, f"no '{word}' section in {path.name}"
    code = "\n".join("".join(c["source"]) for c in cells if c["cell_type"] == "code")
    assert "SEED" in code


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_starts_with_title(path):
    first = _cells(path)[0]
    assert first["cell_type"] == "markdown"
    assert "".join(first["source"]).lstrip().startswith("# ")


def test_olist_notebook_has_saved_outputs():
    cells = _cells(NOTEBOOKS[0])
    code = [c for c in cells if c["cell_type"] == "code"]
    assert code and all(c["outputs"] for c in code[:3])
