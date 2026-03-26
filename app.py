import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO
from typing import Any

import altair as alt
import chess
import chess.pgn
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

APP_TITLE = "Chess Arena"
HISTORY_KEY = "chess_arena_games"

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

PIECE_NAMES = {
    chess.PAWN: "Pawn",
    chess.KNIGHT: "Knight",
    chess.BISHOP: "Bishop",
    chess.ROOK: "Rook",
    chess.QUEEN: "Queen",
    chess.KING: "King",
}

UNICODE_PIECES = {
    "P": "♙",
    "N": "♘",
    "B": "♗",
    "R": "♖",
    "Q": "♕",
    "K": "♔",
    "p": "♟",
    "n": "♞",
    "b": "♝",
    "r": "♜",
    "q": "♛",
    "k": "♚",
}
BOARD_COLORS = {
    "square light": "#EEEED2",
    "square dark": "#769656",
    "coord": "#769656",
    "inner border": "#4b5f3d",
    "outer border": "#4b5f3d",
}

# Piece-square tables (white perspective)
PAWN_TABLE = [
    0, 0, 0, 0, 0, 0, 0, 0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
    5, 5, 10, 25, 25, 10, 5, 5,
    0, 0, 0, 20, 20, 0, 0, 0,
    5, -5, -10, 0, 0, -10, -5, 5,
    5, 10, 10, -20, -20, 10, 10, 5,
    0, 0, 0, 0, 0, 0, 0, 0,
]
KNIGHT_TABLE = [
    -50, -40, -30, -30, -30, -30, -40, -50,
    -40, -20, 0, 5, 5, 0, -20, -40,
    -30, 5, 10, 15, 15, 10, 5, -30,
    -30, 0, 15, 20, 20, 15, 0, -30,
    -30, 5, 15, 20, 20, 15, 5, -30,
    -30, 0, 10, 15, 15, 10, 0, -30,
    -40, -20, 0, 0, 0, 0, -20, -40,
    -50, -40, -30, -30, -30, -30, -40, -50,
]
BISHOP_TABLE = [
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10, 5, 0, 0, 0, 0, 5, -10,
    -10, 10, 10, 10, 10, 10, 10, -10,
    -10, 0, 10, 10, 10, 10, 0, -10,
    -10, 5, 5, 10, 10, 5, 5, -10,
    -10, 0, 5, 10, 10, 5, 0, -10,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -20, -10, -10, -10, -10, -10, -10, -20,
]
ROOK_TABLE = [
    0, 0, 0, 5, 5, 0, 0, 0,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    5, 10, 10, 10, 10, 10, 10, 5,
    0, 0, 0, 0, 0, 0, 0, 0,
]
QUEEN_TABLE = [
    -20, -10, -10, -5, -5, -10, -10, -20,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -10, 0, 5, 5, 5, 5, 0, -10,
    -5, 0, 5, 5, 5, 5, 0, -5,
    0, 0, 5, 5, 5, 5, 0, -5,
    -10, 5, 5, 5, 5, 5, 0, -10,
    -10, 0, 5, 0, 0, 0, 0, -10,
    -20, -10, -10, -5, -5, -10, -10, -20,
]
KING_TABLE = [
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -10, -20, -20, -20, -20, -20, -20, -10,
    20, 20, 0, 0, 0, 0, 20, 20,
    20, 30, 10, 0, 0, 10, 30, 20,
]
PST = {
    chess.PAWN: PAWN_TABLE,
    chess.KNIGHT: KNIGHT_TABLE,
    chess.BISHOP: BISHOP_TABLE,
    chess.ROOK: ROOK_TABLE,
    chess.QUEEN: QUEEN_TABLE,
    chess.KING: KING_TABLE,
}


@dataclass
class Difficulty:
    name: str
    depth: int
    time_limit: float


DIFFICULTIES = {
    "Beginner": Difficulty("Beginner", 2, 1.0),
    "Easy": Difficulty("Easy", 3, 2.0),
    "Medium": Difficulty("Medium", 5, 4.0),
    "Hard": Difficulty("Hard", 7, 8.0),
}


