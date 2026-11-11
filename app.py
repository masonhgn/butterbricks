"""the Butterbricks server: serves the static site in web/ and a small JSON API for accounts and saved progress.

The site keeps everything it saves in the browser's localStorage under butterbricks:* keys. A signed-in browser also
sends those keys here, so progress follows the account to other browsers. Answers are still checked in the browser
(sql.js and Pyodide); the server never runs anyone's code.

Run it locally with ./serve.py. On Fly it runs under gunicorn with one process, because the login throttle below
lives in memory and SQLite wants a single writer machine anyway."""

import hmac
import os
import re
import secrets
import sqlite3
import threading
import time
from collections import defaultdict, deque
from datetime import timedelta
from functools import wraps
from urllib.parse import urlsplit

from flask import Flask, abort, g, jsonify, redirect, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "web")
PRODUCTION = bool(os.environ.get("FLY_APP_NAME"))
DATABASE_PATH = os.environ.get("DATABASE_PATH", os.path.join(HERE, "instance", "butterbricks.db"))
INVITE_CODE = os.environ.get("INVITE_CODE", "" if PRODUCTION else "dev")

USERNAME = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
PASSWORD_LENGTH = (8, 200)
MAX_KEY_LENGTH = 200
MAX_VALUE_LENGTH = 256 * 1024
MAX_KEYS_PER_USER = 5000
THROTTLE_WINDOW = 15 * 60  # seconds
THROTTLE_MAX = 10          # failed sign-ins (or bad invite codes) per address or username in that window
# checked against when a username doesn't exist, so a sign-in takes as long either way and doesn't reveal which exist
DUMMY_HASH = generate_password_hash(secrets.token_hex(16))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS saves (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (user_id, key)
);
"""

app = Flask(__name__, static_folder=None)
secret_key = os.environ.get("SECRET_KEY")
if PRODUCTION and not secret_key:
    raise RuntimeError("SECRET_KEY must be set (fly secrets set SECRET_KEY=...)")
app.config.update(
    SECRET_KEY=secret_key or secrets.token_hex(32),  # locally, sessions last until the server restarts
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=PRODUCTION,
    PERMANENT_SESSION_LIFETIME=timedelta(days=90),
    MAX_CONTENT_LENGTH=4 * 1024 * 1024,
)


#database

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE_PATH, timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)


init_db()


#request guards

@app.before_request
def same_origin_json_only():
    """state-changing API calls must be JSON from this site's own pages. A form on another site can't send JSON
    without a CORS preflight, which this server never approves, so this plus SameSite cookies covers CSRF"""
    if request.method in ("GET", "HEAD", "OPTIONS") or not request.path.startswith("/api/"):
        return None
    if not request.is_json:
        return error("Send JSON.", 415)
    origin = request.headers.get("Origin")
    if origin and urlsplit(origin).netloc != request.host:
        return error("Cross-site request refused.", 403)
    return None


_failures = defaultdict(deque)
_failures_lock = threading.Lock()


def client_address():
    return request.headers.get("Fly-Client-IP") or request.remote_addr or "?"


def throttled(*keys):
    now = time.time()
    with _failures_lock:
        for key in keys:
            q = _failures[key]
            while q and q[0] < now - THROTTLE_WINDOW:
                q.popleft()
            if len(q) >= THROTTLE_MAX:
                return True
    return False


def record_failure(*keys):
    with _failures_lock:
        for key in keys:
            _failures[key].append(time.time())


def error(message, status):
    return jsonify({"error": message}), status


def current_user():
    uid = session.get("uid")
    if uid is None:
        return None
    row = db().execute("SELECT id, username FROM users WHERE id = ?", (uid,)).fetchone()
    if row is None:
        session.clear()
    return row


def signed_in(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if user is None:
            return error("Sign in first.", 401)
        return fn(user, *args, **kwargs)
    return wrapper


def start_session(user_id):
    session.clear()
    session["uid"] = user_id
    session.permanent = True


def user_json(row):
    return {"username": row["username"]}


#accounts

@app.get("/api/health")
def health():
    db().execute("SELECT 1").fetchone()
    return jsonify({"ok": True})


@app.get("/api/me")
def me():
    user = current_user()
    return jsonify({"user": user_json(user) if user else None, "signup": bool(INVITE_CODE)})


@app.post("/api/signup")
def signup():
    body = request.get_json(silent=True) or {}
    username = str(body.get("username", "")).strip()
    password = str(body.get("password", ""))
    invite = str(body.get("invite", "")).strip()
    address = client_address()
    if not INVITE_CODE:
        return error("Sign-up is closed.", 403)
    if throttled(f"ip:{address}"):
        return error("Too many attempts. Try again in a few minutes.", 429)
    if not hmac.compare_digest(invite.encode(), INVITE_CODE.encode()):
        record_failure(f"ip:{address}")
        return error("That invite code isn't right.", 403)
    if not USERNAME.match(username):
        return error("Usernames are 3-32 letters, digits, dots, dashes or underscores.", 400)
    if not PASSWORD_LENGTH[0] <= len(password) <= PASSWORD_LENGTH[1]:
        return error(f"Passwords need at least {PASSWORD_LENGTH[0]} characters.", 400)
    try:
        with db():
            cur = db().execute("INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                               (username, generate_password_hash(password), time.time()))
    except sqlite3.IntegrityError:
        return error("That username is taken.", 409)
    start_session(cur.lastrowid)
    return jsonify({"user": {"username": username}})


@app.post("/api/login")
def login():
    body = request.get_json(silent=True) or {}
    username = str(body.get("username", "")).strip()
    password = str(body.get("password", ""))
    keys = (f"ip:{client_address()}", f"user:{username.lower()}")
    if throttled(*keys):
        return error("Too many attempts. Try again in a few minutes.", 429)
    row = db().execute("SELECT id, username, password_hash FROM users WHERE username = ?", (username,)).fetchone()
    if not check_password_hash(row["password_hash"] if row else DUMMY_HASH, password) or row is None:
        record_failure(*keys)
        return error("Wrong username or password.", 401)
    start_session(row["id"])
    return jsonify({"user": user_json(row)})


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})


#saves: one row per localStorage key

@app.get("/api/saves")
@signed_in
def get_saves(user):
    rows = db().execute("SELECT key, value FROM saves WHERE user_id = ?", (user["id"],)).fetchall()
    return jsonify({"saves": {r["key"]: r["value"] for r in rows}})


@app.put("/api/saves")
@signed_in
def put_saves(user):
    """body: {"changes": {key: value, or null to delete}}"""
    changes = (request.get_json(silent=True) or {}).get("changes")
    if not isinstance(changes, dict):
        return error("Expected {\"changes\": {...}}.", 400)
    for key, value in changes.items():
        if not key.startswith("butterbricks:") or len(key) > MAX_KEY_LENGTH:
            return error(f"Bad key: {key[:60]}", 400)
        if value is not None and (not isinstance(value, str) or len(value) > MAX_VALUE_LENGTH):
            return error(f"Value too large or not text: {key[:60]}", 413)
    now = time.time()
    conn = db()
    with conn:
        for key, value in changes.items():
            if value is None:
                conn.execute("DELETE FROM saves WHERE user_id = ? AND key = ?", (user["id"], key))
            else:
                conn.execute("INSERT INTO saves (user_id, key, value, updated_at) VALUES (?, ?, ?, ?) "
                             "ON CONFLICT (user_id, key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                             (user["id"], key, value, now))
        count = conn.execute("SELECT COUNT(*) FROM saves WHERE user_id = ?", (user["id"],)).fetchone()[0]
        if count > MAX_KEYS_PER_USER:
            conn.rollback()
            return error("Too much saved data.", 413)
    return jsonify({"ok": True})


#the static site

@app.get("/", defaults={"path": ""})
@app.get("/<path:path>")
def site(path):
    if path.startswith("api/"):
        abort(404)
    full = os.path.realpath(os.path.join(WEB, path))
    if not full.startswith(os.path.realpath(WEB)):
        abort(404)
    if os.path.isdir(full):
        if path and not path.endswith("/"):
            return redirect(f"/{path}/")
        path = os.path.join(path, "index.html")
    response = send_from_directory(WEB, path)
    # revalidate every time (cheap with the ETag): a deploy should never leave a stale page or script behind
    response.cache_control.no_cache = True
    return response
