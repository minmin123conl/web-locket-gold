#!/usr/bin/env python3
"""Locket Gold — Kích hoạt Gold cho iOS.

Ứng dụng web chính thức, kiểm tra và kích hoạt Locket Gold
cho người dùng iPhone mà không cần VPN.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, unquote

import aiohttp
from flask import Flask, jsonify, render_template, request, send_from_directory

# ── Configuration ────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
IS_VERCEL = bool(os.getenv("VERCEL")) or os.getenv("AWS_EXECUTION_ENV") is not None

if IS_VERCEL:
    OUTPUT_DIR = Path("/tmp/output")
else:
    OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# Worker URL — luôn có giá trị
FAKE_RC_URL = (
    os.getenv("FAKE_RC_URL", "").strip().rstrip("/")
    or "https://locketgold.hoanganh1mw.workers.dev"
)

# Luôn bật remote status
REMOTE_STATUS_ENABLED = True

# Timeout: 15s cho locket.cam, 10s cho worker
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=float(os.getenv("REQUEST_TIMEOUT", "15")))
WORKER_TIMEOUT = aiohttp.ClientTimeout(total=float(os.getenv("WORKER_TIMEOUT", "10")))

# UID pattern: 28 ký tự alphanumeric
UID_PATTERN = re.compile(r"^[A-Za-z0-9]{28}$")

# Các domain profile được phép
ALLOWED_PROFILE_HOSTS = {
    "locket.cam", "www.locket.cam",
    "locketapp.com", "www.locketapp.com",
    "locket.app", "www.locket.app",
}

# Regex tìm UID trong HTML — linh hoạt hơn
UID_IN_HTML_PATTERNS = [
    re.compile(r"/invites/([A-Za-z0-9]{28})"),
    re.compile(r"invite[=:][\"']?([A-Za-z0-9]{28})"),
    re.compile(r"uid[=:][\"']?([A-Za-z0-9]{28})"),
    re.compile(r"user[_-]?id[=:][\"']?([A-Za-z0-9]{28})"),
    re.compile(r"[\"']([A-Za-z0-9]{28})[\"']"),
]

# User-Agent giả lập browser
UA_BROWSER = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)

# ── App setup ────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config.update(
    MAX_CONTENT_LENGTH=10 * 1024,  # 10KB
    JSON_SORT_KEYS=False,
)
_state_lock = threading.Lock()
_last_result: Optional[Dict[str, Any]] = None


# ── Async helper ─────────────────────────────────────────────────────────────
def _run_async(coro: Any) -> Any:
    """Run coroutine from sync Flask handler."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    value: List[Any] = []
    error: List[BaseException] = []

    def runner() -> None:
        try:
            value.append(asyncio.run(coro))
        except BaseException as exc:
            error.append(exc)

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()
    if error:
        raise error[0]
    return value[0] if value else None


# ── UID extraction ───────────────────────────────────────────────────────────
def _extract_uid(value: str) -> Optional[str]:
    """Trích xuất UID trực tiếp từ input nếu là 28 ký tự hoặc URL hợp lệ."""
    value = value.strip()
    if UID_PATTERN.fullmatch(value):
        return value

    try:
        parsed = urlparse(value if "://" in value else f"https://{value}")
    except ValueError:
        return None

    hostname = (parsed.hostname or "").lower()
    if hostname not in ALLOWED_PROFILE_HOSTS:
        return None

    # Tìm trong path segments
    for segment in reversed(parsed.path.split("/")):
        if UID_PATTERN.fullmatch(segment):
            return segment

    # Tìm trong query string
    from urllib.parse import parse_qs
    query = parse_qs(parsed.query)
    for values in query.values():
        for v in values:
            if UID_PATTERN.fullmatch(v):
                return v

    return None


