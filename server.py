import os
import sys

# Đảm bảo UTF-8 hoạt động trên console Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import json
import socket
import threading
import time
from datetime import datetime
from common import (
    DEFAULT_HOST,
    DEFAULT_SERVER_HOST,
    DEFAULT_PORT,
    WELCOME_EMAIL_FILENAME,
    WELCOME_EMAIL_CONTENT,
    setup_udp_socket,
    send_json,
    recv_json_from,
    get_lan_ip,
)
import db_manager
import smtp_service

# Thư mục lưu trữ dữ liệu Mail Server
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.path.join(BASE_DIR, "server_storage")
ACCOUNTS_FILE = os.path.join(STORAGE_DIR, "accounts.json")

# Khóa luồng để đồng bộ ghi file accounts.json
accounts_lock = threading.Lock()

# Callbacks và quản lý kết nối client cho GUI
LOG_CALLBACK = None
ACTIVE_CLIENT_CALLBACK = None
# active_clients: client_addr -> {"addr": client_addr, "user": str, "last_seen": float}
active_clients = {}
active_clients_lock = threading.Lock()


def set_log_callback(cb):
    """Đặt hàm callback nhận log theo thời gian thực (dùng cho GUI)."""
    global LOG_CALLBACK
    LOG_CALLBACK = cb


def set_client_callback(cb):
    """Đặt hàm callback nhận thông báo thay đổi số lượng client kết nối."""
    global ACTIVE_CLIENT_CALLBACK
    ACTIVE_CLIENT_CALLBACK = cb


def get_active_clients() -> dict:
    """Trả về bản sao danh sách client đang kết nối."""
    with active_clients_lock:
        return dict(active_clients)


def init_storage():
    """Khởi tạo thư mục server_storage, file accounts.json, CSDL SQLite và cấu hình SMTP."""
    if not os.path.exists(STORAGE_DIR):
        os.makedirs(STORAGE_DIR, exist_ok=True)
    if not os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=4, ensure_ascii=False)

    # Khởi tạo CSDL SQLite và đồng bộ tài khoản
    db_manager.init_db()
    accs = load_accounts()
    db_manager.sync_accounts(accs)
    # Tải cấu hình SMTP nếu chưa có
    smtp_service.load_smtp_config()


def load_accounts() -> dict:
    """Tải danh sách tài khoản từ file."""
    with accounts_lock:
        if not os.path.exists(ACCOUNTS_FILE):
            return {}
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}


def save_accounts(accounts: dict):
    """Lưu danh sách tài khoản vào file."""
    with accounts_lock:
        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
            json.dump(accounts, f, indent=4, ensure_ascii=False)


