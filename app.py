import json
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO
from typing import Any

import chess
import chess.engine
import chess.pgn
import chess.svg
import streamlit as st

try:
    from streamlit_js_eval import streamlit_js_eval
except Exception:  # pragma: no cover - fallback if dependency is unavailable
    streamlit_js_eval = None


APP_TITLE = "Personal Chess Trainer"
HISTORY_KEY = "s_chess_game_history"
DEFAULT_ENGINE_PATH = "stockfish"


@dataclass
class Difficulty:
    name: str
    depth: int
    think_time: float


DIFFICULTIES = {
    "Easy": Difficulty("Easy", depth=8, think_time=0.08),
    "Medium": Difficulty("Medium", depth=14, think_time=0.2),
    "Hard": Difficulty("Hard", depth=20, think_time=0.5),
}


def init_state() -> None:
    defaults = {
        "board": chess.Board(),
        "game_in_progress": False,
        "user_color": chess.WHITE,
        "difficulty": "Medium",
        "history": [],
        "history_loaded": False,
        "engine_path": DEFAULT_ENGINE_PATH,
        "pending_review_game": None,
        "last_saved_ply_count": None,
        "move_error": "",
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
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass
    return []


def save_history_to_local_storage(history: list[dict[str, Any]]) -> None:
    if streamlit_js_eval is None:
        return

    payload = json.dumps(history)
    safe_payload = payload.replace("\\", "\\\\").replace("'", "\\'")
    streamlit_js_eval(
        js_expressions=f"localStorage.setItem('{HISTORY_KEY}', '{safe_payload}')",
        key=f"save_history_local_storage_{len(history)}",
        want_output=False,
    )


def get_engine() -> chess.engine.SimpleEngine | None:
    try:
        return chess.engine.SimpleEngine.popen_uci(st.session_state.engine_path)
    except Exception:
        return None


def render_board(board: chess.Board, user_color: bool, size: int = 480) -> None:
    st.image(chess.svg.board(board, flipped=(user_color == chess.BLACK), size=size))


def start_new_game(user_color_choice: str, difficulty: str) -> None:
    st.session_state.board = chess.Board()
    st.session_state.user_color = chess.WHITE if user_color_choice == "White" else chess.BLACK
    st.session_state.difficulty = difficulty
    st.session_state.game_in_progress = True
    st.session_state.move_error = ""


def compute_engine_move(board: chess.Board, difficulty: Difficulty) -> chess.Move | None:
    engine = get_engine()
    if engine is None:
        return None

    try:
        limit = chess.engine.Limit(depth=difficulty.depth, time=difficulty.think_time)
        result = engine.play(board, limit)
        return result.move
    finally:
        engine.quit()


def build_game_record(board: chess.Board, user_color: bool, difficulty: str) -> dict[str, Any]:
    game = chess.pgn.Game()
    game.headers["Event"] = "Personal Streamlit Chess"
    game.headers["Date"] = datetime.now(timezone.utc).strftime("%Y.%m.%d")
    game.headers["White"] = "You" if user_color == chess.WHITE else f"Engine ({difficulty})"
    game.headers["Black"] = "You" if user_color == chess.BLACK else f"Engine ({difficulty})"
    game.headers["Result"] = board.result(claim_draw=True)

    node = game
    replay_board = chess.Board()
    for move in board.move_stack:
        node = node.add_variation(move)
        replay_board.push(move)

    exporter = StringIO()
    print(game, file=exporter, end="\n\n")

    return {
        "id": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "user_color": "White" if user_color == chess.WHITE else "Black",
        "difficulty": difficulty,
        "result": board.result(claim_draw=True),
        "termination": board.outcome(claim_draw=True).termination.name if board.outcome(claim_draw=True) else "Unknown",
        "ply_count": len(board.move_stack),
        "pgn": exporter.getvalue(),
    }


def save_completed_game(board: chess.Board) -> None:
    game_record = build_game_record(board, st.session_state.user_color, st.session_state.difficulty)
    st.session_state.history.insert(0, game_record)
    st.session_state.last_saved_ply_count = len(board.move_stack)
    save_history_to_local_storage(st.session_state.history)


def run_engine_turn_if_needed() -> None:
    board = st.session_state.board
    if board.is_game_over(claim_draw=True):
        return

    if board.turn != st.session_state.user_color:
        difficulty = DIFFICULTIES[st.session_state.difficulty]
        move = compute_engine_move(board, difficulty)
        if move is None:
            st.error(
                "Stockfish engine could not be started. Set a valid engine binary path in the sidebar."
            )
            return
        board.push(move)


def apply_user_move(move_text: str) -> None:
    board = st.session_state.board
    st.session_state.move_error = ""

    try:
        move = board.parse_san(move_text)
    except ValueError:
        try:
            move = chess.Move.from_uci(move_text)
            if move not in board.legal_moves:
                raise ValueError
        except ValueError:
            st.session_state.move_error = "Invalid move. Use SAN (e4, Nf3) or UCI format (e2e4)."
            return

    if move not in board.legal_moves:
        st.session_state.move_error = "That move is not legal in this position."
        return

    board.push(move)


def parse_pgn_game(pgn_text: str) -> chess.pgn.Game | None:
    try:
        return chess.pgn.read_game(StringIO(pgn_text))
    except Exception:
        return None


def render_play_page() -> None:
    st.header("Play vs Engine")

    with st.sidebar:
        st.subheader("Game Setup")
        color_choice = st.radio("Your side", options=["White", "Black"], index=0)
        difficulty = st.selectbox("Difficulty", options=list(DIFFICULTIES.keys()), index=1)
        engine_path = st.text_input("Stockfish binary path", value=st.session_state.engine_path)
        st.session_state.engine_path = engine_path

        if st.button("Start New Game", use_container_width=True):
            start_new_game(color_choice, difficulty)

    if not st.session_state.game_in_progress:
        st.info("Choose your side and difficulty, then start a game.")
        return

    run_engine_turn_if_needed()

    board = st.session_state.board
    render_board(board, st.session_state.user_color)

    st.caption(f"Turn: {'You' if board.turn == st.session_state.user_color else 'Engine'}")
    st.caption(f"Difficulty: {st.session_state.difficulty}")

    if board.is_game_over(claim_draw=True):
        outcome = board.outcome(claim_draw=True)
        st.success(f"Game over: {board.result(claim_draw=True)} ({outcome.termination.name if outcome else 'Unknown'})")
        if st.session_state.last_saved_ply_count != len(board.move_stack):
            save_completed_game(board)

        if st.button("Review this game"):
            st.session_state.pending_review_game = st.session_state.history[0]
            st.session_state.page = "Game Review"
            st.rerun()
        return

    if board.turn == st.session_state.user_color:
        with st.form("move_form", clear_on_submit=True):
            move_text = st.text_input("Your move", placeholder="e4 or e2e4")
            submitted = st.form_submit_button("Play Move")

            if submitted and move_text.strip():
                apply_user_move(move_text.strip())
                if not st.session_state.move_error:
                    run_engine_turn_if_needed()
                    st.rerun()

        if st.session_state.move_error:
            st.error(st.session_state.move_error)


def render_history_page() -> None:
    st.header("Game History")

    if not st.session_state.history:
        st.info("No games saved yet.")
        return

    for game in st.session_state.history:
        created = datetime.fromisoformat(game["created_at"]).strftime("%Y-%m-%d %H:%M UTC")
        with st.expander(
            f"{created} — You as {game['user_color']} — {game['difficulty']} — {game['result']}"
        ):
            st.write(f"Termination: {game['termination']}")
            st.write(f"Half-moves: {game['ply_count']}")
            st.code(game["pgn"], language="pgn")
            if st.button("Review game", key=f"review_{game['id']}"):
                st.session_state.pending_review_game = game
                st.session_state.page = "Game Review"
                st.rerun()


def render_review_page() -> None:
    st.header("Game Review")

    game_data = st.session_state.pending_review_game
    if game_data is None:
        st.info("Open a game from Play or History to review it here.")
        return

    game = parse_pgn_game(game_data["pgn"])
    if game is None:
        st.error("Could not parse PGN for this game.")
        return

    moves = list(game.mainline_moves())
    max_ply = len(moves)
    current_ply = st.slider("Move", min_value=0, max_value=max_ply, value=0)

    board = game.board()
    current_move_san = None
    for move in moves[:current_ply]:
        current_move_san = board.san(move)
        board.push(move)

    user_color = chess.WHITE if game_data["user_color"] == "White" else chess.BLACK
    render_board(board, user_color)

    if current_ply > 0 and current_move_san:
        st.write(f"Current move: {current_move_san}")
    st.caption(f"Result: {game_data['result']} | Difficulty: {game_data['difficulty']}")


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="♟️", layout="wide")
    init_state()

    if not st.session_state.history_loaded:
        st.session_state.history = load_history_from_local_storage()
        st.session_state.history_loaded = True

    st.title(APP_TITLE)

    if streamlit_js_eval is None:
        st.warning(
            "streamlit-js-eval is unavailable. Browser local-storage persistence is disabled."
        )

    page_options = ["Play", "Game History", "Game Review"]
    current_index = page_options.index(st.session_state.get("page", "Play"))
    st.session_state.page = st.radio("Navigate", options=page_options, horizontal=True, index=current_index)

    if st.session_state.page == "Play":
        render_play_page()
    elif st.session_state.page == "Game History":
        render_history_page()
    else:
        render_review_page()


if __name__ == "__main__":
    main()
