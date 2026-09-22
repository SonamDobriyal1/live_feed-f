"""Daycare web dashboard.

Independent of the Pi ML service. Pi uploads to Cloudinary and POSTs here.
Save / delete / midnight purge all run on this service.
Login: camera IP + camera password.
"""

from __future__ import annotations

from functools import wraps

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

import db as store
from cloudinary_util import destroy_asset
from config import (
    DAYCARE_TZ,
    PORTAL_DEBUG,
    PORTAL_INGEST_KEY,
    PORTAL_PORT,
    PORTAL_SECRET_KEY,
    WEB_TENANTS,
)

app = Flask(__name__)
app.secret_key = PORTAL_SECRET_KEY
store.init_db()
store.bootstrap_tenants(WEB_TENANTS)


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("camera_ip"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)

    return wrapper


def ingest_authorized() -> bool:
    key = request.headers.get("X-Ingest-Key") or request.args.get("key")
    return bool(PORTAL_INGEST_KEY) and key == PORTAL_INGEST_KEY


def remove_from_cloud_and_db(row) -> None:
    public_id = row["cloudinary_public_id"] if row else None
    if public_id:
        destroy_asset(public_id)
    store.delete_detection(int(row["id"]))


def purge_expired() -> int:
    rows = store.expired_unsaved()
    removed = 0
    for row in rows:
        remove_from_cloud_and_db(row)
        removed += 1
    return removed


@app.route("/health")
def health():
    return jsonify({"ok": True, "service": "daycare-dashboard"})


@app.route("/")
def home():
    if session.get("camera_ip"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        camera_ip = (request.form.get("camera_ip") or "").strip()
        password = request.form.get("password") or ""
        tenant = store.authenticate(camera_ip, password)
        if tenant is None:
            flash("Camera IP or password is incorrect.", "error")
            return render_template("login.html"), 401
        session["camera_ip"] = tenant["camera_ip"]
        session["daycare_name"] = tenant["daycare_name"]
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    purge_expired()
    camera_ip = session["camera_ip"]
    rows = store.list_detections(camera_ip)
    saved = [r for r in rows if r["saved"]]
    today = [r for r in rows if not r["saved"]]
    return render_template(
        "dashboard.html",
        daycare_name=session.get("daycare_name") or camera_ip,
        camera_ip=camera_ip,
        today=today,
        saved=saved,
        daycare_tz=DAYCARE_TZ,
    )


@app.route("/detections/<int:det_id>/save", methods=["POST"])
@login_required
def save_detection(det_id: int):
    row = store.set_saved(det_id, session["camera_ip"], True)
    if row is None:
        flash("Detection not found.", "error")
    else:
        flash("Detection saved. It will stay on the portal.", "ok")
    return redirect(url_for("dashboard"))


@app.route("/detections/<int:det_id>/unsave", methods=["POST"])
@login_required
def unsave_detection(det_id: int):
    row = store.set_saved(det_id, session["camera_ip"], False)
    if row is None:
        flash("Detection not found.", "error")
    else:
        flash("Save removed. This detection will be deleted at midnight if still unsaved.", "ok")
    return redirect(url_for("dashboard"))


@app.route("/detections/<int:det_id>/delete", methods=["POST"])
@login_required
def delete_detection(det_id: int):
    row = store.get_detection(det_id, session["camera_ip"])
    if row is None:
        flash("Detection not found.", "error")
        return redirect(url_for("dashboard"))
    public_id = row["cloudinary_public_id"]
    store.delete_detection(det_id)
    if public_id:
        destroy_asset(public_id)
    flash("Detection deleted from the portal and Cloudinary.", "ok")
    return redirect(url_for("dashboard"))


@app.route("/api/detections", methods=["POST"])
def ingest_detection():
    if not ingest_authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    camera_ip = str(payload.get("camera_ip") or "").strip()
    if not camera_ip:
        return jsonify({"ok": False, "error": "camera_ip required"}), 400
    tenant = store.get_tenant(camera_ip)
    if tenant is None:
        return jsonify({"ok": False, "error": "unknown camera_ip — register this daycare first"}), 404
    purge_expired()
    det_id = store.insert_detection(payload)
    return jsonify({"ok": True, "id": det_id})


@app.route("/api/purge", methods=["POST", "GET"])
def api_purge():
    if not ingest_authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    n = purge_expired()
    return jsonify({"ok": True, "removed": n})


def main() -> None:
    store.init_db()
    print(f"Daycare web dashboard → http://127.0.0.1:{PORTAL_PORT}")
    app.run(host="0.0.0.0", port=PORTAL_PORT, debug=PORTAL_DEBUG)


if __name__ == "__main__":
    main()
