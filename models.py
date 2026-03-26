import sqlite3
from datetime import datetime

DB = "elo.db"
K = 32


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                elo INTEGER NOT NULL DEFAULT 1000,
                wins INTEGER NOT NULL DEFAULT 0,
                losses INTEGER NOT NULL DEFAULT 0,
                draws INTEGER NOT NULL DEFAULT 0,
                avatar TEXT
            );
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                white_id INTEGER NOT NULL REFERENCES players(id),
                black_id INTEGER NOT NULL REFERENCES players(id),
                played_at TEXT NOT NULL,
                winner TEXT NOT NULL CHECK(winner IN ('white','black','draw'))
            );
        """)


def expected(ra, rb):
    return 1 / (1 + 10 ** ((rb - ra) / 400))


def _apply_elo(conn, a_id, b_id, draw=False):
    ra = conn.execute("SELECT elo FROM players WHERE id=?", (a_id,)).fetchone()["elo"]
    rb = conn.execute("SELECT elo FROM players WHERE id=?", (b_id,)).fetchone()["elo"]
    ea, eb = expected(ra, rb), expected(rb, ra)
    sa, sb = (0.5, 0.5) if draw else (1, 0)
    conn.execute("UPDATE players SET elo=? WHERE id=?", (round(ra + K * (sa - ea)), a_id))
    conn.execute("UPDATE players SET elo=? WHERE id=?", (round(rb + K * (sb - eb)), b_id))


def register_match(white_id, black_id, played_at, winner):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO matches (white_id, black_id, played_at, winner) VALUES (?,?,?,?)",
            (white_id, black_id, played_at, winner),
        )
        if winner == "white":
            _apply_elo(conn, white_id, black_id)
            conn.execute("UPDATE players SET wins=wins+1 WHERE id=?", (white_id,))
            conn.execute("UPDATE players SET losses=losses+1 WHERE id=?", (black_id,))
        elif winner == "black":
            _apply_elo(conn, black_id, white_id)
            conn.execute("UPDATE players SET wins=wins+1 WHERE id=?", (black_id,))
            conn.execute("UPDATE players SET losses=losses+1 WHERE id=?", (white_id,))
        else:
            _apply_elo(conn, white_id, black_id, draw=True)
            conn.execute("UPDATE players SET draws=draws+1 WHERE id=?", (white_id,))
            conn.execute("UPDATE players SET draws=draws+1 WHERE id=?", (black_id,))


def get_leaderboard():
    with get_db() as conn:
        return conn.execute(
            "SELECT *, wins+losses+draws AS games FROM players ORDER BY elo DESC"
        ).fetchall()


def get_players():
    with get_db() as conn:
        return conn.execute("SELECT * FROM players ORDER BY name").fetchall()


def get_matches():
    with get_db() as conn:
        return conn.execute("""
            SELECT m.id, m.white_id, m.black_id,
                   w.name AS white, b.name AS black,
                   m.played_at, m.winner
            FROM matches m
            JOIN players w ON m.white_id = w.id
            JOIN players b ON m.black_id = b.id
            ORDER BY m.played_at DESC
        """).fetchall()


def create_player(name):
    with get_db() as conn:
        conn.execute("INSERT INTO players (name) VALUES (?)", (name,))


def set_avatar(player_id, filename):
    with get_db() as conn:
        conn.execute("UPDATE players SET avatar=? WHERE id=?", (filename, player_id))


def delete_player(player_id):
    with get_db() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM matches WHERE white_id=? OR black_id=?",
            (player_id, player_id)
        ).fetchone()[0]
        if count:
            raise ValueError(f"Cannot delete: player has {count} recorded match(es).")
        conn.execute("DELETE FROM players WHERE id=?", (player_id,))


def delete_match(match_id):
    """Delete a match and revert ELO + win/loss/draw counters for both players."""
    with get_db() as conn:
        m = conn.execute("SELECT * FROM matches WHERE id=?", (match_id,)).fetchone()
        if not m:
            raise ValueError("Match not found.")
        w_id, b_id, winner = m["white_id"], m["black_id"], m["winner"]

        # Revert counters
        if winner == "white":
            conn.execute("UPDATE players SET wins=wins-1 WHERE id=?", (w_id,))
            conn.execute("UPDATE players SET losses=losses-1 WHERE id=?", (b_id,))
        elif winner == "black":
            conn.execute("UPDATE players SET wins=wins-1 WHERE id=?", (b_id,))
            conn.execute("UPDATE players SET losses=losses-1 WHERE id=?", (w_id,))
        else:
            conn.execute("UPDATE players SET draws=draws-1 WHERE id=?", (w_id,))
            conn.execute("UPDATE players SET draws=draws-1 WHERE id=?", (b_id,))

        # Revert ELO (apply the inverse result)
        ra = conn.execute("SELECT elo FROM players WHERE id=?", (w_id,)).fetchone()["elo"]
        rb = conn.execute("SELECT elo FROM players WHERE id=?", (b_id,)).fetchone()["elo"]
        ea, eb = expected(ra, rb), expected(rb, ra)
        sa, sb = (0.5, 0.5) if winner == "draw" else ((1, 0) if winner == "white" else (0, 1))
        # reverse: new = old + K*(s-e)  =>  old = new - K*(s-e)
        conn.execute("UPDATE players SET elo=? WHERE id=?", (round(ra - K * (sa - ea)), w_id))
        conn.execute("UPDATE players SET elo=? WHERE id=?", (round(rb - K * (sb - eb)), b_id))

        conn.execute("DELETE FROM matches WHERE id=?", (match_id,))


def get_player(player_id):
    with get_db() as conn:
        player = conn.execute("SELECT *, wins+losses+draws AS games FROM players WHERE id=?", (player_id,)).fetchone()
        history = conn.execute("""
            SELECT m.played_at, m.winner,
                   w.name AS white, b.name AS black,
                   CASE WHEN m.white_id=? THEN 'white' ELSE 'black' END AS side
            FROM matches m
            JOIN players w ON m.white_id = w.id
            JOIN players b ON m.black_id = b.id
            WHERE m.white_id=? OR m.black_id=?
            ORDER BY m.played_at DESC
        """, (player_id, player_id, player_id)).fetchall()
        return player, history