def inject_css() -> None:
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=DM+Serif+Display&family=Fira+Code:wght@400;500&display=swap');
:root {
  --bg-primary:#1a1a2e; --bg-secondary:#16213e; --bg-card:#0f3460; --accent-gold:#e2b04a;
  --accent-green:#5fa85a; --accent-red:#c0392b; --text-primary:#e8e8e8; --text-secondary:#a0a8b8;
  --sq-light:#f0d9b5; --sq-dark:#b58863;
}
h1, h2, h3 { font-family: 'DM Serif Display', serif !important; letter-spacing: .2px; }
html, body, [data-testid="stAppViewContainer"] { font-family: 'DM Sans', sans-serif; }
.stButton > button {
    background: #e2b04a; color: #1a1a2e; font-weight: 700; border: none; border-radius: 8px;
}
.move-history { font-family: 'Fira Code', monospace; font-size: 13px; background:#0f1929; border-radius:8px; padding:12px; }
.status-card { background:#16213e; border:1px solid rgba(255,255,255,0.07); border-radius:12px; padding:14px; }
.game-card { background:#16213e; border:1px solid rgba(255,255,255,0.07); border-radius:12px; padding:16px; margin-bottom:12px; }
.game-card:hover { border-color:rgba(226,176,74,.4); box-shadow: 0 8px 20px rgba(0,0,0,.25); }
.board-shell { display:flex; align-items:flex-start; gap:12px; }
.eval-wrap { width:18px; height:560px; border-radius:6px; border:1px solid rgba(255,255,255,.2); overflow:hidden; background:#111; }
.eval-black { background:#111; width:100%; transition:height .4s ease; }
.eval-white { background:#f7f7f7; width:100%; transition:height .4s ease; }
.eval-score { text-align:center; font-weight:700; margin-top:6px; color:#e2b04a; }
.board-svg { max-width:100%; height:auto; box-shadow:0 12px 48px rgba(0,0,0,.6); border-radius:8px; }
</style>
        """,
        unsafe_allow_html=True,
    )


def init_state() -> None:
    defaults = {
        "board": chess.Board(),
        "game_in_progress": False,
        "user_color": chess.WHITE,
        "difficulty": "Beginner",
        "history": [],
        "history_loaded": False,
        "selected_from": None,
        "pending_review_game": None,
        "review_ply": 0,
        "game_start_ts": None,
        "ai_depth": 0,
        "eval_history": [0.0],
        "page": "Gameplay",
        "last_saved_ply_count": None,
        "storage_bootstrapped": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def bootstrap_local_storage() -> None:
    if st.session_state.storage_bootstrapped:
        return
    payload = json.dumps(history).replace("\\", "\\\\").replace("'", "\\'")
    streamlit_js_eval(
        js_expressions=f"localStorage.setItem('{HISTORY_KEY}', '{payload}')",
        key=f"save_history_local_storage_{len(history)}",
        want_output=False,
    )


def square_label(square: chess.Square) -> str:
    piece = st.session_state.board.piece_at(square)
    symbol = PIECE_SYMBOLS.get(piece.symbol(), "") if piece else "·"
    return f"{symbol} {chess.square_name(square)}"


def render_animated_svg_board(board: chess.Board, flipped: bool, key_suffix: str) -> None:
    lastmove = board.move_stack[-1] if board.move_stack else None
    svg = chess.svg.board(
        board,
        size=560,
        flipped=flipped,
        lastmove=lastmove,
        check=board.king(board.turn) if board.is_check() else None,
        coordinates=True,
        colors=BOARD_COLORS,
    )
    components.html(
        f"""
        <style>
          .chess-wrap svg {{
            width: 100%;
            height: auto;
            animation: fadeIn 240ms ease-out;
          }}
          @keyframes fadeIn {{
            from {{ opacity: 0.65; transform: scale(0.985); }}
            to {{ opacity: 1; transform: scale(1); }}
          }}
        </style>
        <div class="chess-wrap">{svg}</div>
        """,
        height=590,
        key=f"svg_board_{key_suffix}_{len(board.move_stack)}",
    )


def square_is_user_piece(square: chess.Square) -> bool:
    piece = st.session_state.board.piece_at(square)
    return piece is not None and piece.color == st.session_state.user_color


def legal_targets(from_square: chess.Square) -> set[chess.Square]:
    targets: set[chess.Square] = set()
    for move in st.session_state.board.legal_moves:
        if move.from_square == from_square:
            targets.add(move.to_square)
    return targets

    if "ls_games" in st.query_params and not st.session_state.history_loaded:
        try:
            decoded = json.loads(st.query_params["ls_games"])
            if isinstance(decoded, list):
                st.session_state.history = decoded
        except Exception:
            pass
        st.query_params.clear()
        st.session_state.history_loaded = True
        st.session_state.storage_bootstrapped = True
        return

    components.html(
        f"""
        <script>
        const games = localStorage.getItem('{HISTORY_KEY}') || '[]';
        const u = new URL(window.parent.location.href);
        if (!u.searchParams.get('ls_games')) {{
          u.searchParams.set('ls_games', games);
          window.parent.location.replace(u.toString());
        }}
        </script>
        """,
        height=0,
    )
    st.session_state.storage_bootstrapped = True


def persist_history_to_local_storage() -> None:
    payload = json.dumps(st.session_state.history)
    components.html(
        f"""
        <script>
        localStorage.setItem('{HISTORY_KEY}', {json.dumps(payload)});
        </script>
        """,
        height=0,
    )


def pst_value(piece_type: chess.PieceType, square: chess.Square, color: bool) -> int:
    table = PST[piece_type]
    idx = square if color == chess.WHITE else chess.square_mirror(square)
    return table[idx]


def evaluate_board(board: chess.Board) -> int:
    if board.is_checkmate():
        return -100000 if board.turn == chess.WHITE else 100000
    if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
        return 0

    score = 0
    for piece_type, value in PIECE_VALUES.items():
        for sq in board.pieces(piece_type, chess.WHITE):
            score += value + pst_value(piece_type, sq, chess.WHITE)
        for sq in board.pieces(piece_type, chess.BLACK):
            score -= value + pst_value(piece_type, sq, chess.BLACK)
    return score


def minimax(board: chess.Board, depth: int, alpha: int, beta: int, maximizing: bool, start: float, time_limit: float) -> tuple[int, chess.Move | None]:
    if time.time() - start > time_limit:
        return evaluate_board(board), None

    if depth == 0 or board.is_game_over(claim_draw=True):
        return evaluate_board(board), None

    best_move = None
    if maximizing:
        best_score = -10**9
        for mv in board.legal_moves:
            board.push(mv)
            score, _ = minimax(board, depth - 1, alpha, beta, False, start, time_limit)
            board.pop()
            if score > best_score:
                best_score = score
                best_move = mv
            alpha = max(alpha, best_score)
            if beta <= alpha:
                break
        return best_score, best_move

    best_score = 10**9
    for mv in board.legal_moves:
        board.push(mv)
        score, _ = minimax(board, depth - 1, alpha, beta, True, start, time_limit)
        board.pop()
        if score < best_score:
            best_score = score
            best_move = mv
        beta = min(beta, best_score)
        if beta <= alpha:
            break
    return best_score, best_move


def get_best_move(board: chess.Board, difficulty: Difficulty, depth_callback=None) -> tuple[chess.Move | None, float]:
    best_move = None
    best_score = evaluate_board(board) / 100.0
    start = time.time()
    maximizing = board.turn == chess.WHITE

    for depth in range(1, difficulty.depth + 1):
        if time.time() - start > difficulty.time_limit:
            break
        if depth_callback:
            depth_callback(depth)
        score, move = minimax(board, depth, -10**9, 10**9, maximizing, start, difficulty.time_limit)
        if move is not None:
            best_move = move
            best_score = score / 100.0

    return best_move, max(-5.0, min(5.0, best_score))


def move_options_for_user(board: chess.Board, user_color: bool) -> list[tuple[str, chess.Square]]:
    opts = []
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.color == user_color:
            icon = UNICODE_PIECES[piece.symbol()]
            opts.append((f"{icon} {chess.square_name(sq)} ({PIECE_NAMES[piece.piece_type]})", sq))
    return sorted(opts, key=lambda x: x[0])


def destination_options(board: chess.Board, from_square: chess.Square) -> list[tuple[str, chess.Move]]:
    opts = []
    for mv in board.legal_moves:
        if mv.from_square != from_square:
            continue
        target_piece = board.piece_at(mv.to_square)
        marker = "✕" if target_piece else "○"
        opts.append((f"{chess.square_name(mv.to_square)} {marker}", mv))
    return sorted(opts, key=lambda x: x[0])


def render_board_svg(board: chess.Board, flipped: bool, selected: chess.Square | None, legal_targets: set[chess.Square], eval_score: float) -> None:
    files = list(range(8)) if not flipped else list(range(7, -1, -1))
    ranks = list(range(7, -1, -1)) if not flipped else list(range(8))

    last_move = board.peek() if board.move_stack else None
    check_square = board.king(board.turn) if board.is_check() else None

    squares = []
    overlays = []
    pieces = []
    coords = []
    for r_idx, rank in enumerate(ranks):
        for f_idx, file_ in enumerate(files):
            sq = chess.square(file_, rank)
            x = 20 + f_idx * 70
            y = 20 + r_idx * 70
            base = "#f0d9b5" if (file_ + rank) % 2 == 0 else "#b58863"
            squares.append(f'<rect x="{x}" y="{y}" width="70" height="70" fill="{base}"/>')

            if last_move and sq in (last_move.from_square, last_move.to_square):
                overlays.append(f'<rect x="{x}" y="{y}" width="70" height="70" fill="rgba(235,197,68,0.40)"/>')
            if selected is not None and sq == selected:
                overlays.append(f'<rect x="{x}" y="{y}" width="70" height="70" fill="rgba(246,246,105,0.45)"/>')
            if sq == check_square:
                overlays.append(f'<rect x="{x}" y="{y}" width="70" height="70" fill="url(#checkGlow)"/>')

            if sq in legal_targets:
                if board.piece_at(sq):
                    overlays.append(f'<circle cx="{x+35}" cy="{y+35}" r="33" fill="none" stroke="rgba(0,0,0,0.20)" stroke-width="5"/>')
                else:
                    dot = "rgba(0,0,0,0.18)" if (file_ + rank) % 2 == 0 else "rgba(0,0,0,0.25)"
                    overlays.append(f'<circle cx="{x+35}" cy="{y+35}" r="10" fill="{dot}"/>')

            piece = board.piece_at(sq)
            if piece:
                sym = UNICODE_PIECES[piece.symbol()]
                fill = "#ffffff" if piece.color == chess.WHITE else "#111111"
                stroke = "#222" if piece.color == chess.WHITE else "#ddd"
                pieces.append(
                    f'<text x="{x+35}" y="{y+50}" text-anchor="middle" class="piece" fill="{fill}" stroke="{stroke}" stroke-width="0.8">{sym}</text>'
                )

    for i, file_ in enumerate(files):
        letter = chess.FILE_NAMES[file_]
        coords.append(f'<text x="{20 + i*70 + 35}" y="596" text-anchor="middle" style="font-size:11px;fill:#a0a8b8">{letter}</text>')
    for i, rank in enumerate(ranks):
        coords.append(f'<text x="8" y="{20 + i*70 + 40}" style="font-size:11px;fill:#a0a8b8">{rank+1}</text>')

    white_h = int(((eval_score + 5.0) / 10.0) * 560)
    black_h = 560 - white_h
    score_label = f"{eval_score:+.1f}"

    board_svg = f"""
    <div class='board-shell'>
      <div>
        <div class='eval-wrap'>
          <div class='eval-black' style='height:{black_h}px'></div>
          <div class='eval-white' style='height:{white_h}px'></div>
        </div>
        <div class='eval-score'>{score_label}</div>
      </div>
      <svg class='board-svg' viewBox='0 0 600 600' width='600' height='600' xmlns='http://www.w3.org/2000/svg'>
        <defs>
          <radialGradient id='checkGlow' cx='50%' cy='50%' r='50%'>
            <stop offset='0%' stop-color='rgba(192,57,43,0.6)'/>
            <stop offset='70%' stop-color='rgba(192,57,43,0.0)'/>
          </radialGradient>
          <style>
          .piece {{ font-size:54px; line-height:70px; filter:drop-shadow(0px 2px 3px rgba(0,0,0,.5)); user-select:none; transition:transform .1s ease; }}
          </style>
        </defs>
        {''.join(squares)}
        {''.join(overlays)}
        {''.join(pieces)}
        {''.join(coords)}
      </svg>
    </div>
    """
    st.markdown(board_svg, unsafe_allow_html=True)


def run_engine_turn_if_needed() -> None:
    board = st.session_state.board
    if not st.session_state.game_in_progress or board.is_game_over(claim_draw=True):
        return
    if board.turn == st.session_state.user_color:
        return

    depth_placeholder = st.empty()
    with st.spinner("♟ Calculating..."):
        def report_depth(depth: int) -> None:
            st.session_state.ai_depth = depth
            depth_placeholder.caption(f"Searching depth {depth}...")

        move, eval_score = get_best_move(board, DIFFICULTIES[st.session_state.difficulty], depth_callback=report_depth)

    depth_placeholder.empty()
    if move:
        board.push(move)
        st.session_state.eval_history.append(eval_score)


def format_duration(seconds: float) -> str:
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}m {s:02d}s"


def build_game_record(board: chess.Board) -> dict[str, Any]:
    game = chess.pgn.Game()
    game.headers["Event"] = "Chess Arena"
    game.headers["Date"] = datetime.now(timezone.utc).strftime("%Y.%m.%d")
    game.headers["White"] = "You" if st.session_state.user_color == chess.WHITE else f"Engine ({st.session_state.difficulty})"
    game.headers["Black"] = "You" if st.session_state.user_color == chess.BLACK else f"Engine ({st.session_state.difficulty})"
    game.headers["Result"] = board.result(claim_draw=True)
    node = game
    for mv in board.move_stack:
        node = node.add_variation(mv)

    pgn_buff = StringIO()
    print(game, file=pgn_buff, end="\n\n")
    elapsed = (time.time() - st.session_state.game_start_ts) if st.session_state.game_start_ts else 0
    return {
        "id": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "user_color": "White" if st.session_state.user_color == chess.WHITE else "Black",
        "difficulty": st.session_state.difficulty,
        "result": board.result(claim_draw=True),
        "ply_count": len(board.move_stack),
        "duration_s": int(elapsed),
        "evals": st.session_state.eval_history,
        "pgn": pgn_buff.getvalue(),
    }


def save_completed_game_if_needed() -> None:
    board = st.session_state.board
    if not board.is_game_over(claim_draw=True):
        return
    if st.session_state.last_saved_ply_count == len(board.move_stack):
        return

    st.session_state.history.insert(0, build_game_record(board))
    st.session_state.last_saved_ply_count = len(board.move_stack)
    persist_history_to_local_storage()


def start_new_game(side: str, difficulty: str) -> None:
    st.session_state.board = chess.Board()
    st.session_state.game_in_progress = True
    st.session_state.user_color = chess.WHITE if side == "White" else chess.BLACK
    st.session_state.difficulty = difficulty
    st.session_state.selected_from = None
    st.session_state.review_ply = 0
    st.session_state.eval_history = [0.0]
    st.session_state.game_start_ts = time.time()
    st.session_state.last_saved_ply_count = None


def result_emoji(res: str) -> str:
    if res == "1-0":
        return "✅" if st.session_state.user_color == chess.WHITE else "❌"
    if res == "0-1":
        return "✅" if st.session_state.user_color == chess.BLACK else "❌"
    return "🤝"


def move_list_from_board(board: chess.Board) -> list[str]:
    replay = chess.Board()
    pgn_moves: list[str] = []
    for idx, move in enumerate(board.move_stack):
        if replay.turn == chess.WHITE:
            pgn_moves.append(f"{(idx // 2) + 1}.")
        pgn_moves.append(replay.san(move))
        replay.push(move)
    return pgn_moves


def render_click_board(board: chess.Board) -> None:
    render_animated_svg_board(
        board,
        flipped=(st.session_state.user_color == chess.BLACK),
        key_suffix="play",
    )
    st.caption("Click a piece from the grid below, then click its destination.")

    selected = st.session_state.selected_square
    targets = legal_targets(selected) if selected is not None else set()

    ranks = range(7, -1, -1) if st.session_state.user_color == chess.WHITE else range(8)
    files = range(8) if st.session_state.user_color == chess.WHITE else range(7, -1, -1)

    for rank in ranks:
        cols = st.columns(8, gap="small")
        for file_idx, file in enumerate(files):
            square = chess.square(file, rank)
            marker = ""
            if square == selected:
                marker = "🟨"
            elif square in targets:
                marker = "🟩"

            with cols[file_idx]:
                if st.button(
                    f"{marker}{square_label(square)}",
                    key=f"sq_{square}_{len(board.move_stack)}",
                    use_container_width=True,
                ):
                    handle_square_click(square)
                    run_engine_turn_if_needed()
                    st.rerun()


def render_play_page() -> None:
    st.header("Play vs Engine")
    side = st.radio("Your side", ["White", "Black"], horizontal=True)
    difficulty = st.select_slider("Difficulty", options=list(DIFFICULTIES.keys()), value="Medium")

    if st.button("Start New Game", type="primary"):
        start_new_game(side, difficulty)
        run_engine_turn_if_needed()

    if not st.session_state.game_in_progress:
        st.info("♟ Start a game to begin.")
        return

    run_engine_turn_if_needed()
    board = st.session_state.board
    user_turn = board.turn == st.session_state.user_color

    col_board, col_info = st.columns([3, 2], gap="large")

    with col_board:
        user_flipped = st.session_state.user_color == chess.BLACK
        selected = st.session_state.selected_from
        legal_targets = set()
        if selected is not None:
            legal_targets = {mv.to_square for mv in board.legal_moves if mv.from_square == selected}
        eval_now = st.session_state.eval_history[-1] if st.session_state.eval_history else 0.0
        render_board_svg(board, user_flipped, selected, legal_targets, eval_now)

        if user_turn and not board.is_game_over(claim_draw=True):
            from_options = move_options_for_user(board, st.session_state.user_color)
            if from_options:
                from_label_map = {lbl: sq for lbl, sq in from_options}
                selected_label = st.selectbox("From", list(from_label_map.keys()), key="from_select")
                st.session_state.selected_from = from_label_map[selected_label]
                to_options = destination_options(board, st.session_state.selected_from)
                if to_options:
                    to_label_map = {lbl: mv for lbl, mv in to_options}
                    to_label = st.selectbox("To", list(to_label_map.keys()), key="to_select")
                    if st.button("▶ Make Move", use_container_width=True, type="primary"):
                        board.push(to_label_map[to_label])
                        eval_after = evaluate_board(board) / 100.0
                        st.session_state.eval_history.append(max(-5.0, min(5.0, eval_after)))
                        run_engine_turn_if_needed()
                        st.rerun()

            st.caption("Select your piece · Select destination · Click Move")
            st.caption("Keyboard hint: click dropdown then type square name (e.g., e2, e4)")

    with col_info:
        elapsed = (time.time() - st.session_state.game_start_ts) if st.session_state.game_start_ts else 0
        turn_dot = "⚪" if board.turn == chess.WHITE else "⚫"
        st.markdown(
            f"""
            <div class='status-card'>
              <b>Turn:</b> {turn_dot} {'White' if board.turn == chess.WHITE else 'Black'}<br/>
              <b>Move #:</b> {board.fullmove_number}<br/>
              <b>Time elapsed:</b> {format_duration(elapsed)}
            </div>
            """,
            unsafe_allow_html=True,
        )

        if board.is_check() and not board.is_game_over(claim_draw=True):
            st.error("⚠️ Your king is in check!" if user_turn else "⚠️ Engine king is in check!")

        moves = []
        replay = chess.Board()
        for idx, mv in enumerate(board.move_stack):
            if replay.turn == chess.WHITE:
                moves.append(f"{(idx//2)+1}.")
            moves.append(replay.san(mv))
            replay.push(mv)
        st.markdown("<div class='move-history'>" + (" ".join(moves) if moves else "No moves yet") + "</div>", unsafe_allow_html=True)

    if board.is_game_over(claim_draw=True):
        save_completed_game_if_needed()
        res = board.result(claim_draw=True)
        emoji = "🏆" if result_emoji(res) == "✅" else ("💀" if result_emoji(res) == "❌" else "🤝")
        st.success(f"{emoji} Game over: {res}")
        a, b = st.columns(2)
        if a.button("Review this game", use_container_width=True):
            st.session_state.pending_review_game = st.session_state.history[0]
            st.session_state.page = "Game Review"
            st.rerun()
        if b.button("Play again", use_container_width=True):
            start_new_game("White" if st.session_state.user_color == chess.WHITE else "Black", st.session_state.difficulty)
            run_engine_turn_if_needed()
            st.rerun()


def parse_game(pgn_text: str) -> chess.pgn.Game | None:
    try:
        return chess.pgn.read_game(StringIO(pgn_text))
    except Exception:
        return None


def render_history() -> None:
    st.subheader("Game History")
    games = st.session_state.history
    if not games:
        st.markdown("### ♟ No games yet.")
        st.caption("Start a game to build your history!")
        if st.button("Play Now →"):
            st.session_state.page = "Gameplay"
            st.rerun()
        return

    wins = losses = draws = total_dur = 0
    for g in games:
        total_dur += g.get("duration_s", 0)
        user_white = g.get("user_color") == "White"
        res = g.get("result", "1/2-1/2")
        if (res == "1-0" and user_white) or (res == "0-1" and not user_white):
            wins += 1
        elif res == "1/2-1/2":
            draws += 1
        else:
            losses += 1
    avg_dur = total_dur / max(1, len(games))
    st.markdown(f"✅ {wins} Wins &nbsp;&nbsp;&nbsp; ❌ {losses} Losses &nbsp;&nbsp;&nbsp; 🤝 {draws} Draw &nbsp;&nbsp;&nbsp; ⏱ Avg: {format_duration(avg_dur)}")

    for g in games:
        created = datetime.fromisoformat(g["created_at"]).strftime("%Y-%m-%d %H:%M UTC")
        emoji = "✅" if ((g["result"] == "1-0" and g["user_color"] == "White") or (g["result"] == "0-1" and g["user_color"] == "Black")) else ("🤝" if g["result"] == "1/2-1/2" else "❌")
        st.markdown(
            f"""
            <div class='game-card'>
                <div style='display:flex;justify-content:space-between;align-items:center;'>
                    <div style='font-size:24px'>{emoji}</div>
                    <div><b>{g['difficulty']}</b></div>
                    <div style='color:#a0a8b8'>{created}</div>
                </div>
                <div style='margin-top:8px;color:#e8e8e8;'>
                    {'♔ White' if g['user_color']=='White' else '♚ Black'} · {g['ply_count']} ply · {format_duration(g.get('duration_s',0))}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Review", key=f"review_{g['id']}"):
            st.session_state.pending_review_game = g
            st.session_state.page = "Game Review"
            st.rerun()


def render_review() -> None:
    st.subheader("Game Review")
    data = st.session_state.pending_review_game
    if not data:
        st.info("Select a game from history or finish a game first.")
        return

    game = parse_game(data["pgn"])
    if game is None:
        st.error("Failed to parse PGN.")
        return

    moves = list(game.mainline_moves())
    nav = st.columns([1, 1, 1, 1, 6])
    if nav[0].button("|◀"):
        st.session_state.review_ply = 0
    if nav[1].button("◀"):
        st.session_state.review_ply = max(0, st.session_state.review_ply - 1)
    if nav[2].button("▶"):
        st.session_state.review_ply = min(len(moves), st.session_state.review_ply + 1)
    if nav[3].button("▶|"):
        st.session_state.review_ply = len(moves)

    st.session_state.review_ply = st.slider("Jump to move", 0, len(moves), st.session_state.review_ply)

    board = game.board()
    for mv in moves[: st.session_state.review_ply]:
        board.push(mv)

    left, right = st.columns([3, 2], gap="large")
    with left:
        evals = data.get("evals", [0.0])
        idx = min(st.session_state.review_ply, len(evals) - 1)
        render_board_svg(board, data.get("user_color") == "Black", None, set(), float(evals[idx]))

    cols = st.columns([2, 1])
    with cols[0]:
        user_color = chess.WHITE if game_data["user_color"] == "White" else chess.BLACK
        render_animated_svg_board(board, flipped=(user_color == chess.BLACK), key_suffix="review")
    with cols[1]:
        st.subheader("Review Notes")
        st.write(f"Result: **{game_data['result']}**")
        st.write(f"Difficulty: **{game_data['difficulty']}**")
        st.code(" ".join(san_history) or "Start position")


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="♟", layout="wide")
    inject_css()
    init_state()
    bootstrap_local_storage()

    st.title("♟ Chess Arena")
    st.caption("Cold start notice: first load on Streamlit Community Cloud can take 10–15 seconds.")

    pages = ["Gameplay", "Game History", "Game Review"]
    default_idx = pages.index(st.session_state.page) if st.session_state.page in pages else 0
    st.session_state.page = st.radio("Navigate", pages, horizontal=True, index=default_idx)

    if st.session_state.page == "Gameplay":
        render_gameplay()
    elif st.session_state.page == "Game History":
        render_history()
    else:
        render_review()


if __name__ == "__main__":
    main()
