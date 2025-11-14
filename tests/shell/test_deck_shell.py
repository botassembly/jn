"""Integration tests for the deterministic deck shell plugin."""

from __future__ import annotations

import json
import subprocess
import sys
from typing import List

import pytest


@pytest.fixture
def jn_cli() -> List[str]:
    """Return invocation prefix for the installed jn CLI."""
    import shutil

    jn_path = shutil.which("jn")
    if jn_path:
        return [jn_path]
    return [sys.executable, "-m", "jn.cli.main"]


def _run_deck(jn_cli: List[str], *args: str) -> dict:
    result = subprocess.run(
        [*jn_cli, "sh", "deck", *args],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert lines, "deck plugin produced no JSON output"
    return json.loads(lines[-1])


def test_deck_init_emits_global_token(jn_cli: List[str]):
    """`deck init` should emit a usable global token."""
    record = _run_deck(
        jn_cli, "init", "--seed", "demo-seed-123", "--players", "2"
    )

    assert record["action"] == "init"
    assert record["global_token"].startswith("g1.")
    assert record["players"] == 2
    assert record["draw_index"] == 0
    assert record["cards_remaining"] == 52


def test_deck_draw_is_deterministic_and_batch_invariant(jn_cli: List[str]):
    """Drawing multiple cards matches sequential draws and order is deterministic."""
    init_rec = _run_deck(
        jn_cli,
        "init",
        "--seed",
        "demo-seed-123",
        "--players",
        "2",
    )
    g0 = init_rec["global_token"]

    batch = _run_deck(
        jn_cli,
        "draw",
        "--global",
        g0,
        "--players",
        "2",
        "--player",
        "1",
        "--count",
        "4",
    )

    assert batch["cards"] == ["2H", "8H", "9C", "10C"]
    assert batch["draw_index"] == 4
    assert batch["cards_remaining"] == 48
    assert len(batch["player_hash"]) == 64

    token = g0
    player_hash = ""
    for _ in range(4):
        draw_args = [
            "draw",
            "--global",
            token,
            "--players",
            "2",
            "--player",
            "1",
            "--count",
            "1",
        ]
        if player_hash:
            draw_args.extend(["--player-hash", player_hash])
        step = _run_deck(jn_cli, *draw_args)
        token = step["global_token"]
        player_hash = step["player_hash"]

    assert token == batch["global_token"]
    assert player_hash == batch["player_hash"]
