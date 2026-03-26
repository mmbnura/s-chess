# Personal Chess App (Streamlit)

A personal-use online chess app built with Python + Streamlit.

## Features

- Play against a server-side chess engine implemented in Python using `python-chess`.
- Choose your side (White/Black) and difficulty (Easy/Medium/Hard) before starting.
- Chessboard styled like classic green tournament boards with proper SVG chess icons.
- Light board-transition animation after each move, including last-move highlighting.
- Click-to-move board controls using your mouse (select piece, then destination).
- Persist game history in browser local storage.
- Review completed games immediately after play.
- Open and review any previous game from the history page.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Community Cloud notes

- Engine analysis runs on the server process, not in the browser.
- No external Stockfish binary is required.
