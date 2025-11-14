#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = ["^deck($| )", "^deck .*"]
# ///
"""Deterministic 52-card deck shell plugin for `jn sh`.

The plugin implements a stateless draw protocol where all state is encoded in a
compact global token. Players only need to pass the token (and their private
player hash) between turns to coordinate draws without a server.

Commands
========

Initialize a deck:
    jn sh deck init --seed demo --players 3

Draw cards:
    jn sh deck draw --global g1.... --players 3 --player 1 --count 2

Provide ``--player-hash`` on subsequent draws to continue a player's private
state. Drawing multiple cards at once or one-by-one yields the same hashes.
Outputs are single-line NDJSON objects so they compose naturally in pipelines.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import secrets
import shlex
import struct
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

SUITS = ["S", "H", "D", "C"]
RANKS = ["A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2"]
CARD_COUNT = 52
HEADER = b"SDG1"
MASK64 = (1 << 64) - 1


def _emit(record: dict) -> None:
    try:
        print(json.dumps(record), flush=True)
    except BrokenPipeError:  # pragma: no cover - handled by shell
        os._exit(0)


def _emit_error(message: str, **extra: object) -> None:
    payload = {"_error": message}
    payload.update(extra)
    _emit(payload)


def idx_to_card(idx: int) -> str:
    if not (0 <= idx < CARD_COUNT):
        raise ValueError("card index out of range")
    suit = SUITS[idx // 13]
    rank = RANKS[idx % 13]
    return f"{rank}{suit}"


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64d(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def encode_global(seed: str, n_players: int, t: int) -> str:
    seed_b = seed.encode("utf-8")
    if n_players <= 0:
        raise ValueError("n_players must be >= 1")
    if t < 0 or t > CARD_COUNT:
        raise ValueError("draw index t out of range (0..52)")
    blob = (
        HEADER
        + struct.pack(">H", len(seed_b))
        + seed_b
        + struct.pack(">I", n_players)
        + struct.pack(">Q", t)
    )
    return "g1." + _b64e(blob)


def decode_global(token: str) -> Tuple[str, int, int]:
    if not token.startswith("g1."):
        raise ValueError("bad global token prefix")
    data = _b64d(token[3:])
    view = memoryview(data)
    if len(view) < 4 or bytes(view[:4]) != HEADER:
        raise ValueError("bad global token header")
    offset = 4
    (seed_len,) = struct.unpack_from(">H", view, offset)
    offset += 2
    seed_b = bytes(view[offset : offset + seed_len])
    offset += seed_len
    (n_players,) = struct.unpack_from(">I", view, offset)
    offset += 4
    (t,) = struct.unpack_from(">Q", view, offset)
    offset += 8
    if offset != len(view):
        raise ValueError("unexpected trailing bytes in token")
    return seed_b.decode("utf-8"), t, n_players


def _global_bytes(seed: str, n_players: int, t: int) -> bytes:
    seed_b = seed.encode("utf-8")
    return (
        b"G|"
        + struct.pack(">I", n_players)
        + struct.pack(">Q", t)
        + struct.pack(">H", len(seed_b))
        + seed_b
    )


class SplitMix64:
    def __init__(self, seed_bytes: bytes):
        digest = hashlib.sha256(seed_bytes).digest()
        self.state = int.from_bytes(digest[:8], "big")

    def next_u64(self) -> int:
        self.state = (self.state + 0x9E3779B97F4A7C15) & MASK64
        z = self.state
        z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9 & MASK64
        z = (z ^ (z >> 27)) * 0x94D049BB133111EB & MASK64
        z ^= z >> 31
        return z & MASK64

    def randbelow(self, n: int) -> int:
        if n <= 0:
            raise ValueError("n must be > 0")
        while True:
            x = self.next_u64() >> 1
            limit = ((1 << 63) // n) * n - 1
            if x <= limit:
                return x % n


def deck_from_seed(seed: str) -> List[int]:
    prng = SplitMix64(seed.encode("utf-8"))
    deck = list(range(CARD_COUNT))
    for i in range(CARD_COUNT - 1, 0, -1):
        j = prng.randbelow(i + 1)
        deck[i], deck[j] = deck[j], deck[i]
    return deck


def _sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def init_player_hash(seed: str, position: int, n_players: int) -> bytes:
    if not (1 <= position <= n_players):
        raise ValueError("position must be in [1..n_players]")
    return _sha256(
        b"P_INIT|"
        + seed.encode("utf-8")
        + struct.pack(">I", position)
        + struct.pack(">I", n_players)
    )


def advance_player_hash(p_bytes: bytes, g_bytes: bytes) -> bytes:
    return _sha256(b"P|" + p_bytes + g_bytes)


@dataclass
class DrawResult:
    cards: List[str]
    new_global: str
    new_player_hash: str


def draw(
    curr_global: str,
    position: int,
    num_players: int,
    curr_player_hash: Optional[str],
    m: int,
) -> DrawResult:
    if m <= 0:
        raise ValueError("m must be >= 1")

    seed, t, n_from_token = decode_global(curr_global)
    if n_from_token != num_players:
        raise ValueError(
            f"num_players mismatch: token has {n_from_token}, got {num_players}"
        )
    if t + m > CARD_COUNT:
        raise ValueError(
            f"attempt to draw past end of deck: t={t}, m={m}, remaining={CARD_COUNT - t}"
        )

    if not curr_player_hash:
        player_bytes = init_player_hash(seed, position, num_players)
    else:
        try:
            player_bytes = bytes.fromhex(curr_player_hash)
        except Exception as exc:  # pragma: no cover - defensive
            raise ValueError("curr_player_hash must be 64-hex") from exc
        if len(player_bytes) != 32:
            raise ValueError("curr_player_hash must decode to 32 bytes")

    deck = deck_from_seed(seed)
    cards: List[str] = []
    for i in range(m):
        g_bytes = _global_bytes(seed, num_players, t + i)
        player_bytes = advance_player_hash(player_bytes, g_bytes)
        cards.append(idx_to_card(deck[t + i]))

    new_t = t + m
    new_global = encode_global(seed, num_players, new_t)
    return DrawResult(cards=cards, new_global=new_global, new_player_hash=player_bytes.hex())


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="deck", add_help=True)
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Create or resume a global token")
    p_init.add_argument("--seed", help="Shared seed for the deck", default=None)
    p_init.add_argument(
        "--players",
        "-n",
        type=int,
        required=True,
        help="Total number of players",
    )
    p_init.add_argument(
        "--draw-index",
        type=int,
        default=0,
        help="Start draw index (default 0 for a fresh shoe)",
    )

    p_draw = sub.add_parser("draw", help="Draw cards using an existing token")
    p_draw.add_argument("--global", dest="global_token", required=True)
    p_draw.add_argument(
        "--players",
        "-n",
        type=int,
        required=True,
        help="Total number of players",
    )
    p_draw.add_argument(
        "--player",
        "-p",
        type=int,
        required=True,
        help="This player's 1-based position",
    )
    p_draw.add_argument(
        "--count",
        "-c",
        type=int,
        default=1,
        help="Number of cards to draw",
    )
    p_draw.add_argument(
        "--player-hash",
        dest="player_hash",
        default="",
        help="Player's previous 64-hex hash (blank for first draw)",
    )
    return parser


def _handle_init(args: argparse.Namespace) -> None:
    seed = args.seed or secrets.token_hex(16)
    token = encode_global(seed, args.players, args.draw_index)
    _emit(
        {
            "action": "init",
            "seed": seed,
            "players": args.players,
            "draw_index": args.draw_index,
            "cards_remaining": CARD_COUNT - args.draw_index,
            "global_token": token,
        }
    )


def _handle_draw(args: argparse.Namespace) -> None:
    result = draw(
        curr_global=args.global_token,
        position=args.player,
        num_players=args.players,
        curr_player_hash=args.player_hash or None,
        m=args.count,
    )
    seed, draw_index, n_players = decode_global(result.new_global)
    _emit(
        {
            "action": "draw",
            "seed": seed,
            "players": n_players,
            "player": args.player,
            "cards": result.cards,
            "cards_drawn": len(result.cards),
            "cards_remaining": CARD_COUNT - draw_index,
            "draw_index": draw_index,
            "global_token": result.new_global,
            "player_hash": result.new_player_hash,
        }
    )


def reads(command_str: str | None = None) -> None:
    if not command_str:
        _emit_error("deck requires a subcommand (init or draw)")
        sys.exit(1)

    try:
        argv = shlex.split(command_str)
    except ValueError as exc:
        _emit_error(f"Invalid command syntax: {exc}")
        sys.exit(1)

    if not argv or argv[0] != "deck":
        _emit_error("expected command starting with 'deck'")
        sys.exit(1)

    parser = _build_parser()
    try:
        args = parser.parse_args(argv[1:])
    except SystemExit as exc:  # argparse already printed error
        sys.exit(exc.code)

    try:
        if args.command == "init":
            _handle_init(args)
        elif args.command == "draw":
            _handle_draw(args)
        else:  # pragma: no cover - argparse enforces commands
            _emit_error(f"Unknown deck command: {args.command}")
            sys.exit(1)
    except ValueError as exc:
        _emit_error(str(exc))
        sys.exit(1)


def main() -> None:  # pragma: no cover - exercised via uv script
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="read")
    parser.add_argument("address", nargs="?")
    args = parser.parse_args()
    if args.mode == "read":
        reads(args.address)
    else:
        _emit_error(f"Unsupported mode: {args.mode}. Only 'read' supported.")
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
