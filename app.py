import os
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session
from models import (
    init_db,
    create_player,
    delete_player,
    get_players,
    get_leaderboard,
    get_matches,
    register_match,
    get_player,
    set_avatar,
    delete_match,
    get_last_match_date,
    get_site_stats,
)

load_dotenv()

AVATAR_DIR = os.path.join("static", "images", "avatars")
ALLOWED = {"png", "jpg", "jpeg", "gif", "webp"}

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "elo-chess-dev-secret")


def is_admin():
    return session.get("admin") is True


@app.context_processor
def inject_admin():
    stats = get_site_stats()
    return {
        "is_admin": is_admin(),
        "last_match_date": get_last_match_date(),
        "site_players": stats["players"],
        "site_matches": stats["matches"],
    }


@app.before_request
def setup():
    init_db()


# --- Auth ---


@app.route("/admin/unlock", methods=["POST"])
def admin_unlock():
    key = request.form.get("admin_key", "").strip()
    next_url = request.form.get("next") or url_for("leaderboard")
    if key == os.environ.get("ADMIN_KEY", ""):
        session["admin"] = True
        flash("Admin mode enabled.", "success")
    else:
        flash("Invalid admin key.", "error")
    return redirect(next_url)


@app.route("/admin/lock", methods=["POST"])
def admin_lock():
    session.pop("admin", None)
    flash("Admin mode disabled.", "success")
    return redirect(request.referrer or url_for("leaderboard"))


# --- Views ---


@app.route("/")
def leaderboard():
    return render_template("leaderboard.html", players=get_leaderboard())


@app.route("/players", methods=["GET", "POST"])
def players():
    if request.method == "POST":
        if not is_admin():
            flash("Admin access required.", "error")
            return redirect(url_for("players"))
        name = request.form["name"].strip()
        if name:
            try:
                create_player(name)
                flash(f"Player '{name}' created.", "success")
            except Exception:
                flash(f"Player '{name}' already exists.", "error")
        return redirect(url_for("players"))
    return render_template("players.html", players=get_players())


@app.route("/players/<int:player_id>/delete", methods=["POST"])
def delete_player_route(player_id):
    if not is_admin():
        flash("Admin access required.", "error")
        return redirect(url_for("players"))
    try:
        delete_player(player_id)
        flash("Player deleted.", "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("players"))


@app.route("/players/<int:player_id>")
def player_stats(player_id):
    player, history = get_player(player_id)
    if not player:
        flash("Player not found.", "error")
        return redirect(url_for("players"))
    return render_template("player_stats.html", player=player, history=history)


@app.route("/players/<int:player_id>/avatar", methods=["POST"])
def upload_avatar(player_id):
    if not is_admin():
        flash("Admin access required.", "error")
        return redirect(url_for("player_stats", player_id=player_id))
    file = request.files.get("avatar")
    if not file or not file.filename:
        flash("No file selected.", "error")
        return redirect(url_for("player_stats", player_id=player_id))
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED:
        flash("Invalid file type.", "error")
        return redirect(url_for("player_stats", player_id=player_id))
    filename = f"{player_id}.{ext}"
    for f in os.listdir(AVATAR_DIR):
        if f.startswith(f"{player_id}."):
            os.remove(os.path.join(AVATAR_DIR, f))
    file.save(os.path.join(AVATAR_DIR, filename))
    set_avatar(player_id, filename)
    flash("Avatar updated.", "success")
    return redirect(url_for("player_stats", player_id=player_id))


@app.route("/matches", methods=["GET", "POST"])
def matches():
    players_list = get_players()
    now = datetime.now().strftime("%Y-%m-%dT%H:%M")
    if request.method == "POST":
        if not is_admin():
            flash("Admin access required.", "error")
            return redirect(url_for("matches"))
        white_id = request.form["white_id"]
        black_id = request.form["black_id"]
        played_at = request.form["played_at"]
        winner = request.form["winner"]
        if white_id == black_id:
            flash("White and black must be different players.", "error")
        else:
            try:
                register_match(int(white_id), int(black_id), played_at, winner)
                flash("Match registered.", "success")
            except Exception as e:
                flash(f"Error: {e}", "error")
        return redirect(url_for("matches"))
    return render_template(
        "matches.html", players=players_list, matches=get_matches(), now=now
    )


@app.route("/matches/<int:match_id>/delete", methods=["POST"])
def delete_match_route(match_id):
    if not is_admin():
        flash("Admin access required.", "error")
        return redirect(url_for("matches"))
    try:
        delete_match(match_id)
        flash("Match deleted and ELO reverted.", "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("matches"))


if __name__ == "__main__":
    app.run(debug=True)
