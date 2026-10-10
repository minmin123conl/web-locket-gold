#!/usr/bin/env python3
"""Web app Locket Gold — tự động kích + hướng dẫn DNS setup"""
import asyncio
import json
import os
import re
import subprocess
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import aiohttp
from flask import Flask, render_template, request, send_file, jsonify

# ════════════════════════════════════════════════════════════════
# CẤU HÌNH
# ═════════════════════════════════════════════════════════════════

# Worker URL của bạn (deploy xong rồi điền vào đây)
FAKE_RC_URL = "https://rc-fake-api.YOUR_SUBDOMAIN.workers.dev"

# Hoặc chạy local: FAKE_RC_URL = "http://127.0.0.1:443"
# (chạy `node /path/locket-gold/server.js` trước)

# Cấu hình HEADERS (giữ nguyên từ locketgold.py)
HEADERS = {
    'Host': 'api.revenuecat.com',
    'Authorization': 'Bearer appl_JngFETzdodyLmCREOlwTUtXdQik',
    'Content-Type': 'application/json',
    'Accept': '*/*',
    'X-Platform': 'iOS',
    'X-Platform-Version': 'Version 26.2 (Build 23C55)',
    'X-Platform-Device': 'iPhone15,3',
    'X-Platform-Flavor': 'native',
    'X-Version': '5.41.0',
    'X-Client-Version': '3',
    'X-Client-Bundle-ID': 'com.locket.Locket',
    'X-Client-Build-Version': '3',
    'X-StoreKit2-Enabled': 'true',
    'X-StoreKit-Version': '2',
    'X-Observer-Mode-Enabled': 'false',
    'X-Is-Sandbox': 'false',
    'X-Storefront': 'VNM',
    'X-Apple-Device-Identifier': '39A73C25-1E05-4350-ADA7-5CD3FE1079E8',
    'X-Preferred-Locales': 'vi_KR,ko_KR,en_KR',
    'X-Nonce': 'w0Mlb6+AmV4WYuVv',
    'X-Is-Backgrounded': 'false',
    'X-Retry-Count': '0',
    'X-Is-Debug-Build': 'false',
    'User-Agent': 'Locket/3 CFNetwork/3860.300.31 Darwin/25.2.0',
    'Accept-Language': 'vi-VN,vi;q=0.9',
    'Connection': 'keep-alive',
    'Pragma': 'no-cache',
    'Cache-Control': 'no-cache',
    'X-RevenueCat-ETag': ''
}

# ═════════════════════════════════════════════════════════════════
# FLASK APP
# ═════════════════════════════════════════════════════════════════

app = Flask(__name__)

results = {}  # Lưu kết quả recent (để hiển thị trên web)


# ═════════════════════════════════════════════════════════════════
# HỨNG DẪN TẠO MOBILECONFIG
# ═════════════════════════════════════════════════════════════════

