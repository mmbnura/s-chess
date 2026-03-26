# Chess Arena (Streamlit)

Chess Arena is a Streamlit chess app with a dark “Tournament Hall” UI, Python minimax engine, game history, and review tools.

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

## Highlights

- Dark theme + wood board colors (`#f0d9b5` / `#b58863`)
- Vertical evaluation bar beside the board
- Legal-move dots and capture rings
- Beginner/Easy/Medium/Hard engine levels with iterative deepening and time caps
- Game history cards with summary stats
- Review screen with move navigation and evaluation graph
- Browser localStorage sync via Streamlit components JS injection
