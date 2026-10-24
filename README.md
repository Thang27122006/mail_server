# HỆ THỐNG MAIL SERVER & MAIL CLIENT (UDP SOCKET - PYTHON)

Dự án mô phỏng **Mail Server** và **Mail Client** sử dụng giao thức mạng **UDP Socket** trong Python, đáp ứng đầy đủ và chính xác tất cả các yêu cầu kỹ thuật của bài toán:

---

## 📌 Các Tính Năng Đáp Ứng Đúng Yêu Cầu Đề Bài

1. **Tạo tài khoản mới (Register):**
   - Khi client gửi yêu cầu tạo tài khoản mới lên server qua UDP:
   - Server tự động tạo thư mục mang tên tài khoản đó trong thư mục lưu trữ (`server_storage/<username>/`).
   - Server tự động tạo file `new_email.txt` trong thư mục đó với nội dung chính xác:
     ```
     Thank you for using this service. we hope that you will feel comfortabl........
     ```

2. **Gửi email (Send Email):**
   - Người dùng tại client gửi email tới một tài khoản chỉ định (`to_account`).
   - Server nhận email qua UDP, xác định tài khoản người nhận.
   - Server kiểm tra sự tồn tại của thư mục người nhận.
   - Tại thư mục của người nhận trên server, tạo một file văn bản (`email_<sender>_<timestamp>.txt`) chứa đầy đủ nội dung email.

3. **Đăng nhập vào account (Login):**
   - Client đăng nhập vào một tài khoản.
   - Server xác thực, mở thư mục tương ứng với account đó trên server.
   - Server quét toàn bộ thư mục và **gửi tất cả các tên file trong thư mục đó về máy client**.
   - Client hiển thị danh sách các file email đã nhận từ server.

4. **Tự động văng ra giao diện đăng nhập khi Server Dừng (Auto-Kickback to Login):**
   - Khi Server GUI bấm nút **⏹ Dừng Server**, Server sẽ phát thông báo `SERVER_STOPPED` tới tất cả các Client đang kết nối.
   - Toàn bộ Client GUI đang mở (kể cả đang ở màn hình Hộp thư, xem email hay soạn thư) sẽ ngay lập tức bị đóng phiên làm việc và **văng trở lại giao diện Đăng nhập** kèm hộp thoại thông báo.

5. **Gửi thư thực tế vào Gmail (Gmail SMTP Relay) & Lưu trữ Database:**
   - **Gửi thư thực tế qua Gmail SMTP:** Khi người dùng gửi thư tới một địa chỉ email (ví dụ: `nguoinhan@gmail.com`), Server tự động chuyển tiếp và gửi thư thực tế qua giao thức Gmail SMTP (`smtp.gmail.com:587` mã hóa STARTTLS).
   - **Lưu trữ toàn diện trong Cơ sở dữ liệu (SQLite):** Mọi email (cả thư gửi nội bộ và thư gửi ra Gmail) đều được lưu trữ đầy đủ trong CSDL SQLite (`server_storage/mail_server.db`) gồm: người gửi, người nhận, tiêu đề, nội dung, ngày giờ, hình thức gửi, trạng thái và phản hồi chi tiết.
   - **Giao diện Quản trị CSDL (Database Dashboard):** Server GUI tích hợp tab riêng biệt cho phép tìm kiếm, lọc theo hình thức (LOCAL / GMAIL), xem chi tiết nội dung từng thư và xóa bản ghi.
   - **Tab Cấu hình Gmail SMTP:** Hỗ trợ nhập Email, Mật khẩu ứng dụng Google (App Password) và nút "Kiểm Tra Kết Nối Gmail" tức thì.

6. **Tính năng bổ trợ tiện ích:**
   - **Đọc email (Read Email):** Client có thể chọn xem nội dung bất kỳ file nào từ danh sách file được server gửi về.
   - **Làm mới hộp thư (Refresh):** Lấy danh sách file mới nhất từ server.
   - **Hỗ trợ 2 giao diện Client:**
     - `client.py`: Giao diện dòng lệnh (CLI) trực quan.
     - `client_gui.py`: Giao diện đồ họa (GUI bằng Tkinter) hiện đại, hỗ trợ mở nhiều cửa sổ cùng lúc.
   - **Đa luồng (Multi-threading):** Server lắng nghe và dispatch gói tin UDP trên các luồng nền độc lập, phục vụ nhiều client đồng thời mà không nghẽn mạng.

---

## 📂 Cấu Trúc Dự Án

