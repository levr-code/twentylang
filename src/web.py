from __future__ import annotations

import flask
import hashlib
import hmac
import secrets

from flask_socketio import SocketIO, emit

from .runners import split_by_not_in_blocks_or_strings

app = flask.Flask(__name__)
app.secret_key = secrets.token_hex(32)
socketio = SocketIO(app, manage_session=True)


def verify_password(password: str, stored: str) -> bool:
    """
    stored format: salt_hex:key_hex
    """
    salt_hex, key_hex = stored.split(":")
    salt = bytes.fromhex(salt_hex)
    stored_key = bytes.fromhex(key_hex)
    new_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return hmac.compare_digest(new_key, stored_key)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        200_000,
    )
    return salt.hex() + ":" + key.hex()


class Server:
    """
    Multi-user web-based IDE environment with authentication and sandboxed code execution.
    """
    def __init__(self, env_cls, rcls):
        self.env_cls = env_cls
        self.runner_cls = rcls
        self.users_to_pass_hashes: dict[str, str] = {}
        self.sandboxes: dict[str, object] = {}

    def init_server(self, auth_template: str, ide_template: str):
        @app.route("/auth")
        def auth():
            return flask.render_template(auth_template)

        @app.route("/auth/done", methods=["GET", "POST"])
        def authdone():
            if flask.request.method != "POST":
                return flask.redirect("/auth")

            username = (flask.request.form.get("user") or "").strip()
            password = flask.request.form.get("pass") or ""

            if not username or not password.strip():
                return flask.redirect("/auth")

            if username not in self.users_to_pass_hashes:
                self.users_to_pass_hashes[username] = hash_password(password)
                self.sandboxes[username] = self.env_cls()
            else:
                if not verify_password(password, self.users_to_pass_hashes[username]):
                    return flask.redirect("/auth")

            flask.session["user"] = username
            return flask.redirect("/")

        @app.route("/")
        def home():
            if "user" not in flask.session:
                return flask.redirect("/auth")

            user = flask.session["user"]
            if user not in self.sandboxes:
                self.sandboxes[user] = self.env_cls()

            return flask.render_template(ide_template, user=user)

        @socketio.on("run_code")
        def handle_client_message(data):
            if "user" not in flask.session:
                return False

            text = (data or {}).get("text")
            if not isinstance(text, str):
                emit("server", "Error: input must be a string")
                self.sandboxes[flask.session["user"]].output("Error: input must be a string")
                return False

            emit("clear", "")

            envir = self.sandboxes[flask.session["user"]]
            for i in split_by_not_in_blocks_or_strings(text, "\n"):
                if i.strip():
                    self.runner_cls.from_string(i, envir).run()

            return True

    def run(self, host: str, port: int):
        """Runs server as a flask application"""
        socketio.run(host, port)
