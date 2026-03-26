# Personal Chess App (Streamlit)

A personal-use online chess app built with Python + Streamlit.

## Features

- Play against a server-side chess engine (Stockfish via `python-chess` UCI integration).
- Choose your side (White/Black) and difficulty (Easy/Medium/Hard) before starting.
- Persist game history in browser local storage.
- Review completed games immediately after play.
- Open and review any previous game from the history page.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Community Cloud notes

- This app runs engine analysis on the server process, not in the browser.
- By default the app expects a `stockfish` binary on `PATH`.
- If needed, set a custom engine path in the sidebar.
