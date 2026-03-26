import json
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO
from typing import Any

import chess
import chess.pgn
import chess.svg
import streamlit as st

try:
    from streamlit_js_eval import streamlit_js_eval
except Exception:  # pragma: no cover
    streamlit_js_eval = None


APP_TITLE = "Personal Chess Trainer"
HISTORY_KEY = "s_chess_game_history"
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}
PIECE_SYMBOLS = {
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


@dataclass
class Difficulty:
    name: str
    depth: int
    randomness: float


DIFFICULTIES = {
    "Easy": Difficulty("Easy", depth=1, randomness=0.35),
    "Medium": Difficulty("Medium", depth=2, randomness=0.15),
    "Hard": Difficulty("Hard", depth=3, randomness=0.0),
}


def init_state() -> None:
    defaults = {
        "board": chess.Board(),
        "game_in_progress": False,
        "user_color": chess.WHITE,
        "difficulty": "Medium",
        "history": [],
        "history_loaded": False,
        "pending_review_game": None,
        "last_saved_ply_count": None,
        "selected_square": None,
        "move_error": "",
        "page": "Play",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def load_history_from_local_storage() -> list[dict[str, Any]]:
    if streamlit_js_eval is None:
        return st.session_state.history
    raw_value = streamlit_js_eval(
        js_expressions=f"localStorage.getItem('{HISTORY_KEY}')",
        key="load_history_local_storage",
    )
    if raw_value in (None, "null", ""):
        return []
    try:
        parsed = json.loads(raw_value)
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


def save_history_to_local_storage(history: list[dict[str, Any]]) -> None:
    if streamlit_js_eval is None:
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
    return f"{symbol}\n{chess.square_name(square)}"


def square_is_user_piece(square: chess.Square) -> bool:
    piece = st.session_state.board.piece_at(square)
    return piece is not None and piece.color == st.session_state.user_color


def legal_targets(from_square: chess.Square) -> set[chess.Square]:
    targets: set[chess.Square] = set()
    for move in st.session_state.board.legal_moves:
        if move.from_square == from_square:
            targets.add(move.to_square)
    return targets


def handle_square_click(square: chess.Square) -> None:
    board = st.session_state.board
    if board.turn != st.session_state.user_color or board.is_game_over(claim_draw=True):
        return

    selected = st.session_state.selected_square

    if selected is None:
        if square_is_user_piece(square):
            st.session_state.selected_square = square
        else:
            st.session_state.move_error = "Select one of your own pieces first."
        return

    if square == selected:
        st.session_state.selected_square = None
        return

    candidate_moves = [
        move for move in board.legal_moves if move.from_square == selected and move.to_square == square
    ]

    if not candidate_moves:
        if square_is_user_piece(square):
            st.session_state.selected_square = square
            st.session_state.move_error = ""
        else:
            st.session_state.move_error = "Illegal destination for selected piece."
        return

    move = candidate_moves[0]
    if len(candidate_moves) > 1:
        promotions = [m for m in candidate_moves if m.promotion == chess.QUEEN]
        move = promotions[0] if promotions else candidate_moves[0]

    board.push(move)
    st.session_state.selected_square = None
    st.session_state.move_error = ""


def evaluate_board(board: chess.Board) -> int:
    if board.is_checkmate():
        return -100000 if board.turn == chess.WHITE else 100000
    if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
        return 0

    score = 0
    for piece_type, value in PIECE_VALUES.items():
        score += len(board.pieces(piece_type, chess.WHITE)) * value
        score -= len(board.pieces(piece_type, chess.BLACK)) * value

    # mobility bonus
    score += len(list(board.legal_moves)) * (3 if board.turn == chess.WHITE else -3)
    return score


def minimax(board: chess.Board, depth: int, alpha: int, beta: int, maximizing: bool) -> int:
    if depth == 0 or board.is_game_over(claim_draw=True):
        return evaluate_board(board)

    if maximizing:
        value = -10**9
        for move in board.legal_moves:
            board.push(move)
            value = max(value, minimax(board, depth - 1, alpha, beta, False))
            board.pop()
            alpha = max(alpha, value)
            if alpha >= beta:
                break
        return value

    value = 10**9
    for move in board.legal_moves:
        board.push(move)
        value = min(value, minimax(board, depth - 1, alpha, beta, True))
        board.pop()
        beta = min(beta, value)
        if alpha >= beta:
            break
    return value


def engine_move(board: chess.Board, difficulty: Difficulty) -> chess.Move | None:
    legal = list(board.legal_moves)
    if not legal:
        return None

    scored_moves: list[tuple[int, chess.Move]] = []
    maximizing = board.turn == chess.WHITE

    for move in legal:
        board.push(move)
        score = minimax(board, difficulty.depth, -10**9, 10**9, not maximizing)
        board.pop()
        scored_moves.append((score, move))

    scored_moves.sort(key=lambda x: x[0], reverse=maximizing)

    top_n = max(1, int(len(scored_moves) * difficulty.randomness))
    candidate_bucket = scored_moves[: top_n + 1]
    return candidate_bucket[0][1]


def build_game_record(board: chess.Board, user_color: bool, difficulty: str) -> dict[str, Any]:
    game = chess.pgn.Game()
    game.headers["Event"] = "Personal Streamlit Chess"
    game.headers["Date"] = datetime.now(timezone.utc).strftime("%Y.%m.%d")
    game.headers["White"] = "You" if user_color == chess.WHITE else f"Engine ({difficulty})"
    game.headers["Black"] = "You" if user_color == chess.BLACK else f"Engine ({difficulty})"
    game.headers["Result"] = board.result(claim_draw=True)

    node = game
    for move in board.move_stack:
        node = node.add_variation(move)

    exporter = StringIO()
    print(game, file=exporter, end="\n\n")

    outcome = board.outcome(claim_draw=True)
    return {
        "id": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "user_color": "White" if user_color == chess.WHITE else "Black",
        "difficulty": difficulty,
        "result": board.result(claim_draw=True),
        "termination": outcome.termination.name if outcome else "Unknown",
        "ply_count": len(board.move_stack),
        "pgn": exporter.getvalue(),
    }


def save_completed_game(board: chess.Board) -> None:
    game_record = build_game_record(board, st.session_state.user_color, st.session_state.difficulty)
    st.session_state.history.insert(0, game_record)
    st.session_state.last_saved_ply_count = len(board.move_stack)
    save_history_to_local_storage(st.session_state.history)


def start_new_game(side: str, difficulty: str) -> None:
    st.session_state.board = chess.Board()
    st.session_state.user_color = chess.WHITE if side == "White" else chess.BLACK
    st.session_state.difficulty = difficulty
    st.session_state.game_in_progress = True
    st.session_state.last_saved_ply_count = None
    st.session_state.selected_square = None
    st.session_state.move_error = ""


def run_engine_turn_if_needed() -> None:
    board = st.session_state.board
    if board.is_game_over(claim_draw=True):
        return
    if board.turn == st.session_state.user_color:
        return

    move = engine_move(board, DIFFICULTIES[st.session_state.difficulty])
    if move:
        board.push(move)


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
        st.info("Start a game to begin.")
        return

    run_engine_turn_if_needed()
    board = st.session_state.board

    left, right = st.columns([2, 1])
    with left:
        render_click_board(board)
        if st.session_state.move_error:
            st.error(st.session_state.move_error)

    with right:
        st.subheader("Game Info")
        st.write(f"**You:** {('White' if st.session_state.user_color == chess.WHITE else 'Black')}")
        st.write(f"**Level:** {st.session_state.difficulty}")
        st.write(f"**Turn:** {'You' if board.turn == st.session_state.user_color else 'Engine'}")

        st.subheader("Moves")
        st.code(" ".join(move_list_from_board(board)) or "No moves yet")

    if board.is_game_over(claim_draw=True):
        outcome = board.outcome(claim_draw=True)
        st.success(f"Game over: {board.result(claim_draw=True)} ({outcome.termination.name if outcome else 'Unknown'})")
        if st.session_state.last_saved_ply_count != len(board.move_stack):
            save_completed_game(board)

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Review this game", use_container_width=True):
                st.session_state.pending_review_game = st.session_state.history[0]
                st.session_state.page = "Game Review"
                st.rerun()
        with c2:
            if st.button("Play again", use_container_width=True):
                start_new_game("White" if st.session_state.user_color == chess.WHITE else "Black", st.session_state.difficulty)
                run_engine_turn_if_needed()
                st.rerun()


def parse_pgn_game(pgn_text: str) -> chess.pgn.Game | None:
    try:
        return chess.pgn.read_game(StringIO(pgn_text))
    except Exception:
        return None


def render_history_page() -> None:
    st.header("Game History")
    if not st.session_state.history:
        st.info("No games saved yet.")
        return

    for game in st.session_state.history:
        created = datetime.fromisoformat(game["created_at"]).strftime("%Y-%m-%d %H:%M UTC")
        with st.expander(f"{created} | {game['user_color']} | {game['difficulty']} | {game['result']}"):
            st.write(f"Termination: {game['termination']}")
            st.write(f"Moves: {game['ply_count']}")
            if st.button("Review", key=f"review_{game['id']}", type="primary"):
                st.session_state.pending_review_game = game
                st.session_state.page = "Game Review"
                st.rerun()


def render_review_page() -> None:
    st.header("Game Review")
    game_data = st.session_state.pending_review_game
    if game_data is None:
        st.info("Select a game from History or finish a game to review.")
        return

    game = parse_pgn_game(game_data["pgn"])
    if game is None:
        st.error("Could not parse PGN.")
        return

    moves = list(game.mainline_moves())
    if "review_ply" not in st.session_state:
        st.session_state.review_ply = 0

    controls = st.columns([1, 1, 1, 1, 4])
    with controls[0]:
        if st.button("⏮", key="rv_first"):
            st.session_state.review_ply = 0
    with controls[1]:
        if st.button("◀", key="rv_prev"):
            st.session_state.review_ply = max(0, st.session_state.review_ply - 1)
    with controls[2]:
        if st.button("▶", key="rv_next"):
            st.session_state.review_ply = min(len(moves), st.session_state.review_ply + 1)
    with controls[3]:
        if st.button("⏭", key="rv_last"):
            st.session_state.review_ply = len(moves)

    st.session_state.review_ply = st.slider(
        "Move", 0, len(moves), st.session_state.review_ply, key="rv_slider"
    )

    board = game.board()
    san_history: list[str] = []
    for idx, move in enumerate(moves[: st.session_state.review_ply]):
        if board.turn == chess.WHITE:
            san_history.append(f"{(idx // 2) + 1}.")
        san_history.append(board.san(move))
        board.push(move)

    cols = st.columns([2, 1])
    with cols[0]:
        user_color = chess.WHITE if game_data["user_color"] == "White" else chess.BLACK
        st.image(chess.svg.board(board, flipped=(user_color == chess.BLACK), size=520))
    with cols[1]:
        st.subheader("Review Notes")
        st.write(f"Result: **{game_data['result']}**")
        st.write(f"Difficulty: **{game_data['difficulty']}**")
        st.code(" ".join(san_history) or "Start position")


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="♟️", layout="wide")
    init_state()

    if not st.session_state.history_loaded:
        st.session_state.history = load_history_from_local_storage()
        st.session_state.history_loaded = True

    st.title(APP_TITLE)
    if streamlit_js_eval is None:
        st.warning("streamlit-js-eval unavailable; local-storage sync disabled.")

    pages = ["Play", "Game History", "Game Review"]
    index = pages.index(st.session_state.page) if st.session_state.page in pages else 0
    st.session_state.page = st.radio("Navigate", pages, horizontal=True, index=index)

    if st.session_state.page == "Play":
        render_play_page()
    elif st.session_state.page == "Game History":
        render_history_page()
    else:
        render_review_page()


if __name__ == "__main__":
    main()
