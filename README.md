# Chess ELO System

ELO tracker for IRL chess games. Built with Flask + SQLite.

## Dev setup

```bash
# Install dependencies
uv sync

# Set your admin key
cp .env.example .env   # then edit ADMIN_KEY

# Run
uv run python main.py
```

Open `http://localhost:5000`.

The SQLite database (`elo.db`) is created automatically on first run. **If U're the new host, the scores and matches are available in a compact sqlite DB that is straighforward to move between machines**

## create an .env

```
ADMIN_KEY=change-me
```

The admin key is required to delete or add players or matches. In this way we are publicly exposed to criticism, without compromising our database.
