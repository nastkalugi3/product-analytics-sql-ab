"""Every SQL file must parse as PostgreSQL (syntax check only, see README)."""

from pathlib import Path

import pytest
import sqlglot

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"
FILES = sorted(SQL_DIR.rglob("*.sql"))

FORBIDDEN = ["QUALIFY", "GROUP BY ALL", "ORDER BY ALL", "LIST_", "UNNEST", "::"]


def test_files_found():
    assert len(FILES) >= 25  # 1 schema + 11 olist + 5 ab + 8 dashboard


@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(SQL_DIR)))
def test_parses_as_postgres(path):
    statements = sqlglot.parse(path.read_text(encoding="utf-8"), read="postgres")
    assert [s for s in statements if s is not None]


@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(SQL_DIR)))
def test_no_duckdb_only_constructs(path):
    text = path.read_text(encoding="utf-8").upper()
    code = "\n".join(
        line for line in text.splitlines() if not line.strip().startswith("--")
    )
    for token in FORBIDDEN:
        assert token not in code, f"{token} in {path.name}"
