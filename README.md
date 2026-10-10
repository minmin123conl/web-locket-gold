# Locket Gold — Consolidated Project

## Mục lục
- `/web_app.py` — Flask web app (kích hoạt + hướng dẫn DNS)
- `/templates/index.html` — Giao diện người dùng
- `/static/` — Thư mục assets (CSS/JS)
- `/locketgold.py` — CLI tool gốc (Python)
- `/server.js` — Node.js HTTPS server (self-host option)
- `/rc_fake_worker.js` — Cloudflare Worker code
- `/SETUP.txt` — Hướng dẫn cài đặt (No-VPN)
- `/locketgold_novpn.mobileconfig` — File profile iOS
- `/locketgold.service` — Systemd service (VPS)
- `/setup_vps.sh` — Script cài VPS
- `/server.crt`, `/server.key` — TLS certificates
- `/requirements.txt` — Python dependencies
- `/output/` — Files tự động tạo sau khi kích hoạt

## Cách chạy

### 1. Web App (khuyên dùng)
```bash
cd locket-gold-web
python web_app.py
# Truy cập: http://127.0.0.1:5000
# - Nhập username/link Locket
# - Nhấn "Kích hoạt Gold"
# - Download guide.txt + mobileconfig.tmp
# - Cài profile iPhone theo hướng dẫn
# - Mở Locket → Gold hoạt động
```

### 2. Self-host VPS
```bash
cd locket-gold-web
bash setup_vps.sh   # Cài Node.js + server + systemd
# Sau đó cấu hình NextDNS rewrite: api.revenuecat.com → IP VPS
```

### 3. Cloudflare Worker (miễn phí)
```bash
# Deploy rc_fake_worker.js lên Cloudflare Workers
# Cấu hình NextDNS rewrite: api.revenuecat.com → IP Worker
# Sửa FAKE_RC_URL trong web_app.py thành URL worker của bạn
```

## Cấu trúc thư mục
```
locket-gold-web/
├── web_app.py          # Flask app (main entry)
├── requirements.txt    # pip install -r requirements.txt
├── locketgold.py       # CLI tool gốc
├── server.js           # Node.js HTTPS server
├── rc_fake_worker.js   # Cloudflare Worker
├── SETUP.txt           # Hướng dẫn chi tiết
├── locketgold.service # Systemd service
├── setup_vps.sh        # Script cài VPS
├── server.crt / server.key # TLS certs
├── locketgold_novpn.mobileconfig # iOS profile (chỉnh sửa ID/IP)
├── templates/
│   └── index.html      # Giao diện web
├── static/             # Thư mục assets (CSS/JS)
└── output/             # Files tự tạo (guide.txt, mobileconfig.tmp)
```

## Chỉnh sửa nhanh

### Sửa Cloudflare Worker URL
Mở `web_app.py`, tìm dòng:
```python
FAKE_RC_URL = "https://rc-fake-api.YOUR_SUBDOMAIN.workers.dev"
```
Thay bằng URL thực của bạn sau khi deploy.

### Sửa mobileconfig ID/IP
Mở `locketgold_novpn.mobileconfig` bằng TextEditor, thay:
- `<string>9ed13f.dns.nextdns.io</string>` → ID NextDNS của bạn
- `<string>45.90.28.58</string>` và `<string>45.90.30.58</string>` → IP NextDNS của bạn

### Đổi port/cổng
Thay cổng 5000 trong `web_app.py` nếu cần.

## Liên hệ
- Dự án kết hợp: CLI tool (`locketgold.py`) + DNS rewriting (`locket-gold`)
- Mục tiêu: Kích Gold Locket **không cần VPN/ScreenTime**