def log(msg: str):
    """Ghi log có kèm timestamp."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{now_str}] {msg}"
    print(formatted)
    if LOG_CALLBACK:
        try:
            LOG_CALLBACK(formatted)
        except Exception:
            pass


def handle_register(server_sock: socket.socket, client_addr: tuple, data: dict):
    """
    Xử lý tạo account mới qua UDP:
    1. Tạo thư mục tương ứng ở máy server: server_storage/<username>
    2. Tạo file new_email.txt có nội dung:
       'Thank you for using this service. we hope that you will feel comfortabl........'
    """
    req_id = data.get("req_id")
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        send_json(server_sock, {
            "status": "ERROR",
            "message": "Tên đăng nhập và mật khẩu không được để trống!",
            "req_id": req_id
        }, client_addr)
        return

    accounts = load_accounts()
    if username in accounts:
        send_json(server_sock, {
            "status": "ERROR",
            "message": f"Tài khoản '{username}' đã tồn tại!",
            "req_id": req_id
        }, client_addr)
        log(f"[REGISTER FAILED] Tài khoản '{username}' đã tồn tại (từ {client_addr}).")
        return

    # Đường dẫn thư mục của user tại server
    user_dir = os.path.join(STORAGE_DIR, username)
    try:
        # Tạo thư mục tương ứng với account trên server
        os.makedirs(user_dir, exist_ok=True)

        # Tạo file new_email.txt với nội dung theo đúng yêu cầu đề bài
        welcome_file_path = os.path.join(user_dir, WELCOME_EMAIL_FILENAME)
        with open(welcome_file_path, "w", encoding="utf-8") as f:
            f.write(WELCOME_EMAIL_CONTENT)

        # Lưu thông tin tài khoản
        created_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        accounts[username] = {
            "password": password,
            "created_at": created_time
        }
        save_accounts(accounts)
        db_manager.save_account(username, password, created_time)

        log(f"[REGISTER SUCCESS] Đã tạo account '{username}' và thư mục '{user_dir}' cùng file '{WELCOME_EMAIL_FILENAME}'")
        send_json(server_sock, {
            "status": "SUCCESS",
            "message": f"Đăng ký tài khoản '{username}' thành công! Thư mục cá nhân và {WELCOME_EMAIL_FILENAME} đã được tạo.",
            "req_id": req_id
        }, client_addr)
    except Exception as e:
        log(f"[REGISTER ERROR] Không thể tạo tài khoản '{username}': {e}")
        send_json(server_sock, {
            "status": "ERROR",
            "message": f"Lỗi phía server khi tạo tài khoản: {e}",
            "req_id": req_id
        }, client_addr)


def handle_login(server_sock: socket.socket, client_addr: tuple, data: dict) -> str:
    """
    Xử lý đăng nhập qua UDP:
    1. Kiểm tra tài khoản và mật khẩu
    2. Mở thư mục tương ứng với account đó ở server
    3. Gửi tất cả các tên file của thư mục đó về client
    """
    req_id = data.get("req_id")
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    accounts = load_accounts()
    if username not in accounts or accounts[username]["password"] != password:
        send_json(server_sock, {
            "status": "ERROR",
            "message": "Sai tên đăng nhập hoặc mật khẩu!",
            "req_id": req_id
        }, client_addr)
        log(f"[LOGIN FAILED] Đăng nhập thất bại cho user '{username}' (từ {client_addr})")
        return ""

    user_dir = os.path.join(STORAGE_DIR, username)
    if not os.path.exists(user_dir):
        os.makedirs(user_dir, exist_ok=True)

    # Đọc tất cả các tên file trong thư mục của account
    filenames = []
    try:
        filenames = [
            f for f in os.listdir(user_dir)
            if os.path.isfile(os.path.join(user_dir, f))
        ]
        filenames.sort()
    except Exception as e:
        log(f"[LOGIN ERROR] Lỗi khi đọc thư mục '{user_dir}': {e}")

    log(f"[LOGIN SUCCESS] User '{username}' ({client_addr}) đã đăng nhập thành công. Gửi {len(filenames)} tên file về client.")
    send_json(server_sock, {
        "status": "SUCCESS",
        "message": f"Đăng nhập thành công! Chào mừng {username}.",
        "username": username,
        "files": filenames,
        "req_id": req_id
    }, client_addr)
    return username


def handle_send_email(server_sock: socket.socket, client_addr: tuple, current_user: str, data: dict):
    """
    Xử lý gửi email qua UDP:
    1. Nhận email từ client (người gửi, người nhận, tiêu đề, nội dung)
    2. Xác định gửi đến account nội bộ hay địa chỉ Gmail thực tế:
       - Nếu là địa chỉ Email/Gmail thực tế:
         + Chuyển tiếp gửi qua giao thức Gmail SMTP (smtp.gmail.com:587)
         + Lưu toàn bộ thông tin và kết quả gửi vào Cơ sở dữ liệu SQLite
       - Nếu là account nội bộ trên Server:
         + Lưu vào file email_<sender>_<timestamp>.txt trong thư mục account đó
         + Lưu thông tin vào Cơ sở dữ liệu SQLite
    """
    req_id = data.get("req_id")
    recipient = data.get("to", "").strip()
    subject = data.get("subject", "Không có tiêu đề").strip()
    content = data.get("content", "").strip()
    sender = data.get("from", "").strip() or current_user or "Khách"

    if not recipient:
        send_json(server_sock, {
            "status": "ERROR",
            "message": "Chưa chỉ định người nhận email!",
            "req_id": req_id
        }, client_addr)
        return

    # TRƯỜNG HỢP 1: GỬI THỰC TẾ VÀO ĐỊA CHỈ GMAIL (Hoặc bất kỳ địa chỉ Email hợp lệ)
    if smtp_service.is_email_address(recipient):
        smtp_cfg = smtp_service.load_smtp_config()
        if not smtp_cfg.get("enabled", False) or not smtp_cfg.get("sender_email") or not smtp_cfg.get("sender_password"):
            err_msg = (
                "Chưa cấu hình tài khoản gửi Gmail SMTP trên Server!\n"
                "Vui lòng mở Server GUI -> Tab '⚙️ Cấu Hình Gmail (SMTP)' để nhập Email gửi và Mật khẩu ứng dụng."
            )
            # Vẫn ghi nhận email gửi thất bại vào CSDL
            email_id = db_manager.save_email(
                sender=sender,
                recipient=recipient,
                subject=subject,
                content=content,
                delivery_type="GMAIL",
                status="FAILED",
                status_message=err_msg
            )
            log(f"[GMAIL FAILED] Gửi tới '{recipient}' thất bại: Chưa bật/cấu hình SMTP (Email ID #{email_id})")
            send_json(server_sock, {
                "status": "ERROR",
                "message": err_msg,
                "email_id": email_id,
                "req_id": req_id
            }, client_addr)
            return

        log(f"[SMTP SENDING] Đang gửi thư thực tế qua Gmail SMTP tới '{recipient}' (Người gửi: {sender})...")
        ok, msg_detail = smtp_service.send_gmail_smtp(
            to_email=recipient,
            subject=subject,
            content=content,
            sender_alias=sender
        )

        status_str = "SUCCESS" if ok else "FAILED"

        # Nếu người nhận cũng có thư mục nội bộ trên server thì lưu thêm file text
        recipient_dir = os.path.join(STORAGE_DIR, recipient)
        saved_file = ""
        if os.path.exists(recipient_dir):
            try:
                t_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                saved_file = f"email_{sender}_{t_str}.txt"
                with open(os.path.join(recipient_dir, saved_file), "w", encoding="utf-8") as f:
                    f.write(
                        f"Từ (From)      : {sender}\n"
                        f"Tới (To)        : {recipient}\n"
                        f"Thời gian (Date): {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"Tiêu đề (Subject): {subject}\n"
                        f"{'-'*50}\n"
                        f"Nội dung (Content):\n{content}\n"
                    )
            except Exception:
                pass

        # Lưu bản ghi vào CSDL SQLite
        email_id = db_manager.save_email(
            sender=sender,
            recipient=recipient,
            subject=subject,
            content=content,
            delivery_type="GMAIL",
            status=status_str,
            status_message=msg_detail,
            file_path=saved_file
        )

        if ok:
            log(f"[GMAIL SUCCESS] Đã gửi thư thực tế tới Gmail '{recipient}' (ID #{email_id}) và lưu CSDL thành công!")
            send_json(server_sock, {
                "status": "SUCCESS",
                "message": f"Đã gửi thư thực tế thành công vào Gmail '{recipient}' và lưu vào Database! (ID: #{email_id})",
                "email_id": email_id,
                "delivery_type": "GMAIL",
                "req_id": req_id
            }, client_addr)
        else:
            log(f"[GMAIL ERROR] Lỗi gửi thư tới Gmail '{recipient}': {msg_detail}")
            send_json(server_sock, {
                "status": "ERROR",
                "message": f"Không thể gửi thư tới Gmail: {msg_detail}\n(Email đã được lưu vào Database với trạng thái FAILED, ID: #{email_id})",
                "email_id": email_id,
                "delivery_type": "GMAIL",
                "req_id": req_id
            }, client_addr)
        return

    # TRƯỜNG HỢP 2: GỬI TỚI ACCOUNT NỘI BỘ TRÊN SERVER (GIỮ ĐÚNG YÊU CẦU ĐỀ BÀI)
    recipient_dir = os.path.join(STORAGE_DIR, recipient)
    if not os.path.exists(recipient_dir):
        send_json(server_sock, {
            "status": "ERROR",
            "message": f"Tài khoản người nhận '{recipient}' không tồn tại trên Mail Server và không phải địa chỉ Gmail hợp lệ!",
            "req_id": req_id
        }, client_addr)
        log(f"[SEND FAILED] Người nhận '{recipient}' không tồn tại (từ '{sender}' tại {client_addr})")
        return

    # Tạo tên file email (kèm timestamp để không bị trùng lặp)
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    email_filename = f"email_{sender}_{timestamp_str}.txt"
    email_filepath = os.path.join(recipient_dir, email_filename)

    # Đảm bảo tên file duy nhất
    counter = 1
    while os.path.exists(email_filepath):
        email_filename = f"email_{sender}_{timestamp_str}_{counter}.txt"
        email_filepath = os.path.join(recipient_dir, email_filename)
        counter += 1

    # Nội dung chi tiết của email được ghi vào file
    email_body = (
        f"Từ (From)      : {sender}\n"
        f"Tới (To)        : {recipient}\n"
        f"Thời gian (Date): {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Tiêu đề (Subject): {subject}\n"
        f"{'-'*50}\n"
        f"Nội dung (Content):\n{content}\n"
    )

    try:
        with open(email_filepath, "w", encoding="utf-8") as f:
            f.write(email_body)

        # Lưu bản ghi vào CSDL SQLite
        email_id = db_manager.save_email(
            sender=sender,
            recipient=recipient,
            subject=subject,
            content=content,
            delivery_type="LOCAL",
            status="SUCCESS",
            status_message=f"Lưu file {email_filename}",
            file_path=email_filename
        )

        log(f"[SEND SUCCESS] Email (ID #{email_id}) từ '{sender}' tới '{recipient}' đã lưu vào '{email_filename}' và CSDL.")
        send_json(server_sock, {
            "status": "SUCCESS",
            "message": f"Đã gửi email thành công tới '{recipient}' và lưu vào Database! (File: {email_filename})",
            "filename": email_filename,
            "email_id": email_id,
            "delivery_type": "LOCAL",
            "req_id": req_id
        }, client_addr)
    except Exception as e:
        log(f"[SEND ERROR] Không thể ghi file email vào '{recipient_dir}': {e}")
        send_json(server_sock, {
            "status": "ERROR",
            "message": f"Lỗi khi lưu email tại server: {e}",
            "req_id": req_id
        }, client_addr)


def handle_list_files(server_sock: socket.socket, client_addr: tuple, current_user: str, data: dict):
    """Lấy danh sách các file trong thư mục của tài khoản hiện tại qua UDP."""
    req_id = data.get("req_id")
    target_user = current_user or data.get("username", "").strip()
    if not target_user:
        send_json(server_sock, {
            "status": "ERROR",
            "message": "Bạn chưa đăng nhập!",
            "req_id": req_id
        }, client_addr)
        return

    user_dir = os.path.join(STORAGE_DIR, target_user)
    if not os.path.exists(user_dir):
        send_json(server_sock, {
            "status": "SUCCESS",
            "files": [],
            "req_id": req_id
        }, client_addr)
        return

    try:
        filenames = [
            f for f in os.listdir(user_dir)
            if os.path.isfile(os.path.join(user_dir, f))
        ]
        filenames.sort()
        send_json(server_sock, {
            "status": "SUCCESS",
            "files": filenames,
            "req_id": req_id
        }, client_addr)
    except Exception as e:
        send_json(server_sock, {
            "status": "ERROR",
            "message": f"Lỗi đọc thư mục: {e}",
            "req_id": req_id
        }, client_addr)


def handle_read_email(server_sock: socket.socket, client_addr: tuple, current_user: str, data: dict):
    """Đọc nội dung của một file email cụ thể qua UDP."""
    req_id = data.get("req_id")
    target_user = current_user or data.get("username", "").strip()
    if not target_user:
        send_json(server_sock, {
            "status": "ERROR",
            "message": "Bạn chưa đăng nhập!",
            "req_id": req_id
        }, client_addr)
        return

    filename = os.path.basename(data.get("filename", "").strip())
    if not filename:
        send_json(server_sock, {
            "status": "ERROR",
            "message": "Chưa chọn file cần đọc!",
            "req_id": req_id
        }, client_addr)
        return

    user_dir = os.path.join(STORAGE_DIR, target_user)
    filepath = os.path.join(user_dir, filename)

    if not os.path.exists(filepath):
        send_json(server_sock, {
            "status": "ERROR",
            "message": f"File '{filename}' không tồn tại!",
            "req_id": req_id
        }, client_addr)
        return

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        send_json(server_sock, {
            "status": "SUCCESS",
            "filename": filename,
            "content": content,
            "req_id": req_id
        }, client_addr)
        log(f"[READ EMAIL] User '{target_user}' đã đọc file '{filename}'")
    except Exception as e:
        send_json(server_sock, {
            "status": "ERROR",
            "message": f"Lỗi đọc file email: {e}",
            "req_id": req_id
        }, client_addr)


def dispatch_client_packet(server_sock: socket.socket, client_addr: tuple, req: dict):
    """Điều phối và xử lý một gói tin UDP từ client."""
    is_new_client = False
    with active_clients_lock:
        if client_addr not in active_clients:
            active_clients[client_addr] = {
                "addr": client_addr,
                "user": None,
                "last_seen": time.time()
            }
            is_new_client = True
        else:
            active_clients[client_addr]["last_seen"] = time.time()

    if is_new_client:
        log(f"[CONNECTED] Client mới kết nối qua UDP từ {client_addr}")
        if ACTIVE_CLIENT_CALLBACK:
            try:
                ACTIVE_CLIENT_CALLBACK(len(active_clients))
            except Exception:
                pass

    current_user = ""
    with active_clients_lock:
        info = active_clients.get(client_addr)
        if info:
            current_user = info.get("user") or ""

    action = req.get("action", "").upper()
    req_id = req.get("req_id")

    if action in ["CONNECT", "PING"]:
        send_json(server_sock, {
            "status": "SUCCESS",
            "message": "Kết nối Mail Server UDP thành công!",
            "req_id": req_id
        }, client_addr)

    elif action == "REGISTER":
        handle_register(server_sock, client_addr, req)

    elif action == "LOGIN":
        logged_in_user = handle_login(server_sock, client_addr, req)
        if logged_in_user:
            with active_clients_lock:
                if client_addr in active_clients:
                    active_clients[client_addr]["user"] = logged_in_user
            if ACTIVE_CLIENT_CALLBACK:
                try:
                    ACTIVE_CLIENT_CALLBACK(len(active_clients))
                except Exception:
                    pass

    elif action == "SEND_EMAIL":
        handle_send_email(server_sock, client_addr, current_user, req)

    elif action == "LIST_FILES":
        handle_list_files(server_sock, client_addr, current_user, req)

    elif action == "READ_EMAIL":
        handle_read_email(server_sock, client_addr, current_user, req)

    elif action == "LOGOUT":
        log(f"[LOGOUT] User '{current_user}' ({client_addr}) đã đăng xuất.")
        with active_clients_lock:
            if client_addr in active_clients:
                active_clients[client_addr]["user"] = None
        if ACTIVE_CLIENT_CALLBACK:
            try:
                ACTIVE_CLIENT_CALLBACK(len(active_clients))
            except Exception:
                pass
        send_json(server_sock, {
            "status": "SUCCESS",
            "message": "Đã đăng xuất thành công.",
            "req_id": req_id
        }, client_addr)

    elif action == "QUIT":
        with active_clients_lock:
            active_clients.pop(client_addr, None)
        if ACTIVE_CLIENT_CALLBACK:
            try:
                ACTIVE_CLIENT_CALLBACK(len(active_clients))
            except Exception:
                pass
        log(f"[CLOSED] Client {client_addr} đã thoát.")
        send_json(server_sock, {
            "status": "SUCCESS",
            "message": "Tạm biệt!",
            "req_id": req_id
        }, client_addr)

    else:
        send_json(server_sock, {
            "status": "ERROR",
            "message": f"Hành động không hợp lệ: '{action}'",
            "req_id": req_id
        }, client_addr)


class MailServerController:
    """Bộ điều khiển Mail Server UDP có thể bắt đầu / dừng linh hoạt cho cả CLI và GUI."""

    def __init__(self, host=DEFAULT_SERVER_HOST, port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self.server_sock = None
        self.is_running = False
        self.server_thread = None

    def start(self):
        """Bắt đầu lắng nghe gói tin UDP trên một luồng nền."""
        if self.is_running:
            return True, "Server đang chạy."
        init_storage()

        try:
            self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            setup_udp_socket(self.server_sock)
            self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_sock.bind((self.host, self.port))
            self.server_sock.settimeout(0.5)
            self.is_running = True

            lan_ip = get_lan_ip()
            log("=" * 60)
            log(f" MAIL SERVER (UDP SOCKET) ĐANG CHẠY TẠI {self.host}:{self.port}")
            if self.host in ["0.0.0.0", ""]:
                log(f" -> Máy khác trong mạng LAN kết nối bằng IP : {lan_ip}:{self.port}")
                log(f" -> Máy nội bộ (localhost) kết nối bằng IP: 127.0.0.1:{self.port}")
            log(f" Thư mục lưu trữ: {STORAGE_DIR}")
            log(f" Sẵn sàng tiếp nhận các gói tin UDP từ client...")
            log("=" * 60)

            self.server_thread = threading.Thread(target=self._run_server_loop, daemon=True)
            self.server_thread.start()
            return True, f"Server UDP đã khởi động thành công trên {self.host}:{self.port}"
        except Exception as e:
            self.is_running = False
            if self.server_sock:
                try:
                    self.server_sock.close()
                except Exception:
                    pass
                self.server_sock = None
            log(f"[FATAL ERROR] Lỗi server: {e}")
            return False, str(e)

    def _run_server_loop(self):
        """Vòng lặp nhận và xử lý datagram UDP từ client."""
        while self.is_running:
            try:
                if not self.server_sock:
                    break
                req, client_addr = recv_json_from(self.server_sock)
                if req is None or client_addr is None:
                    continue

                # Xử lý gói tin trên luồng nền để không nghẽn nhận UDP
                threading.Thread(
                    target=dispatch_client_packet,
                    args=(self.server_sock, client_addr, req),
                    daemon=True
                ).start()
            except (socket.timeout, BlockingIOError):
                continue
            except (ConnectionResetError, OSError):
                continue
            except Exception as e:
                if self.is_running:
                    log(f"[SERVER LOOP ERROR] {e}")
                break

        self.is_running = False
        log("[STOPPED] Mail Server đã dừng.")

    def stop(self):
        """
        Dừng Mail Server:
        1. Gửi thông báo SERVER_STOPPED tới TẤT CẢ các client đang kết nối (để client văng ra màn hình đăng nhập)
        2. Đóng socket và cập nhật trạng thái
        """
        if not self.is_running and not self.server_sock:
            return
        log("\n[STOPPING] Đang tắt Mail Server và thông báo ngắt kết nối tới các client...")
        self.is_running = False

        # 1. Thu thập danh sách tất cả các client đang online
        with active_clients_lock:
            clients_to_notify = list(active_clients.keys())
            active_clients.clear()

        # 2. Phát thông báo SERVER_STOPPED tới tất cả client (gửi 3 lần để tránh thất lạc gói UDP)
        if self.server_sock:
            stop_notification = {
                "action": "SERVER_STOPPED",
                "status": "SERVER_STOPPED",
                "message": "Máy chủ (Mail Server) đã dừng hoạt động. Bạn đã bị đưa về giao diện đăng nhập!"
            }
            for _ in range(3):
                for addr in clients_to_notify:
                    try:
                        send_json(self.server_sock, stop_notification, addr)
                    except Exception:
                        pass
                time.sleep(0.015)

        # 3. Cập nhật số client kết nối về 0 trên GUI
        if ACTIVE_CLIENT_CALLBACK:
            try:
                ACTIVE_CLIENT_CALLBACK(0)
            except Exception:
                pass

        # 4. Đóng socket lắng nghe UDP
        sock = self.server_sock
        self.server_sock = None
        if sock:
            try:
                sock.close()
            except Exception:
                pass

        log("[STOPPED] Mail Server đã dừng thành công. Đã thông báo cho tất cả client.")


def start_server(host=DEFAULT_SERVER_HOST, port=DEFAULT_PORT):
    """Khởi động Mail Server và lắng nghe kết nối (dùng cho chế độ Console)."""
    controller = MailServerController(host, port)
    ok, err = controller.start()
    if not ok:
        print(f"[-] Khởi động server thất bại: {err}")
        return
    try:
        while controller.is_running:
            time.sleep(0.5)
    except KeyboardInterrupt:
        controller.stop()


if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SERVER_HOST
    port = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_PORT
    start_server(host, port)