async def resolve_uid(user_input: str) -> Optional[str]:
    """Resolve username hoặc URL thành UID 28 ký tự."""
    # 1. Thử extract trực tiếp
    direct_uid = _extract_uid(user_input)
    if direct_uid:
        return direct_uid

    if not REMOTE_STATUS_ENABLED:
        return None

    # 2. Validate input
    username = user_input.strip().strip("/")
    if not username or "/" in username or len(username) > 80:
        return None

    # Loại bỏ query string nếu có
    username = username.split("?")[0].split("#")[0].strip()

    if not username:
        return None

    # 3. Thử resolve qua locket.cam
    try:
        url = f"https://locket.cam/{username}"
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with session.get(url, headers={"User-Agent": UA_BROWSER}, allow_redirects=True) as response:
                if response.status != 200:
                    # Thử qua locketapp.com
                    url2 = f"https://locketapp.com/{username}"
                    async with session.get(url2, headers={"User-Agent": UA_BROWSER}, allow_redirects=True) as resp2:
                        if resp2.status != 200:
                            return None
                        html = await resp2.text(errors="ignore")
                else:
                    # Kiểm tra redirect URL
                    final_url = str(response.url)
                    uid_from_url = _extract_uid(final_url)
                    if uid_from_url:
                        return uid_from_url

                    html = await response.text(errors="ignore")
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        print(f"[resolve_uid] Lỗi kết nối: {e}")
        return None

    # 4. Tìm UID trong HTML bằng nhiều pattern
    for pattern in UID_IN_HTML_PATTERNS:
        match = pattern.search(html)
        if match:
            uid = match.group(1)
            if UID_PATTERN.fullmatch(uid):
                return uid

    return None


# ── Status check ─────────────────────────────────────────────────────────────
async def check_status_gold(uid: str) -> Dict[str, Any]:
    """Kiểm tra trạng thái Gold từ Worker API."""
    if not FAKE_RC_URL:
        return {
            "active": False,
            "expires": None,
            "source": "error",
            "message": "Chưa cấu hình Worker URL.",
        }

    try:
        async with aiohttp.ClientSession(timeout=WORKER_TIMEOUT) as session:
            async with session.get(f"{FAKE_RC_URL}/v1/subscribers/{uid}") as response:
                if response.status != 200:
                    return {
                        "active": False,
                        "expires": None,
                        "source": "remote",
                        "message": f"Worker trả về HTTP {response.status}. Vui lòng thử lại.",
                    }
                data = await response.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        print(f"[check_status] Lỗi kết nối Worker: {e}")
        return {
            "active": False,
            "expires": None,
            "source": "remote",
            "message": "Không thể kết nối Worker. Vui lòng thử lại sau.",
        }
    except json.JSONDecodeError:
        return {
            "active": False,
            "expires": None,
            "source": "remote",
            "message": "Worker trả về dữ liệu không hợp lệ.",
        }

    # Parse response — hỗ trợ nhiều format
    try:
        subscriber = data.get("subscriber", {})
        entitlements = subscriber.get("entitlements", {})

        # Thử tìm "Gold" trước
        entitlement = entitlements.get("Gold", {})

        # Nếu không có "Gold", thử tìm entitlement active đầu tiên
        if not entitlement:
            for key, val in entitlements.items():
                if isinstance(val, dict) and (val.get("is_active") or val.get("active")):
                    entitlement = val
                    break

        is_active = bool(entitlement.get("is_active", entitlement.get("active", False)))
        expires = entitlement.get("expires_date") or entitlement.get("expiresDate")

        if is_active:
            return {
                "active": True,
                "expires": expires or "2099-12-31T23:59:59Z",
                "source": "remote",
                "message": "Gold đang hoạt động trên tài khoản này.",
            }
        else:
            return {
                "active": False,
                "expires": expires,
                "source": "remote",
                "message": "Tài khoản chưa có gói Gold hoạt động.",
            }
    except Exception as e:
        print(f"[check_status] Lỗi parse: {e}")
        return {
            "active": False,
            "expires": None,
            "source": "remote",
            "message": "Lỗi xử lý dữ liệu từ Worker.",
        }