def generate_mobileconfig_guide(worker_ip, nextdns_id):
    """
    Tạo nội dung hướng dẫn DNS setup kèm file mobileconfig mẫu.
    User sẽ replace ID/IP rồi cài trên iPhone.
    """
    guide = f"""
# 📱 HƯỚNG DẪN CÀI DNS - Giữ Locket Gold (không VPN)

## 1. Deploy Cloudflare Worker (đã làm)
Worker URL của bạn: {FAKE_RC_URL}
IP Worker: {worker_ip}

## 2. Cấu hình NextDNS Rewrite
1. Đăng nhập nextdns.io → Profile của bạn
2. Tab **Rewrites** → Add rewrite:
   - Name: `api.revenuecat.com`
   - Answer: `{worker_ip}`
3. Save

## 3. Cài đặt profile iOS
1. Tải file mobileconfig dưới đây
2. **QUAN TRỌNG**: Mở file bằng TextEditor, sửa:
   - Thay `<string>9ed13f.dns.nextdns.io</string>` bằng ID NextDNS của bạn
     (tại nextdns.io → profile → ID trong URL, ví dụ: `ab12cd`)
   - Thay hai IP `<string>45.90.28.58</string>` và `<string>45.90.30.58</string>`
     bằng IP NextDNS profile của bạn (tại nextdns.io/profile → Setup → IPs)
3. Host file lên đâu đó (GitHub Raw, gửi email, v.v.)
4. Mở link trên iPhone → Settings → Profile Downloaded → Install
5. Settings → General → VPN & Device Management → trust "LocketGold-CA cert"
6. Settings → General → About → Certificate Trust Settings → enable LocketGold-CA

## 4. Test
1. Tắt hoàn toàn Shadowrocket/VPN khác
2. Mở ứng dụng Locket
3. Gold status nên hiện ra → {results.get('status', 'Chờ kiểm tra')}

---
⚠️ Lưu ý: Cài 1 lần là mãi mãi dùng. Nếu IP Worker thay đổi → cập nhật lại rule NextDNS.
"""
    
    # Tạo file mobileconfig mẫu (chỉ có cấu trúc cơ bản, user cần edit)
    mobileconfig = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>PayloadContent</key>
    <array>
        <!-- CA Cert -->
        <dict>
            <key>PayloadCertificateFileName</key>
            <string>LocketGold-CA.crt</string>
            <key>PayloadContent>
            <data>LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSURWekNDQWorZ0F3SUJBZ0lVV1RubXlKYk52YkJYdFQ0cHp6Ym5KVmpmbjdrd0RRWUpLb1pJaHZjTkFRRUwKQlFBd09qRVdNQlFHQTFVRUF3d05URzlqYTJWMFIyOXNaQzFEUVRFVE1CRUdBMVVFQ2d3S1RHOWphMlYwUjI5cwpaREVMTUFrR0ExVUVCaE1DVlZNd0lCY05Nall3TnpBeU1EYzBOalExV2hnUE1qRXlOakEyTURnd056UTJORFZhCk1Eb3hGakFVQmdOVkJBTU1EVXh2WTJ0bGRFZHZiR1F0UTBFeEV6QVJCZ05WQkFvTUNreHZZMnRsZEVkdmJHUXgKQ3pBSkJnTlZCQVlUQWxWVE1JSUJJakFOQmdrcWhraUc5dzBCQVFFRkFBT0NBUThBTUlJQkNnS0NBUUVBMGwrSAp0OWxRR25LTEF2b2cybE5nRTBUdStNVHFDOUlKMnhIcjdZZ2Z5MWtjTUx1Y05ndjJUN2JkazVHWlRGQXNmQkc1CkNXSDhDT2VUZ0hNOHJBZ2x4RzJlK0pXTXdEMnVGSFRzaktFSUtkSmsyS2Y1cExBY1AvT1ZSMWtpdUZrVnUrZGIKc0pLaWlIUFlES3hsYkRxVEROaDFEdEpmMzVHVHp3Qi90bWE5eGxrMVMwanlpWVgzcDcvbk53VzhYN1dpOWJ5RAoyZnd4aWxuWGJmUFdQdDY1S2JtVURITG5jWjg5WE9MdlFOUERRR2pkQWsvZDVXcG5jaTJLWmJUMGFkSFg1emdsCmRYd3ZiSG4ydkR6ZVI4K3NUaURHR2xrbG9rZGZIVDh4VCs2b0hIMGVFQlZWL01XK3lKNUU0c25vTHNRV1lsQ3oKS3dUdC9YMkkxMXY5QWtUUUZRSURBUUFCbzFNd1VUQWRCZ05WSFE0RUZnUVUzb2NnNU5ycStTUDVUYWRRbGoxMQpQNGZxTG1Vd0h3WURWUjBqQkJnd0ZvQVUzb2NnNU5ycStTUDVUYWRRbGoxMVA0ZnFMbVV3RHdZRFZSMFRBUUgvCkJBVXdBd0VCL3pBTkJna3Foa2lHOXcwQkFRc0ZBQU9DQVFFQVFDczdJRW9UYU04c05GeTN1YkZjUzg5T2dxNkMKbEYrM1YxU1B3b2t2STM0ZzBzQnRmUGZDSVZHb2JyWitSVG0rcGx2QTh1eXZLQ3VRWUw5cUQ1eHNkSmkrSnhXUAo1RmFycjAzdWtURkN6UUFTUGZzSGlMNTlWbk90V3B2MU8zN2drM3lOUFB0N0lkWkRvWUQzVGwyU0JtL1lMM2tkCmVBTFlQM1dQeFhjVGVNQnYwSTdja2FXOXZtbWtmenlScWRyNmFQcUlJbHIySEEvb05RSzJVUDlVQWZyNXlBMVcKb0s4M0h3eW0zUVFiWW5abTJWcEdpTzdIbnJjcS9zb3dTYTNHM1BYV0VpVXNsMkpzM3RyeERIVDFYckRueUgxNQowRDg4c1FNczJUK3Fjd2dNMkVFOXUxcGpSTmxUS0dwT3Rad3dqYTFROWErdU5sV1VhSU4zT0pXeVJ3PT0KLS0tLS1FTkQgQ0VSVElGSUNBVEUtLS0tLQo=</data>
            </key>

        <!-- DNS Settings -->
        <dict>
            <key>DNSSettings</key>
            <dict>
                <key>DNSProtocol</key>
                <string>TLS</string>
                <key>ServerAddresses>
                <array>
                    <string>45.90.28.58</string>
                    <string>45.90.30.58</string>
                </array>
                <key>ServerName>
                <string>9ed13f.dns.nextdns.io</string>
            </dict>
            <key>PayloadDescription>
            <string>DNS rewrite for api.revenuecat.com</string>
            <key>PayloadDisplayName>
            <string>LocketGold DNS</string>
            <key>PayloadIdentifier>
            <string>com.locketgold.dns</string>
            <key>PayloadType>
            <string>com.apple.dnsSettings.managed</string>
            <key>PayloadUUID>
            <string>EF397645-A665-4DC1-A426-C805CD4FC19E</string>
            <key>PayloadVersion>
            <integer>1</integer>
        </dict>
    </key>
    <key>PayloadDescription>
    <string>LocketGold — No VPN required.</string>
    <key>PayloadDisplayName>
    <string>LocketGold No-VPN</string>
    <key>PayloadIdentifier>
    <string>com.locketgold.novpn</string>
    <key>PayloadRemovalDisallowed>
    <false/>
    <key>PayloadType>
    <string>Configuration</string>
    <key>PayloadUUID>
    <string>67BB6BED-D367-4B51-8BB9-050A3A08326C</string>
    <key>PayloadVersion>
    <integer>1</integer>
