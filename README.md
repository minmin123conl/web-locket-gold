# Locket Gold · Status Lab

Ứng dụng Flask thử nghiệm để kiểm tra định dạng UID/link hồ sơ và tạo báo cáo trạng thái. Giao diện chạy local-first, không tự động thay đổi tài khoản, cài profile thiết bị hoặc can thiệp DNS.

## Chạy local

```bash
cd locket-gold-web
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python web_app.py
```

Mở `http://127.0.0.1:5000`. Endpoint `/healthz` trả về trạng thái hoạt động của app.

## Cấu hình nguồn kiểm thử (tuỳ chọn)

Mặc định app chạy `DEMO_MODE` và không gọi mạng. Chỉ bật khi bạn có endpoint kiểm thử do mình sở hữu:

```bash
ENABLE_REMOTE_STATUS=1 \
FAKE_RC_URL=https://example.test \
python web_app.py
```

Khi bật remote, app chỉ thực hiện GET tới `/v1/subscribers/<uid>` và hiển thị dữ liệu trả về; route `/activate` vẫn là route kiểm tra tương thích, không thực hiện thao tác ghi.

## Cấu trúc

- `web_app.py`: Flask app, xác thực input, status check và download report.
- `templates/index.html`: layout giao diện.
- `static/app.css`, `static/app.js`: style và tương tác phía trình duyệt.
- `output/guide.txt`: báo cáo được tạo sau mỗi lần kiểm tra.

## Kiểm tra nhanh

```bash
python -m py_compile web_app.py
node --check static/app.js
```