```
mail_server/
│
├── common.py           # Cấu hình cổng/host, hàm gửi/nhận JSON qua UDP socket
├── db_manager.py       # Quản lý Cơ sở dữ liệu SQLite (Lưu email, tài khoản)
├── smtp_service.py     # Dịch vụ gửi thư thực tế qua Gmail SMTP (TLS 587)
├── server.py           # Mail Server xử lý đa luồng UDP (Giao diện Console)
├── server_gui.py       # Mail Server Dashboard quản trị trực quan (Giao diện Tkinter GUI)
├── client.py           # Mail Client giao diện dòng lệnh UDP (CLI)
├── client_gui.py       # Mail Client giao diện đồ họa UDP (Tkinter GUI)
├── demo_test.py        # Kịch bản kiểm thử tự động toàn bộ 6 bước yêu cầu
└── server_storage/     # Thư mục lưu trữ trên máy chủ (Server Data Storage)
    ├── mail_server.db  # CSDL SQLite lưu trữ toàn bộ email và tài khoản
    ├── smtp_config.json# Cấu hình tài khoản và máy chủ Gmail SMTP
    ├── accounts.json   # Lưu thông tin tài khoản và mật khẩu
    ├── <username1>/    # Thư mục riêng của tài khoản 1 (chứa new_email.txt, email_*.txt)
    └── <username2>/    # Thư mục riêng của tài khoản 2
```

---

## 🚀 Hướng Dẫn Chạy Chương Trình

Mở Terminal / PowerShell và chuyển đến thư mục dự án:

```powershell
cd "d:\2026-2027\Kì 1\Lập trình mạng\mail_server"
```

---

### 1. Khởi động Mail Server (Chọn 1 trong 2 cách)

#### 🔹 Cách A: Dùng Giao diện đồ họa Quản trị Server GUI (Khuyên dùng)
```powershell
python server_gui.py
```
- Bấm nút **▶ Khởi Động Server** (mặc định tại `0.0.0.0:2345`).
- Bấm nút **⏹ Dừng Server** bất kỳ lúc nào để ngắt hoạt động và đẩy tất cả client về màn hình đăng nhập.
- Theo dõi thẻ thống kê thời gian thực: số lượng tài khoản, tổng số email, số client đang kết nối.
- Tab **Nhật ký hoạt động (Live Logs)**: Hiển thị chi tiết từng gói tin UDP, đăng nhập, gửi email có màu sắc trực quan.
- Tab **Quản lý Tài khoản & Hộp thư**: Duyệt danh sách tài khoản, các file email trong thư mục, xem trước nội dung email và tạo/xóa tài khoản.
- Tab **Kết nối Trực tuyến**: Danh sách chi tiết các IP:Port client đang kết nối qua UDP.

#### 🔹 Cách B: Dùng Console Terminal
```powershell
python server.py
```

---

### 2. Chạy Mail Client

#### 🔹 Cách A: Client Giao diện đồ họa (GUI)
```powershell
python client_gui.py
```
- Nhấn **Kết nối Server (UDP)** (mặc định `127.0.0.1:2345`).
- **Mở nhiều cửa sổ Client cùng lúc:**
  - Nhấn nút **➕ Mở Cửa Sổ Mới** trên Client GUI để mở thêm bao nhiêu cửa sổ tùy thích.
  - Hoặc trên `server_gui.py`, bấm nút **👤 Mở Client GUI** để mở nhanh.
- Điền tên tài khoản, mật khẩu rồi nhấn **Đăng Ký Tài Khoản Mới** hoặc **Đăng Nhập Hộp Thư**.
- Sau khi đăng nhập, danh sách file email hiển thị ở cột bên trái. Bấm chọn file để xem nội dung bên phải.
- Nhấn **+ Soạn Email Mới** để gửi thư.
- **Thử nghiệm Dừng Server:** Khi đang mở hộp thư, quay sang `server_gui.py` bấm **⏹ Dừng Server**, Client sẽ lập tức nhận thông báo và văng về giao diện đăng nhập!

#### 🔹 Cách B: Client Dòng lệnh (CLI)
```powershell
python client.py
```

---

### 3. Chạy kiểm thử tự động (Automated Test)
Chạy kịch bản kiểm thử tự động xác minh toàn bộ các yêu cầu qua giao thức UDP:
```powershell
python demo_test.py
```
Kết quả kiểm thử xác nhận thành công 100%:
- Tạo tài khoản `alice_udp` và tự động sinh `new_email.txt`.
- `alice_udp` đăng nhập và nhận về danh sách file.
- Tạo tài khoản `bob_udp`.
- `bob_udp` gửi email tới `alice_udp` -> Server tạo file email trong thư mục `alice_udp`.
- `alice_udp` nhận danh sách file mới và đọc nội dung thư thành công.
- Server bấm dừng -> Client nhận gói tin `SERVER_STOPPED` và văng ra màn hình đăng nhập.
