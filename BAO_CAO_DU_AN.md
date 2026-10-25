# BÁO CÁO BÀI TẬP LỚN MÔN HỌC: LẬP TRÌNH MẠNG
## ĐỀ TÀI: XÂY DỰNG HỆ THỐNG MAIL SERVER & MAIL CLIENT ĐA GIAO THỨC (UDP SOCKET, CƠ SỞ DỮ LIỆU POSTGRESQL / PGADMIN 4, SQLITE & GMAIL SMTP RELAY)

---

- **Học kỳ:** Kỳ 1 - Năm học 2026 - 2027
- **Học phần:** Lập trình mạng (Network Programming)
- **Nền tảng phát triển:** Python 3, UDP Socket, Tkinter GUI, PostgreSQL, pgAdmin 4, SQLite3, SMTPLib (STARTTLS)
- **Hệ điều hành thử nghiệm:** Linux (Ubuntu) / Windows
- **Cơ sở dữ liệu quản trị:** PostgreSQL (Quản trị trực quan qua **pgAdmin 4**) & SQLite fallback

---

## MỤC LỤC
1. [GIỚI THIỆU & MỤC TIÊU ĐỀ TÀI](#1-giới-thiệu--mục-tiêu-đề-tài)
2. [KIẾN TRÚC TỔNG THỂ HỆ THỐNG](#2-kiến-trúc-tổng-thể-hệ-thống)
3. [THIẾT KẾ GIAO THỨC TRUYỀN THÔNG TẦNG ỨNG DỤNG (UDP)](#3-thiết-kế-giao-thức-truyền-thông-tầng-ứng-dụng-udp)
4. [THIẾT KẾ CƠ SỞ DỮ LIỆU POSTGRESQL (PGADMIN 4) & SQLITE](#4-thiết-kế-cơ-sở-dữ-liệu-postgresql-pgadmin-4--sqlite)
5. [CƠ CHẾ GỬI EMAIL THỰC TẾ RA GMAIL (GMAIL SMTP RELAY)](#5-cơ-chế-gửi-email-thực-tế-ra-gmail-gmail-smtp-relay)
6. [CÁC TÍNH NĂNG NỔI BẬT & CHI TIẾT CÀI ĐẶT](#6-các-tính-năng-nổi-bật--chi-tiết-cài-đặt)
7. [GIAO DIỆN NGƯỜI DÙNG & HỆ THỐNG QUẢN TRỊ (GUI & CLI)](#7-giao-diện-người-dùng--hệ-thống-quản-trị-gui--cli)
8. [KỊCH BẢN KIỂM THỬ & KẾT QUẢ THỰC NGHIỆM](#8-kịch-bản-kiểm-thử--kết-quả-thực-nghiệm)
9. [HƯỚNG DẪN CÀI ĐẶT, VẬN HÀNH & KẾT NỐI PGADMIN 4](#9-hướng-dẫn-cài-đặt-vận-hành--kết-nối-pgadmin-4)
10. [KẾT LUẬN & HƯỚNG PHÁT TRIỂN](#10-kết-luận--hướng-phát-triển)

---

## 1. GIỚI THIỆU & MỤC TIÊU ĐỀ TÀI

### 1.1. Đặt vấn đề
Dịch vụ thư điện tử (Email) là thành phần then chốt trong hạ tầng mạng máy tính toàn cầu. Đề tài hướng tới việc nghiên cứu, lập trình mô phỏng một hệ thống máy chủ thư điện tử (Mail Server) và ứng dụng máy khách (Mail Client) hoàn chỉnh dựa trên giao thức truyền vận **UDP Socket**. Đồng thời, dự án tích hợp hệ quản trị cơ sở dữ liệu mạnh mẽ **PostgreSQL** (quản lý trực quan trên **pgAdmin 4**) và giao thức gửi thư Internet **Gmail SMTP** để đem lại trải nghiệm ứng dụng thực tế cao cấp.

### 1.2. Mục tiêu đề tài
- **Đáp ứng chuẩn xác 100% tất cả các yêu cầu bài toán Lập trình mạng:**
  1. **Đăng ký tài khoản (Register):** Tự động sinh thư mục cá nhân `server_storage/<username>/` tại Server và khởi tạo file thư chào mừng `new_email.txt` với nội dung chuẩn xác theo yêu cầu đề bài.
  2. **Gửi email (Send Email):** Nhận email từ Client qua gói tin UDP, xác định người nhận và tạo file văn bản (`email_<sender>_<timestamp>.txt`) lưu tại thư mục của người nhận.
  3. **Đăng nhập (Login):** Xác thực tài khoản, mở thư mục trên Server, quét và gửi danh sách toàn bộ các tên file về cho Client hiển thị.
  4. **Tự động ngắt phiên khi Server dừng (Auto Kickback):** Khi Server bấm dừng, máy chủ phát tín hiệu `SERVER_STOPPED` để mọi Client đang mở lập tức bị đóng phiên và văng về giao diện đăng nhập.
  5. **Đọc email (Read Email):** Cho phép Client xem nội dung chi tiết bất kỳ bức thư nào.
- **Mở rộng nâng cao (Điểm sáng nổi bật của dự án):**
  - **Tích hợp PostgreSQL & pgAdmin 4:** Tự động tạo database `mail_server` và các bảng `accounts`, `emails` trên PostgreSQL. Dữ liệu lưu trữ dạng quan hệ có chỉ mục (Index) và người dùng có thể mở **pgAdmin 4** để duyệt dữ liệu trực quan thời gian thực.
  - **Cơ chế Dual-Database:** Tự động đồng bộ song song với SQLite (`mail_server.db`) để đảm bảo hệ thống có độ sẵn sàng cao (High Availability), không bao giờ bị dừng hoạt động dù cơ sở dữ liệu chính bị gián đoạn.
  - **Gửi thư thực tế vào Gmail:** Tích hợp giao thức Gmail SMTP (`smtp.gmail.com:587`, STARTTLS), cho phép gửi thư đến hòm thư thực tế của người nhận trên `mail.google.com`.
  - **Giao diện đa dạng:** Cung cấp cả giao diện đồ họa **Tkinter GUI** (Dashboard, KPI, Live Logs, cấu hình SMTP, trình duyệt CSDL) và giao diện dòng lệnh **CLI**.

---

## 2. KIẾN TRÚC TỔNG THỂ HỆ THỐNG

### 2.1. Sơ đồ kiến trúc toàn diện

```mermaid
graph TD
    subgraph "MÁY KHÁCH (CLIENT)"
        CGUI["Client GUI (client_gui.py)<br/>Tkinter - Đa cửa sổ"]
        CCLI["Client CLI (client.py)<br/>Console Terminal"]
    end

    subgraph "GIAO THỨC TRUYỀN VẬN (TRANSPORT LAYER)"
        UDP["Giao thức UDP Socket (Datagram)<br/>Đóng gói JSON - Port: 2345<br/>Định danh phiên bằng req_id"]
    end

    subgraph "MÁY CHỦ MAIL (SERVER CORE & MANAGEMENT)"
        CORE["Server Core Controller (server.py)<br/>Xử lý đa luồng Worker Threads"]
        SGUI["Server GUI Dashboard (server_gui.py)<br/>KPI Cards, Live Logs, Quản trị CSDL"]
        DBM["Database Manager (db_manager.py)<br/>Quản trị CSDL Kép PostgreSQL & SQLite"]
        SMTPM["SMTP Relay Service (smtp_service.py)<br/>MIME UTF-8, STARTTLS Port 587"]
    end

    subgraph "CƠ SỞ DỮ LIỆU & LƯU TRỮ (PERSISTENCE LAYER)"
        PG["Hệ quản trị PostgreSQL<br/>Database: mail_server (Port 5432)"]
        PGADMIN["pgAdmin 4 Dashboard<br/>Xem & quản trị trực quan Database"]
        SQLITE["Cơ sở dữ liệu SQLite<br/>server_storage/mail_server.db"]
        FS["Hệ thống File Storage (server_storage/)<br/>- accounts.json<br/>- &lt;user&gt;/new_email.txt<br/>- &lt;user&gt;/email_*.txt"]
    end

    subgraph "MẠNG INTERNET (GLOBAL EMAIL SERVICES)"
        GMAIL["Máy chủ Google Gmail<br/>smtp.gmail.com:587"]
        USERGMAIL["Hộp thư Gmail người nhận<br/>mail.google.com (Inbox thực tế)"]
    end

    CGUI <-->|Datagram UDP JSON| UDP
    CCLI <-->|Datagram UDP JSON| UDP
    UDP <--> CORE
    CORE <--> SGUI
    CORE --> DBM
    CORE --> SMTPM
    DBM -->|psycopg2| PG
    PG <--> PGADMIN
    DBM -->|sqlite3 (Sync/Fallback)| SQLITE
    CORE <--> FS
    SMTPM -->|STARTTLS + App Password| GMAIL
    GMAIL -->|Chuyển phát thư| USERGMAIL
```

### 2.2. Các module thành phần chính trong mã nguồn

| File | Module | Vai trò chức năng |
| :--- | :--- | :--- |
| `common.py` | Cấu hình & Hàm tiện ích | Thiết lập socket UDP, mã hóa/giải mã JSON UTF-8, lấy địa chỉ IP LAN tự động. |
| `server.py` | Mail Server Core | Tiếp nhận datagram UDP, điều phối đa luồng (Worker Threads), xử lý đăng ký, đăng nhập, gửi thư và ngắt kết nối. |
| `server_gui.py` | Server Dashboard GUI | Giao diện quản trị Tkinter: Thẻ KPI thống kê, Live Logs phân loại màu, quản lý file tài khoản, duyệt CSDL, cấu hình Gmail SMTP. |
| `db_manager.py` | Quản trị CSDL (Dual DB) | Kết nối PostgreSQL (cho pgAdmin 4) và SQLite. Tự động khởi tạo database `mail_server` và các bảng `accounts`, `emails`. |
| `smtp_service.py` | Dịch vụ gửi Gmail | Kết nối `smtp.gmail.com:587` qua STARTTLS, mã hóa tiêu đề MIME tiếng Việt, gửi thư thực tế vào hòm thư Gmail người nhận. |
| `client.py` | Mail Client CLI | Ứng dụng dòng lệnh cho người dùng đăng ký, đăng nhập, duyệt thư và gửi thư. |
| `client_gui.py` | Mail Client GUI | Giao diện đồ họa người dùng: Hộp thư đến, xem thư, soạn thư nội bộ / Gmail, mở nhiều cửa sổ độc lập (`-n 2`). |
| `demo_test.py` | Kiểm thử tự động | Kịch bản kiểm thử độc lập tự động thực thi và xác thực toàn bộ 6 bước yêu cầu của bài toán. |

---

## 3. THIẾT KẾ GIAO THỨC TRUYỀN THÔNG TẦNG ỨNG DỤNG (UDP)

Hệ thống giao tiếp thông qua các gói tin UDP Datagram chứa chuỗi JSON mã hóa UTF-8. Để khắc phục nhược điểm phi trạng thái (stateless) và không tin cậy của UDP, hệ thống triển khai:
1. **Trường `req_id` (Request ID):** Mỗi yêu cầu gửi từ Client sinh một mã UUID ngẫu nhiên. Khi Server phản hồi, Server gửi kèm đúng `req_id` đó để Client khớp gói tin trong hàng đợi đa luồng.
2. **Cơ chế Timeout & Retry:** Client thiết lập timeout chờ phản hồi (3s cho nội bộ, 20s cho SMTP Gmail).
3. **Cơ chế Broadcast dừng server:** Server phát gói tin dừng 3 lần liên tiếp cách nhau 15ms để đảm bảo không bị rớt gói tin.

### 3.1. Bảng đặc tả chi tiết các gói tin JSON

| Mã lệnh (Action) | Gói tin Request (Client -> Server) | Gói tin Response (Server -> Client) | Diễn giải chức năng |
| :--- | :--- | :--- | :--- |
| `CONNECT` | `{"action": "CONNECT", "req_id": "uuid"}` | `{"status": "SUCCESS", "message": "...", "req_id": "uuid"}` | Bắt tay kiểm tra kết nối Server |
| `REGISTER` | `{"action": "REGISTER", "username": "u", "password": "p", "req_id": "uuid"}` | `{"status": "SUCCESS/ERROR", "message": "...", "req_id": "uuid"}` | Đăng ký: tạo thư mục và file `new_email.txt` |
| `LOGIN` | `{"action": "LOGIN", "username": "u", "password": "p", "req_id": "uuid"}` | `{"status": "SUCCESS", "username": "u", "files": ["f1", ...], "req_id": "uuid"}` | Xác thực và trả về danh sách file thư |
| `LIST_FILES` | `{"action": "LIST_FILES", "username": "u", "req_id": "uuid"}` | `{"status": "SUCCESS", "files": ["new_email.txt", ...], "req_id": "uuid"}` | Làm mới danh sách file thư mục |
| `READ_EMAIL` | `{"action": "READ_EMAIL", "username": "u", "filename": "fn", "req_id": "uuid"}` | `{"status": "SUCCESS", "filename": "fn", "content": "...", "req_id": "uuid"}` | Đọc nội dung file thư được chọn |
| `SEND_EMAIL` | `{"action": "SEND_EMAIL", "from": "u1", "to": "u2/email", "subject": "s", "content": "c", "req_id": "uuid"}` | `{"status": "SUCCESS", "message": "...", "delivery_type": "LOCAL/GMAIL", "email_id": 1, "req_id": "uuid"}` | Gửi thư: lưu file + CSDL hoặc gửi ra Gmail |
| `LOGOUT` | `{"action": "LOGOUT", "username": "u", "req_id": "uuid"}` | `{"status": "SUCCESS", "message": "Đã đăng xuất.", "req_id": "uuid"}` | Đăng xuất phiên làm việc |
| `SERVER_STOPPED` | *(Server phát tín hiệu chủ động)* | `{"action": "SERVER_STOPPED", "status": "SERVER_STOPPED", "message": "..."}` | Bắt buộc mọi Client văng về màn hình login |
| `QUIT` | `{"action": "QUIT", "req_id": "uuid"}` | `{"status": "SUCCESS", "message": "Tạm biệt!", "req_id": "uuid"}` | Đóng socket Client |

---

## 4. THIẾT KẾ CƠ SỞ DỮ LIỆU POSTGRESQL (PGADMIN 4) & SQLITE

Hệ thống được thiết kế theo kiến trúc **Dual-Database** nhằm đạt tiêu chuẩn doanh nghiệp:
- **Cơ sở dữ liệu chính: PostgreSQL (Port 5432)** phục vụ xem, truy vấn và quản trị chuyên nghiệp trên **pgAdmin 4**.
- **Cơ sở dữ liệu phụ: SQLite (`server_storage/mail_server.db`)** chạy song song giúp hệ thống không phụ thuộc và có khả năng chạy độc lập khi không có PostgreSQL.

### 4.1. Thiết kế Schema trên PostgreSQL (Hiển thị trong pgAdmin 4)

Database chuyên biệt: **`mail_server`** (Server tự động kiểm tra và khởi tạo nếu chưa có thông qua hàm `ensure_pg_database_exists`).

#### Bảng `accounts` (Lưu trữ thông tin tài khoản)
```sql
CREATE TABLE IF NOT EXISTS accounts (
    username VARCHAR(100) PRIMARY KEY,
    password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Bảng `emails` (Lưu trữ lịch sử và nội dung toàn bộ email)
```sql
CREATE TABLE IF NOT EXISTS emails (
    id SERIAL PRIMARY KEY,
    sender VARCHAR(100) NOT NULL,
    recipient VARCHAR(100) NOT NULL,
    subject VARCHAR(255),
    content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    delivery_type VARCHAR(20) NOT NULL,  -- 'LOCAL', 'GMAIL', 'BOTH'
    status VARCHAR(20) NOT NULL,         -- 'SUCCESS', 'FAILED'
    status_message TEXT DEFAULT '',
    file_path TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_emails_sender ON emails(sender);
CREATE INDEX IF NOT EXISTS idx_emails_recipient ON emails(recipient);
CREATE INDEX IF NOT EXISTS idx_emails_created_at ON emails(created_at);
```

### 4.2. File cấu hình kết nối CSDL: `server_storage/db_config.json`
```json
{
    "db_type": "postgres",
    "postgres": {
        "host": "localhost",
        "port": 5432,
        "database": "mail_server",
        "user": "postgres",
        "password": "123"
    }
}
```

### 4.3. Quản trị trực quan qua pgAdmin 4
Người dùng mở **pgAdmin 4**, đăng nhập vào PostgreSQL, mở rộng cây thư mục:
👉 `Servers` ➔ `PostgreSQL` ➔ `Databases` ➔ `mail_server` ➔ `Schemas` ➔ `public` ➔ `Tables`:
- Nhấp chuột phải vào `emails` ➔ chọn **View/Edit Data ➔ All Rows** để xem toàn bộ danh sách email được Server lưu trữ trực tiếp.
- Nhấp chuột phải vào `accounts` để xem danh sách tài khoản đã đăng ký.

---

## 5. CƠ CHẾ GỬI EMAIL THỰC TẾ RA GMAIL (GMAIL SMTP RELAY)

### 5.1. Quy trình kết nối và gửi thư
Khi người dùng soạn thư trên Client và nhập người nhận có định dạng email (ví dụ: `tranthang20060903@gmail.com`):
1. **Nhận diện địa chỉ:** Hàm `is_email_address()` xác thực địa chỉ hợp lệ bằng biểu thức chính quy Regex.
2. **Kiểm tra cấu hình:** Đọc `server_storage/smtp_config.json` để lấy Email người gửi và Google App Password.
3. **Mã hóa MIME chuẩn quốc tế:**
   - Tiêu đề (`Subject`) và Tên hiển thị (`From`) được mã hóa qua `email.header.Header(..., 'utf-8')` giúp tiếng Việt có dấu hiển thị chuẩn 100% trên giao diện Gmail Web và App di động.
   - Thân thư đính kèm chữ ký xác nhận thư chuyển tiếp từ Socket Server.
4. **Kết nối máy chủ Google SMTP:**
   - Mở socket TCP tới `smtp.gmail.com:587`.
   - Bắt tay `EHLO`, kích hoạt mã hóa kênh truyền bảo mật **STARTTLS**.
   - Xác thực tài khoản với Google qua mật khẩu ứng dụng 16 ký tự.
   - Chuyển phát thông điệp (`server.send_message(msg)`).
5. **Ghi nhận CSDL:** Lưu bản ghi vào PostgreSQL và SQLite với `delivery_type='GMAIL'` và trạng thái `SUCCESS`.

### 5.2. File cấu hình SMTP: `server_storage/smtp_config.json`
```json
{
    "enabled": true,
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "use_tls": true,
    "sender_email": "tranthang20060903@gmail.com",
    "sender_password": "xxxx xxxx xxxx xxxx",
    "sender_name": "Python Mail Server"
}
```

---

## 6. CÁC TÍNH NĂNG NỔI BẬT & CHI TIẾT CÀI ĐẶT

### 6.1. Xử lý đa luồng non-blocking (Worker Threads)
Trong `server.py`, luồng chính chỉ đảm nhận việc `recvfrom()` gói tin UDP. Ngay khi có gói tin, Server tạo một luồng riêng:
```python
threading.Thread(
    target=dispatch_client_packet,
    args=(self.server_sock, client_addr, req),
    daemon=True
).start()
```
Điều này đảm bảo khi một người dùng gửi email ra Gmail (mất 2 - 4 giây để bắt tay TLS với Google), các client khác vẫn đăng nhập, đọc thư và gửi thư nội bộ tức thì mà không gặp hiện tượng giật lag hay nghẽn mạng.

### 6.2. Tính năng Auto-Kickback khi dừng Server
Khi quản trị viên bấm nút **`⏹ Dừng Server`**:
- Server gửi gói tin `SERVER_STOPPED` 3 lần liên tiếp tới toàn bộ danh sách Client online trong bộ nhớ đệm `active_clients`.
- Client GUI nhận được tín hiệu sẽ lập tức hủy phiên làm việc hiện tại, đưa người dùng trở lại màn hình Đăng nhập kèm hộp thoại thông báo.

### 6.3. Tự động kiểm tra và khởi tạo CSDL
Hàm `ensure_pg_database_exists()` trong `db_manager.py` tự động kết nối vào maintenance database của PostgreSQL, kiểm tra xem `mail_server` đã tồn tại chưa và tự động thực thi `CREATE DATABASE "mail_server"` cùng các bảng cần thiết mà không yêu cầu người dùng phải gõ lệnh SQL thủ công.

---

## 7. GIAO DIỆN NGƯỜI DÙNG & HỆ THỐNG QUẢN TRỊ (GUI & CLI)

### 7.1. Máy chủ Quản trị (`server_gui.py`)
Giao diện quản trị Tkinter phong cách Dashboard hiện đại chia thành các khu vực:
- **Thanh điều khiển trên:** Bật/Tắt Server, chỉnh Host/Port, nút mở nhanh Client GUI.
- **Thẻ KPI thời gian thực:** Trạng thái Server (ĐANG CHẠY / ĐANG DỪNG), Số tài khoản, Số lượng Email lưu trữ (`X DB (Y Files)`), Số Client kết nối trực tuyến.
- **Hệ thống 6 Tab chức năng:**
  1. `📜 Nhật Ký Hoạt Động (Live Logs)`: Console màu sắc trực quan theo từng loại sự kiện.
  2. `📁 Quản Lý Tài Khoản & Hộp Thư`: Quản lý cây thư mục, xem trước file thư, tạo/xóa tài khoản.
  3. `🗄️ Cơ Sở Dữ Liệu (Database)`: Tìm kiếm, lọc theo LOCAL/GMAIL/SUCCESS/FAILED, xem chi tiết popup nội dung thư trong CSDL.
  4. `⚙️ Cấu Hình Gmail (SMTP)`: Form nhập tài khoản Gmail, nút Kiểm tra kết nối Gmail tức thì.
  5. `🔌 Kết Nối Trực Tuyến`: Danh sách IP:Port các Client đang mở kết nối UDP.
  6. `ℹ️ Hướng Dẫn & Giao Thức`: Toàn văn tài liệu hướng dẫn và đặc tả gói tin.

### 7.2. Ứng dụng Máy khách (`client_gui.py` & `client.py`)
- Kết nối tới Server UDP theo IP và Port linh hoạt.
- Hỗ trợ mở nhiều cửa sổ Client cùng lúc bằng nút `➕ Mở Cửa Sổ Mới` hoặc lệnh `python3 client_gui.py -n 3`.
- Giao diện Hộp thư đến hiển thị danh sách thư, click chọn file để đọc ngay.
- Cửa sổ Soạn email hỗ trợ gửi đồng thời tới tài khoản nội bộ (ví dụ: `bob`) hoặc địa chỉ Gmail thật (`user@gmail.com`).

---

## 8. KỊCH BẢN KIỂM THỬ & KẾT QUẢ THỰC NGHIỆM

Hệ thống được kiểm thử tự động toàn diện qua file [demo_test.py](file:///home/tmthang/Downloads/2026-2027/K%C3%AC%201/L%E1%BA%ADp%20tr%C3%ACnh%20m%E1%BA%A1ng/mail_server/demo_test.py):

### Nhật ký kiểm thử thực tế (Terminal Output):
```
=================================================================
 BẮT ĐẦU KIỂM THỬ HỆ THỐNG MAIL SERVER GIAO THỨC UDP
=================================================================

[Bước 1] Khởi động Mail Server UDP tại 127.0.0.1:19876...
[POSTGRES] Tự động tạo database 'mail_server' trên PostgreSQL thành công!
[POSTGRES] Khởi tạo các bảng 'accounts' và 'emails' trên PostgreSQL thành công!
[2026-10-25 22:19:16] ============================================================
[2026-10-25 22:19:16]  MAIL SERVER (UDP SOCKET) ĐANG CHẠY TẠI 127.0.0.1:19876
[2026-10-25 22:19:16]  Thư mục lưu trữ: server_storage
[2026-10-25 22:19:16]  Sẵn sàng tiếp nhận các gói tin UDP từ client...
[2026-10-25 22:19:16] ============================================================
 -> Server UDP đã khởi động thành công.
 -> Kết nối UDP Client - Server thành công.

[Bước 2] Kiểm tra Đăng Ký (REGISTER) tài khoản 'alice_udp'...
 -> Server phản hồi: Đăng ký tài khoản 'alice_udp' thành công! Thư mục cá nhân và new_email.txt đã được tạo.
 -> Đã xác minh: Thư mục 'alice_udp' và file 'new_email.txt' tồn tại với đúng nội dung đề bài!

[Bước 3] Kiểm tra Đăng Nhập (LOGIN) tài khoản 'alice_udp'...
 -> Đăng nhập thành công, Server đã gửi danh sách file: ['new_email.txt']

[Bước 4] Kiểm tra Tạo tài khoản 'bob_udp' và Gửi email tới 'alice_udp'...
[POSTGRES] Đã lưu email #1 vào PostgreSQL thành công (sẵn sàng hiển thị trên pgAdmin 4)!
 -> Gửi email thành công: File 'email_bob_udp_*.txt' đã được tạo trong thư mục alice_udp và CSDL.

[Bước 5] Kiểm tra 'alice_udp' tải danh sách file và Đọc nội dung email...
 -> Đọc email thành công! Nội dung hiển thị chính xác tiêu đề và nội dung.

[Bước 6] Kiểm tra tính năng DỪNG SERVER -> Client nhận thông báo và văng ra đăng nhập...
 -> Client đã nhận thành công gói tin dừng từ Server: SERVER_STOPPED.
 -> Xác nhận client tự động văng về giao diện đăng nhập thành công!

=================================================================
 [HOÀN TẤT] TẤT CẢ 6 BƯỚC KIỂM THỬ UDP ĐÃ THÀNH CÔNG 100%!
=================================================================
```

---

## 9. HƯỚNG DẪN CÀI ĐẶT, VẬN HÀNH & KẾT NỐI PGADMIN 4

### 9.1. Cài đặt các gói phụ thuộc trên Ubuntu
```bash
sudo apt update
sudo apt install -y python3-tk python3-psycopg2
```

### 9.2. Cấu hình quyền PostgreSQL (nếu chưa đặt mật khẩu)
Đặt mật khẩu tài khoản `postgres` thành `123`:
```bash
sudo -u postgres psql -c "ALTER USER postgres WITH PASSWORD '123';"
```

### 9.3. Vận hành hệ thống
1. **Khởi động Mail Server GUI:**
   ```bash
   python3 server_gui.py
   ```
   - Bấm **`▶ Khởi Động Server`**. Server sẽ tự động kết nối PostgreSQL, tạo database `mail_server` và sẵn sàng nhận gói tin UDP.
   - Sang Tab **`⚙️ Cấu Hình Gmail (SMTP)`** để nhập tài khoản gửi Gmail nếu cần gửi ra Internet.
2. **Khởi động Mail Client GUI:**
   ```bash
   python3 client_gui.py
   ```
   - Bấm **`Kết nối Server (UDP)`**.
   - Đăng nhập (ví dụ: `thang` / `123`) hoặc Đăng ký tài khoản mới.
   - Bấm **`+ Soạn Email Mới`** để gửi thư nội bộ hoặc gửi ra Gmail thực tế.
3. **Xem dữ liệu trên pgAdmin 4:**
   - Mở **pgAdmin 4**.
   - Mở rộng: `Servers` ➔ `Databases` ➔ click chuột phải chọn **Refresh** ➔ xuất hiện database **`mail_server`**.
   - Mở: `mail_server` ➔ `Schemas` ➔ `public` ➔ `Tables` ➔ nhấp chuột phải vào `emails` chọn **View/Edit Data ➔ All Rows** để xem dữ liệu.

---

## 10. KẾT LUẬN & HƯỚNG PHÁT TRIỂN

### 10.1. Đánh giá kết quả đạt được
- **Về lý thuyết mạng:** Nắm vững cấu trúc Socket UDP, đóng gói dữ liệu JSON tầng ứng dụng, cơ chế kiểm soát lỗi và độ tin cậy trên giao thức không kết nối.
- **Về tính năng đề bài:** Đáp ứng 100% chuẩn xác mọi tiêu chí kỹ thuật (Register, file `new_email.txt`, Send Email, Login duyệt thư mục, Auto Kickback khi dừng server).
- **Về tính thực tiễn & mở rộng:** Tích hợp thành công **PostgreSQL** (pgAdmin 4), cơ chế sao lưu **SQLite**, và dịch vụ gửi thư thực tế **Gmail SMTP Relay**.

### 10.2. Hướng mở rộng trong tương lai
- Phát triển kỹ thuật phân mảnh và tái hợp gói tin (Packet Chunking & Reassembly) để hỗ trợ gửi các file đính kèm đa phương tiện dung lượng lớn qua UDP.
- Tích hợp giao thức nhận thư chuẩn **POP3 / IMAP** để kéo email từ Gmail về hiển thị hai chiều trên Client GUI.
- Triển khai bảo mật mã hóa đầu cuối (End-to-End Encryption) bằng thuật toán RSA / AES.