</dict>
</plist>
"""
    
    # Ghi file hướng dẫn và mobileconfig
    os.makedirs("output", exist_ok=True)
    
    with open("output/guide.txt", "w", encoding="utf-8") as f:
        f.write(guide)
    
    with open("output/mobileconfig.tmp", "w", encoding="utf-8") as f:
        f.write(mobileconfig)
    
    # Tên file không có extension để match route @download/
    guide_filename = "guide"
    mobileconfig_filename = "mobileconfig"
    
    return guide_filename, mobileconfig_filename


# ═════════════════════════════════════════════════════════════════
# XỬ LÝ KÍCH HOẠT GOLD
# ═════════════════════════════════════════════════════════════════

async def resolve_uid(user_input):
    """Phân giải username/link thành UID 28 ký tự"""
    # Nếu là link locket.cam
    if "locket.cam" in user_input or "locketapp.com" in user_input:
        # Trích xuất username từ link
        m = re.search(r'(?:locket\.cam|locketapp\.com)/(?:[^/]+/)?([A-Za-z0-9]{28})', user_input)
        if m:
            return m.group(1)
    
    # Nếu đã là UID 28 ký tự
    if re.match(r'^[A-Za-z0-9]{28}$', user_input.strip()):
        return user_input.strip()
    
    # Try resolve qua locket.cam
    try:
        url = f"https://locket.cam/{user_input.strip()}"
        headers = {"User-Agent": "Mozilla/5.0"}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=10) as res:
                html = await res.text()
                m = re.search(r'/invites/([A-Za-z0-9]{28})', html)
                if m:
                    return m.group(1)
    except:
        pass
    
    return None


async def check_status_gold(uid):
    """Kiểm tra trạng thái Gold qua Fake RC API"""
    url = f"{FAKE_RC_URL}/v1/subscribers/{uid}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as res:
                if res.status == 200:
                    data = await res.json()
                    subs = data.get('subscriber', {})
                    gold_ent = subs.get('entitlements', {}).get('Gold', {})
                    if gold_ent:
                        return {
                            "active": gold_ent.get('is_active', False),
                            "expires": gold_ent.get('expires_date', 'Forever (2099)')
                        }
    except Exception as e:
        print(f"Error check status: {e}")
    return {"active": False, "expires": "N/A"}


async def inject_gold(uid):
    """Tiêm Gold qua fake API (không cần token phức tạp vì worker trả về luôn)"""
    # Với fake API, chúng ta chỉ cần gọi endpoint subscribers để tạo entitlement
    # Thực tế thì do Worker trả về đã có subscription sẵn sàng
    # Chỉ cần verify thôi
    status = await check_status_gold(uid)
    return status


# ═════════════════════════════════════════════════════════════════
# ROUTES FLASK
# ═════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    """Trang chính - nhập username"""
    return render_template("index.html", result=results.get("last_result", None))


@app.route("/activate", methods=["POST"])
def activate():
    """Xử lý kích hoạt Gold"""
    global results
    
    user_input = request.form.get("username", "").strip()
    if not user_input:
        return jsonify({"error": "Vui lòng nhập username hoặc link"}), 400
    
    # Bước 1: Resolve UID
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    uid = loop.run_until_complete(resolve_uid(user_input))
    if not uid:
        return jsonify({"error": "Không tìm thấy UID. Kiểm tra username/link có đúng không?"}), 404
    
    # Bước 2: Kiểm tra/status
    result = loop.run_until_complete(inject_gold(uid))
    
    # Bước 3: Lấy IP worker (cần nslookup)
    try:
        import subprocess
        ns_result = subprocess.run(
            ["nslookup", f"rc-fake-api.YOUR_SUBDOMAIN.workers.dev"],
            capture_output=True, text=True
        )
        # Lấy IP từ output (dòng có Address)
        lines = ns_result.stdout.split("\n")
        worker_ip = ""
        for line in lines:
            if "Address:" in line and not line.startswith("Server:"):
                worker_ip = line.split("Address:")[1].strip()
                break
        if not worker_ip:
            worker_ip = "104.16.110.240"  # IP mặc định
    except:
        worker_ip = "104.16.110.240"
    
    # Bước 4: Generate hướng dẫn DNS
    # Cần NextDNS ID - lấy từ URL profile
    nextdns_id = "ab12cd"  # User cần replace
    
    guide_path, mc_path = generate_mobileconfig_guide(worker_ip, nextdns_id)
    
    # Lưu kết quả
    results = {
        "last_result": result,
        "uid": uid,
        "guide_path": guide_path,
        "mc_path": mc_path,
        "worker_ip": worker_ip,
        "status": "completed"
    }
    
    # Trả về kết quả
    return jsonify({
        "success": True,
        "uid": uid,
        "gold_active": result["active"],
        "expires": result["expires"],
        "guide_file": "guide.txt",
        "mobileconfig_file": "mobileconfig.tmp",
        "worker_ip": worker_ip
    })


# ═════════════════════════════════════════════════════════════════
# CHẠY SERVER
# ═════════════════════════════════════════════════════════════════

@app.route("/download/<filename>")
def download_file(filename):
    """Cung cấp file hướng dẫn/mobileconfig cho download"""
    return send_file(f"output/{filename}", as_attachment=True)


if __name__ == "__main__":
    print("""
 ═══════════════════════════════════════════════════════════
 🌐 LOCKET GOLD WEB APP - Chạy kèm DNS setup
 ═══════════════════════════════════════════════════════════
 ✅ Web: http://127.0.0.1:5000
 ✅ Cắm kết nối: Username → Kích Gold → Lấy guide DNS
 ═══════════════════════════════════════════════════════════
""")
    
    # Cập nhật FAKE_RC_URL với domain thực
    print("⚠️  NHỚ: Điền FAKE_RC_URL đúng worker của bạn trước khi chạy!")
    
    app.run(host="0.0.0.0", port=5000, debug=False)