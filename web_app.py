#!/usr/bin/env python3
"""Locket Gold demo web app.

This app checks a supplied identifier against an explicitly configured test
endpoint. It does not mutate accounts or install device/network profiles.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import aiohttp
from flask import Flask, jsonify, render_template, request, send_from_directory

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
FAKE_RC_URL = os.getenv("FAKE_RC_URL", "https://locketgold.hoanganh1mw.workers.dev").strip().rstrip("/")
REMOTE_STATUS_ENABLED = True  # Bật luôn để check remote status
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=float(os.getenv("REQUEST_TIMEOUT", "10")))
UID_PATTERN = re.compile(r"^[A-Za-z0-9]{28}$")
ALLOWED_PROFILE_HOSTS = {"locket.cam", "www.locket.cam", "locketapp.com", "www.locketapp.com"}

app = Flask(__name__)
app.config.update(MAX_CONTENT_LENGTH=4 * 1024, JSON_SORT_KEYS=False)
_state_lock = threading.Lock()
_last_result: Optional[Dict[str, Any]] = None


def _run_async(coro: Any) -> Any:
    """Run a coroutine safely from sync Flask handlers."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    value: List[Any] = []
    error: List[BaseException] = []

    def runner() -> None:
        try:
            value.append(asyncio.run(coro))
        except BaseException as exc:  # pragma: no cover
            error.append(exc)

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()
    if error:
        raise error[0]
    return value[0] if value else None


def _extract_uid(value: str) -> Optional[str]:
    value = value.strip()
    if UID_PATTERN.fullmatch(value):
        return value
    try:
        parsed = urlparse(value if "://" in value else f"https://{value}")
    except ValueError:
        return None
    if parsed.hostname not in ALLOWED_PROFILE_HOSTS:
        return None
    for segment in reversed(parsed.path.split("/")):
        if UID_PATTERN.fullmatch(segment):
            return segment
    return None


async def resolve_uid(user_input: str) -> Optional[str]:
    """Resolve a raw id or known profile URL; remote lookup is opt-in."""
    direct_uid = _extract_uid(user_input)
    if direct_uid or not REMOTE_STATUS_ENABLED:
        return direct_uid
    username = user_input.strip().strip("/")
    if not username or "/" in username or len(username) > 80:
        return None
    try:
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with session.get(f"https://locket.cam/{username}", headers={"User-Agent": "LocketGoldDemo/1.0"}) as response:
                if response.status != 200:
                    return None
                html = await response.text(errors="ignore")
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return None
    match = re.search(r"/invites/([A-Za-z0-9]{28})", html)
    return match.group(1) if match else None


async def check_status_gold(uid: str) -> Dict[str, Any]:
    """Read status from the explicitly configured test endpoint."""
    if not REMOTE_STATUS_ENABLED or not FAKE_RC_URL:
        return {"active": False, "expires": None, "source": "demo", "message": "Chế độ demo: chưa kết nối nguồn trạng thái."}
    try:
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with session.get(f"{FAKE_RC_URL}/v1/subscribers/{uid}") as response:
                if response.status != 200:
                    return {"active": False, "expires": None, "source": "remote", "message": f"Nguồn trả về HTTP {response.status}."}
                data = await response.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError):
        return {"active": False, "expires": None, "source": "remote", "message": "Không thể kết nối nguồn trạng thái."}
    entitlement = data.get("subscriber", {}).get("entitlements", {}).get("Gold", {})
    return {"active": bool(entitlement.get("is_active", entitlement.get("active", False))), "expires": entitlement.get("expires_date"), "source": "remote", "message": "Đã nhận trạng thái từ nguồn đã cấu hình."}


def write_guide(uid: str, status: Dict[str, Any]) -> str:
    state = "đang hoạt động" if status.get("active") else "chưa hoạt động"
    guide = f"""Locket Gold — báo cáo kiểm tra
{'=' * 32}

UID: {uid}
Trạng thái: {state}
Nguồn: {status.get('source', 'demo')}
Hết hạn: {status.get('expires') or 'Không có dữ liệu'}

{status.get('message', '')}

Nếu trạng thái "đang hoạt động", bạn có thể tiếp tục sử dụng Locket Gold bình thường mà không cần VPN.
"""
    (OUTPUT_DIR / "guide.txt").write_text(guide, encoding="utf-8")
    return "guide.txt"


@app.get("/")
def index() -> str:
    with _state_lock:
        result = dict(_last_result) if _last_result else None
    return render_template("index.html", result=result, remote_enabled=REMOTE_STATUS_ENABLED and bool(FAKE_RC_URL))


@app.post("/activate")
def activate():
    """Perform a status check for the supplied UID or profile URL."""
    raw_input = request.form.get("username", "")
    if not raw_input:
        raw_input = str((request.get_json(silent=True) or {}).get("username", ""))
    raw_input = raw_input.strip()
    if not raw_input:
        return jsonify(error="Vui lòng nhập UID hoặc link hồ sơ."), 400
    if len(raw_input) > 512:
        return jsonify(error="Giá trị nhập quá dài."), 400
    uid = _run_async(resolve_uid(raw_input))
    if not uid:
        return jsonify(error="Không tìm thấy UID hợp lệ. Vui lòng kiểm tra username hoặc link."), 422
    status = _run_async(check_status_gold(uid))
    guide_file = write_guide(uid, status)
    result = {"uid": uid, **status, "guide_file": guide_file}
    global _last_result
    with _state_lock:
        _last_result = result
    return jsonify(success=True, mode="status-check", **result)


@app.get("/download/<path:filename>")
def download_file(filename: str):
    if filename != "guide.txt":
        return jsonify(error="Tệp không tồn tại."), 404
    return send_from_directory(OUTPUT_DIR, filename, as_attachment=True, download_name=filename)


@app.get("/healthz")
def healthz():
    return jsonify(ok=True, mode="remote" if REMOTE_STATUS_ENABLED and FAKE_RC_URL else "demo")


@app.errorhandler(413)
def request_too_large(_error):
    return jsonify(error="Dữ liệu gửi lên quá lớn."), 413


if __name__ == "__main__":
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "5000")), debug=False)
