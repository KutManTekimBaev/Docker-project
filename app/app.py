import os
import time

import psycopg2
import redis
from flask import Flask, redirect, render_template, request

app = Flask(__name__)

DB_HOST = os.environ.get("DATABASE_HOST", "db")
DB_PORT = int(os.environ.get("DATABASE_PORT", "5432"))
DB_NAME = os.environ.get("DATABASE_NAME", "guestbook")
DB_USER = os.environ.get("DATABASE_USER", "guestbook")
DB_PASSWORD = os.environ.get("DATABASE_PASSWORD")

REDIS_HOST = os.environ.get("REDIS_HOST", "cache")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))

APP_PORT = int(os.environ.get("APP_PORT", "8080"))

if not DB_PASSWORD:
    raise RuntimeError(
        "DATABASE_PASSWORD не задан. Сервис конфигурируется через переменные "
        "окружения — пробросьте их через docker compose."
    )

cache = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


def connect_db() -> psycopg2.extensions.connection:
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        connect_timeout=3,
    )


def wait_for_db(timeout: int = 30) -> None:
    # web-контейнер стартует раньше, чем postgres готов принимать соединения;
    # depends_on только упорядочивает запуск, но не ждёт готовности БД.
    deadline = time.time() + timeout
    while True:
        try:
            connect_db().close()
            return
        except psycopg2.OperationalError:
            if time.time() > deadline:
                raise
            time.sleep(1)


def init_schema() -> None:
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id         SERIAL PRIMARY KEY,
                author     TEXT NOT NULL,
                body       TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        conn.commit()


@app.route("/")
def index() -> str:
    try:
        visits = cache.incr("visits")
    except redis.RedisError:
        visits = None

    with connect_db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT author, body, created_at "
            "FROM messages ORDER BY id DESC LIMIT 50"
        )
        messages = cur.fetchall()

    return render_template("index.html", messages=messages, visits=visits)


@app.route("/messages", methods=["POST"])
def add_message():
    author = (request.form.get("author") or "anon").strip()[:50]
    body = (request.form.get("body") or "").strip()[:500]
    if body:
        with connect_db() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO messages (author, body) VALUES (%s, %s)",
                (author, body),
            )
            conn.commit()
    return redirect("/")


@app.route("/healthz")
def healthz():
    status = {"db": False, "cache": False}
    try:
        with connect_db() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
        status["db"] = True
    except psycopg2.Error:
        pass
    try:
        cache.ping()
        status["cache"] = True
    except redis.RedisError:
        pass

    code = 200 if all(status.values()) else 503
    return status, code


wait_for_db()
init_schema()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=APP_PORT)
