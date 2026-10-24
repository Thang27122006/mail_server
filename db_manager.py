"""
db_manager.py - Quản lý Cơ sở dữ liệu SQLite cho Mail Server
Lưu trữ thông tin tài khoản và toàn bộ email (gửi nội bộ hoặc gửi ra Gmail thực tế).
Đảm bảo an toàn đa luồng (thread-safe) với threading.Lock và chế độ WAL.
"""
import os
import sqlite3
import threading
from datetime import datetime
from typing import Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.path.join(BASE_DIR, "server_storage")
DB_FILE = os.path.join(STORAGE_DIR, "mail_server.db")

_db_lock = threading.Lock()


def get_connection():
    """Tạo kết nối tới SQLite với timeout 15s và kích hoạt chế độ row factory."""
    if not os.path.exists(STORAGE_DIR):
        os.makedirs(STORAGE_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_FILE, timeout=15.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Khởi tạo các bảng cơ sở dữ liệu nếu chưa tồn tại."""
    with _db_lock:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Bật WAL mode để xử lý đọc/ghi đồng thời tốt hơn
            cursor.execute("PRAGMA journal_mode=WAL;")

            # Bảng lưu thông tin tài khoản
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    username TEXT PRIMARY KEY,
                    password TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
            """)

            # Bảng lưu thông tin email (cả local và thực tế qua Gmail)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender TEXT NOT NULL,
                    recipient TEXT NOT NULL,
                    subject TEXT,
                    content TEXT,
                    created_at TEXT NOT NULL,
                    delivery_type TEXT NOT NULL,  -- 'LOCAL', 'GMAIL', 'BOTH'
                    status TEXT NOT NULL,         -- 'SUCCESS', 'FAILED'
                    status_message TEXT DEFAULT '',
                    file_path TEXT DEFAULT ''
                );
            """)

            # Index tối ưu hóa tìm kiếm
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_emails_sender ON emails(sender);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_emails_recipient ON emails(recipient);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_emails_created_at ON emails(created_at);")

            conn.commit()
        finally:
            conn.close()


def save_account(username: str, password: str, created_at: Optional[str] = None) -> bool:
    """Lưu hoặc cập nhật tài khoản vào CSDL."""
    if not created_at:
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _db_lock:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO accounts (username, password, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    password = excluded.password;
            """, (username, password, created_at))
            conn.commit()
            return True
        except Exception as e:
            print(f"[DB ERROR] save_account error: {e}")
            return False
        finally:
            conn.close()


def delete_account(username: str) -> bool:
    """Xóa tài khoản khỏi CSDL."""
    with _db_lock:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM accounts WHERE username = ?", (username,))
            conn.commit()
            return True
        except Exception as e:
            print(f"[DB ERROR] delete_account error: {e}")
            return False
        finally:
            conn.close()


def sync_accounts(accounts_dict: Dict[str, dict]):
    """Đồng bộ tài khoản từ accounts.json vào SQLite."""
    if not accounts_dict:
        return
    with _db_lock:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            for user, info in accounts_dict.items():
                pwd = info.get("password", "")
                created = info.get("created_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("""
                    INSERT INTO accounts (username, password, created_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(username) DO UPDATE SET password = excluded.password;
                """, (user, pwd, created))
            conn.commit()
        except Exception as e:
            print(f"[DB ERROR] sync_accounts error: {e}")
        finally:
            conn.close()


def get_all_accounts() -> List[dict]:
    """Lấy danh sách tất cả tài khoản từ CSDL."""
    with _db_lock:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT username, password, created_at FROM accounts ORDER BY username ASC;")
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def save_email(
    sender: str,
    recipient: str,
    subject: str,
    content: str,
    delivery_type: str = "LOCAL",
    status: str = "SUCCESS",
    status_message: str = "",
    file_path: str = "",
    created_at: Optional[str] = None
) -> int:
    """
    Lưu email vào CSDL. Trả về ID của email vừa lưu (hoặc -1 nếu lỗi).
    delivery_type: 'LOCAL', 'GMAIL', 'BOTH'
    status: 'SUCCESS', 'FAILED'
    """
    if not created_at:
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with _db_lock:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO emails (sender, recipient, subject, content, created_at, delivery_type, status, status_message, file_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (sender, recipient, subject, content, created_at, delivery_type, status, status_message, file_path))
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            print(f"[DB ERROR] save_email error: {e}")
            return -1
        finally:
            conn.close()


def get_emails(
    limit: int = 200,
    search_query: str = "",
    delivery_filter: str = "",
    status_filter: str = ""
) -> List[dict]:
    """
    Lấy danh sách email từ CSDL kèm lọc và tìm kiếm.
    """
    with _db_lock:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT id, sender, recipient, subject, content, created_at, delivery_type, status, status_message, file_path FROM emails WHERE 1=1"
            params = []

            if delivery_filter and delivery_filter != "TẤT CẢ":
                query += " AND delivery_type = ?"
                params.append(delivery_filter)

            if status_filter and status_filter != "TẤT CẢ":
                query += " AND status = ?"
                params.append(status_filter)

            if search_query:
                like_term = f"%{search_query.strip()}%"
                query += " AND (sender LIKE ? OR recipient LIKE ? OR subject LIKE ? OR content LIKE ?)"
                params.extend([like_term, like_term, like_term, like_term])

            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def get_email_by_id(email_id: int) -> Optional[dict]:
    """Lấy chi tiết 1 email theo ID."""
    with _db_lock:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM emails WHERE id = ?", (email_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def get_total_email_count() -> int:
    """Đếm tổng số email đã lưu trong CSDL."""
    with _db_lock:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM emails")
            row = cursor.fetchone()
            return row[0] if row else 0
        finally:
            conn.close()


def delete_email(email_id: int) -> bool:
    """Xóa 1 bản ghi email trong CSDL."""
    with _db_lock:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM emails WHERE id = ?", (email_id,))
            conn.commit()
            return True
        except Exception as e:
            print(f"[DB ERROR] delete_email error: {e}")
            return False
        finally:
            conn.close()
