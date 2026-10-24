"""
smtp_service.py - Dịch vụ gửi thư thực tế qua Gmail SMTP
Hỗ trợ xác thực tài khoản Gmail (bằng App Password của Google), mã hóa TLS cổng 587,
kiểm tra định dạng email và kiểm tra kết nối SMTP.
"""
import json
import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from typing import Dict, Tuple

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.path.join(BASE_DIR, "server_storage")
SMTP_CONFIG_FILE = os.path.join(STORAGE_DIR, "smtp_config.json")

EMAIL_REGEX = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")

DEFAULT_SMTP_CONFIG = {
    "enabled": False,
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "use_tls": True,
    "sender_email": "",
    "sender_password": "",
    "sender_name": "Python Mail Server"
}


def is_email_address(text: str) -> bool:
    """Kiểm tra một chuỗi có phải là địa chỉ email hợp lệ (vd: abc@gmail.com)."""
    if not text:
        return False
    return bool(EMAIL_REGEX.match(text.strip()))


def is_gmail_address(text: str) -> bool:
    """Kiểm tra một chuỗi có phải địa chỉ kết thúc bằng @gmail.com."""
    if not is_email_address(text):
        return False
    return text.strip().lower().endswith("@gmail.com")


def load_smtp_config() -> dict:
    """Tải cấu hình SMTP từ file json."""
    if not os.path.exists(STORAGE_DIR):
        os.makedirs(STORAGE_DIR, exist_ok=True)
    if not os.path.exists(SMTP_CONFIG_FILE):
        save_smtp_config(DEFAULT_SMTP_CONFIG)
        return dict(DEFAULT_SMTP_CONFIG)
    try:
        with open(SMTP_CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            # Điền các giá trị mặc định còn thiếu
            merged = dict(DEFAULT_SMTP_CONFIG)
            merged.update(cfg)
            return merged
    except Exception as e:
        print(f"[SMTP WARNING] Không thể đọc {SMTP_CONFIG_FILE}: {e}")
        return dict(DEFAULT_SMTP_CONFIG)


def save_smtp_config(config: dict):
    """Lưu cấu hình SMTP vào file json."""
    if not os.path.exists(STORAGE_DIR):
        os.makedirs(STORAGE_DIR, exist_ok=True)
    with open(SMTP_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)


def test_smtp_connection(
    host: str,
    port: int,
    sender_email: str,
    sender_password: str,
    use_tls: bool = True
) -> Tuple[bool, str]:
    """
    Kiểm tra thông tin đăng nhập SMTP với máy chủ Gmail.
    Trả về (True, "Thông báo thành công") hoặc (False, "Chi tiết lỗi").
    """
    sender_email = sender_email.strip()
    sender_password = sender_password.strip()

    if not sender_email or not sender_password:
        return False, "Vui lòng nhập đầy đủ Email gửi và Mật khẩu ứng dụng (App Password)!"

    try:
        server = smtplib.SMTP(host.strip(), int(port), timeout=12)
        server.ehlo()
        if use_tls:
            server.starttls()
            server.ehlo()
        server.login(sender_email, sender_password)
        server.quit()
        return True, f"Xác thực SMTP thành công với tài khoản '{sender_email}'!"
    except smtplib.SMTPAuthenticationError as e:
        return False, (
            "Lỗi xác thực (Authentication Error):\n"
            "Google từ chối mật khẩu. Vui lòng sử dụng 'Mật khẩu ứng dụng' (App Password 16 chữ cái), "
            "không dùng mật khẩu đăng nhập thông thường của Google.\n"
            f"Chi tiết từ Google: {e}"
        )
    except Exception as e:
        return False, f"Không thể kết nối đến máy chủ SMTP ({host}:{port}): {e}"


def send_gmail_smtp(
    to_email: str,
    subject: str,
    content: str,
    sender_alias: str = ""
) -> Tuple[bool, str]:
    """
    Gửi email thực tế tới hòm thư (ví dụ: Gmail) qua giao thức SMTP.
    Trả về (True, thông báo) hoặc (False, thông báo lỗi).
    """
    cfg = load_smtp_config()
    if not cfg.get("enabled", False):
        return False, "Tính năng gửi thư qua Gmail đang bị tắt trên Server! Hãy bật trong cấu hình."

    sender_email = cfg.get("sender_email", "").strip()
    sender_password = cfg.get("sender_password", "").strip()
    smtp_host = cfg.get("smtp_host", "smtp.gmail.com").strip()
    smtp_port = int(cfg.get("smtp_port", 587))
    use_tls = cfg.get("use_tls", True)
    sender_name = cfg.get("sender_name", "Python Mail Server").strip()

    if not sender_email or not sender_password or "DÁN_MẬT_KHẨU" in sender_password:
        return False, "Server chưa được điền Mật khẩu ứng dụng (App Password 16 chữ cái) của Google! Vui lòng mở file server_storage/smtp_config.json hoặc tab Cấu Hình Gmail trên Server GUI để dán mật khẩu."

    to_email = to_email.strip()
    if not is_email_address(to_email):
        return False, f"Địa chỉ '{to_email}' không đúng định dạng email!"

    try:
        # Tạo gói tin email chuẩn MIME
        from email.header import Header
        msg = MIMEMultipart()
        display_name = f"{sender_alias} qua Mail Server" if sender_alias else sender_name
        msg["From"] = f"{Header(display_name, 'utf-8').encode()} <{sender_email}>"
        msg["To"] = to_email
        msg["Subject"] = Header(subject or "Không có tiêu đề", "utf-8")
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid()

        # Nội dung email kèm chữ ký thông tin
        full_body = (
            f"{content}\n\n"
            f"-----------------------------------------\n"
            f"[Thư gửi từ Hệ thống Python Mail Server qua giao thức UDP & SMTP Relay]\n"
            f"Người gửi client: {sender_alias or 'Ẩn danh'}\n"
        )
        msg.attach(MIMEText(full_body, "plain", "utf-8"))

        # Kết nối và gửi qua SMTP
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
        server.ehlo()
        if use_tls:
            server.starttls()
            server.ehlo()

        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()

        return True, f"Đã gửi email thực tế thành công tới '{to_email}' qua Gmail SMTP!"
    except smtplib.SMTPAuthenticationError as e:
        return False, f"Lỗi xác thực Gmail SMTP: Mật khẩu ứng dụng không hợp lệ ({e})"
    except Exception as e:
        return False, f"Lỗi gửi thư qua SMTP: {e}"
