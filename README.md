# Chess Arena (Streamlit)

Chess Arena is a Streamlit chess app with a dark “Tournament Hall” UI, Python minimax engine, game history, and review tools.

## Run

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