# ── Guide generation ─────────────────────────────────────────────────────────
def write_guide(uid: str, status: Dict[str, Any]) -> str:
    """Tạo file báo cáo kích hoạt."""
    state = "🟢 ĐANG HOẠT ĐỘNG" if status.get("active") else "🔴 CHƯA KÍCH HOẠT"
    guide = f"""╔══════════════════════════════════════════════════════════╗
║           LOCKET GOLD — BÁO CÁO KÍCH HOẠT               ║
╚══════════════════════════════════════════════════════════╝

📅 Thời gian: {__import__('datetime').datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
👤 UID: {uid}
📊 Trạng thái: {state}
📅 Hết hạn: {status.get('expires') or 'Vĩnh viễn'}
📝 Ghi chú: {status.get('message', '')}

{'─' * 56}

CÁCH SỬ DỤNG LOCKET GOLD:
1. Tắt hoàn toàn Shadowrocket/VPN trên iPhone
2. Cài profile DNS (locketgold_novpn.mobileconfig)
3. Mở Locket → Gold sẽ tự động kích hoạt
4. Hoạt động trên WiFi và 4G/5G

{'─' * 56}

📞 Hỗ trợ 24/7: Liên hệ nếu Gold bị mất
🔒 An toàn · Không ảnh hưởng tài khoản
"""
    (OUTPUT_DIR / "guide.txt").write_text(guide, encoding="utf-8")
    return "guide.txt"


# ── Routes ───────────────────────────────────────────────────────────────────
@app.get("/")
def index() -> str:
    with _state_lock:
        result = dict(_last_result) if _last_result else None
    return render_template(
        "index.html",
        result=result,
        remote_enabled=True,  # Luôn là True
    )


@app.post("/activate")
def activate():
    """Kích hoạt Gold cho UID hoặc link hồ sơ."""
    # Nhận input từ form hoặc JSON
    raw_input = request.form.get("username", "")
    if not raw_input:
        data = request.get_json(silent=True) or {}
        raw_input = str(data.get("username", ""))

    raw_input = raw_input.strip()

    if not raw_input:
        return jsonify(
            error="Vui lòng nhập UID hoặc link hồ sơ Locket.",
            success=False,
        ), 400

    if len(raw_input) > 512:
        return jsonify(
            error="Giá trị nhập quá dài.",
            success=False,
        ), 400

    # Resolve UID
    try:
        uid = _run_async(resolve_uid(raw_input))
    except Exception as e:
        print(f"[activate] Lỗi resolve_uid: {e}")
        return jsonify(
            error="Lỗi xử lý yêu cầu. Vui lòng thử lại.",
            success=False,
        ), 500

    if not uid:
        return jsonify(
            error=(
                "Không tìm thấy UID hợp lệ. "
                "Vui lòng nhập UID 28 ký tự hoặc link từ locket.cam/locketapp.com."
            ),
            success=False,
        ), 422

    # Check status
    try:
        status = _run_async(check_status_gold(uid))
    except Exception as e:
        print(f"[activate] Lỗi check_status: {e}")
        return jsonify(
            error="Lỗi kiểm tra trạng thái. Vui lòng thử lại.",
            success=False,
        ), 500

    # Generate guide
    try:
        guide_file = write_guide(uid, status)
    except Exception as e:
        print(f"[activate] Lỗi write_guide: {e}")
        guide_file = None

    # Build result
    result = {
        "uid": uid,
        **status,
        "guide_file": guide_file,
    }

    global _last_result
    with _state_lock:
        _last_result = result

    return jsonify(success=True, **result)


@app.get("/download/<path:filename>")
def download_file(filename: str):
    if filename != "guide.txt":
        return jsonify(error="Tệp không tồn tại."), 404
    return send_from_directory(
        OUTPUT_DIR, filename, as_attachment=True, download_name=filename
    )


@app.get("/healthz")
def healthz():
    return jsonify(
        ok=True,
        mode="remote",
        worker_url=FAKE_RC_URL,
    )


@app.errorhandler(413)
def request_too_large(_error):
    return jsonify(error="Dữ liệu gửi lên quá lớn."), 413


@app.errorhandler(404)
def not_found(_error):
    return jsonify(error="Không tìm thấy trang."), 404


@app.errorhandler(500)
def internal_error(_error):
    return jsonify(error="Lỗi máy chủ. Vui lòng thử lại."), 500


# ── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    print(f"""
╔══════════════════════════════════════════════════════════╗
║              LOCKET GOLD — PRODUCTION                    ║
╠══════════════════════════════════════════════════════════╣
║  🌐 Local:   http://127.0.0.1:{port}                      ║
║  🔗 Worker:  {FAKE_RC_URL:<42}║
║  📡 Mode:    REMOTE (production)                          ║
╚══════════════════════════════════════════════════════════╝
""")
    app.run(host=os.getenv("HOST", "0.0.0.0"), port=port, debug=False)