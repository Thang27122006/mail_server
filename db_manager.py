"""
db_manager.py - Quản lý Cơ sở dữ liệu cho Mail Server (Hỗ trợ cả PostgreSQL & SQLite)
- Tích hợp PostgreSQL: Tương thích hoàn hảo với pgAdmin 4.
- Tự động chuyển đổi hoặc sao lưu song song sang SQLite: Đảm bảo server không bao giờ bị lỗi kết nối.
- Đảm bảo an toàn đa luồng (thread-safe).
"""
import json
import os
import sqlite3
import threading
from datetime import datetime
from typing import Dict, List, Optional

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.path.join(BASE_DIR, "server_storage")
DB_FILE = os.path.join(STORAGE_DIR, "mail_server.db")
DB_CONFIG_FILE = os.path.join(STORAGE_DIR, "db_config.json")

_db_lock = threading.Lock()

DEFAULT_DB_CONFIG = {
    "db_type": "postgres",
    "postgres": {
        "host": "localhost",
        "port": 5432,
        "database": "postgres",
        "user": "postgres",
        "password": ""
    }
}


def load_db_config() -> dict:
    """Tải cấu hình cơ sở dữ liệu từ file json."""
    if not os.path.exists(STORAGE_DIR):
        os.makedirs(STORAGE_DIR, exist_ok=True)
    if not os.path.exists(DB_CONFIG_FILE):
        save_db_config(DEFAULT_DB_CONFIG)
        return dict(DEFAULT_DB_CONFIG)
    try:
        with open(DB_CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            merged = dict(DEFAULT_DB_CONFIG)
            merged.update(cfg)
            return merged
    except Exception as e:
        print(f"[DB CONFIG WARNING] Không thể đọc {DB_CONFIG_FILE}: {e}")
        return dict(DEFAULT_DB_CONFIG)


def save_db_config(config: dict):
    """Lưu cấu hình cơ sở dữ liệu vào file json."""
    if not os.path.exists(STORAGE_DIR):
        os.makedirs(STORAGE_DIR, exist_ok=True)
    with open(DB_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)


def ensure_pg_database_exists(host, port, user, password, target_db):
    """Tự động tạo database trên PostgreSQL nếu chưa có (dành cho pgAdmin 4)."""
    if not HAS_PSYCOPG2 or not target_db or target_db == "postgres":
        return
    try:
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
        admin_conn = psycopg2.connect(
            host=host,
            port=int(port),
            dbname="postgres",
            user=user,
            password=password,
            connect_timeout=4
        )
        admin_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = admin_conn.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (target_db,))
        if not cur.fetchone():
            cur.execute(f'CREATE DATABASE "{target_db}";')
            print(f"[POSTGRES] Tự động tạo database '{target_db}' trên PostgreSQL thành công!")
        cur.close()
        admin_conn.close()
    except Exception as e:
        pass


def get_pg_connection():
    """Tạo kết nối tới PostgreSQL (dành cho pgAdmin 4)."""
    if not HAS_PSYCOPG2:
        return None
    cfg = load_db_config()
    if cfg.get("db_type") != "postgres":
        return None
    pg_cfg = cfg.get("postgres", {})
    host = pg_cfg.get("host", "localhost")
    port = int(pg_cfg.get("port", 5432))
    target_db = pg_cfg.get("database", "mail_server")
    user = pg_cfg.get("user", "postgres")
    password = pg_cfg.get("password", "")

    # Tự động tạo database nếu chưa có trên PostgreSQL
    ensure_pg_database_exists(host, port, user, password, target_db)

    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=target_db,
            user=user,
            password=password,
            connect_timeout=4
        )
        return conn
    except Exception as e:
        return None


def get_sqlite_connection():
    """Tạo kết nối tới SQLite (dùng cục bộ hoặc khi PostgreSQL chưa sẵn sàng)."""
    if not os.path.exists(STORAGE_DIR):
        os.makedirs(STORAGE_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_FILE, timeout=15.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Khởi tạo các bảng trên cả PostgreSQL (cho pgAdmin 4) và SQLite."""
    with _db_lock:
        # 1. Khởi tạo SQLite
        s_conn = get_sqlite_connection()
        try:
            c = s_conn.cursor()
            c.execute("PRAGMA journal_mode=WAL;")
            c.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    username TEXT PRIMARY KEY,
                    password TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender TEXT NOT NULL,
                    recipient TEXT NOT NULL,
                    subject TEXT,
                    content TEXT,
                    created_at TEXT NOT NULL,
                    delivery_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    status_message TEXT DEFAULT '',
                    file_path TEXT DEFAULT ''
                );
            """)
            s_conn.commit()
        finally:
            s_conn.close()

        # 2. Khởi tạo PostgreSQL (nếu đã kết nối được)
        pg_conn = get_pg_connection()
        if pg_conn:
            try:
                c = pg_conn.cursor()
                c.execute("""
                    CREATE TABLE IF NOT EXISTS accounts (
                        username VARCHAR(100) PRIMARY KEY,
                        password VARCHAR(255) NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                c.execute("""
                    CREATE TABLE IF NOT EXISTS emails (
                        id SERIAL PRIMARY KEY,
                        sender VARCHAR(100) NOT NULL,
                        recipient VARCHAR(100) NOT NULL,
                        subject VARCHAR(255),
                        content TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        delivery_type VARCHAR(20) NOT NULL,
                        status VARCHAR(20) NOT NULL,
                        status_message TEXT DEFAULT '',
                        file_path TEXT DEFAULT ''
                    );
                """)
                pg_conn.commit()
                print("[POSTGRES] Khởi tạo các bảng 'accounts' và 'emails' trên PostgreSQL thành công!")
            except Exception as e:
                print(f"[POSTGRES INIT ERROR] {e}")
            finally:
                pg_conn.close()


def save_account(username: str, password: str, created_at: Optional[str] = None) -> bool:
    """Lưu hoặc cập nhật tài khoản vào PostgreSQL và SQLite."""
    if not created_at:
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with _db_lock:
        # Ghi vào PostgreSQL
        pg_conn = get_pg_connection()
        if pg_conn:
            try:
                c = pg_conn.cursor()
                c.execute("""
                    INSERT INTO accounts (username, password, created_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT(username) DO UPDATE SET password = EXCLUDED.password;
                """, (username, password, created_at))
                pg_conn.commit()
            except Exception as e:
                print(f"[POSTGRES ERROR] save_account: {e}")
            finally:
                pg_conn.close()

        # Ghi vào SQLite
        s_conn = get_sqlite_connection()
        try:
            c = s_conn.cursor()
            c.execute("""
                INSERT INTO accounts (username, password, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET password = excluded.password;
            """, (username, password, created_at))
            s_conn.commit()
            return True
        except Exception as e:
            print(f"[SQLITE ERROR] save_account: {e}")
            return False
        finally:
            s_conn.close()


def delete_account(username: str) -> bool:
    """Xóa tài khoản khỏi PostgreSQL và SQLite."""
    with _db_lock:
        pg_conn = get_pg_connection()
        if pg_conn:
            try:
                c = pg_conn.cursor()
                c.execute("DELETE FROM accounts WHERE username = %s;", (username,))
                pg_conn.commit()
            except Exception as e:
                print(f"[POSTGRES ERROR] delete_account: {e}")
            finally:
                pg_conn.close()

        s_conn = get_sqlite_connection()
        try:
            c = s_conn.cursor()
            c.execute("DELETE FROM accounts WHERE username = ?;", (username,))
            s_conn.commit()
            return True
        except Exception as e:
            print(f"[SQLITE ERROR] delete_account: {e}")
            return False
        finally:
            s_conn.close()


def sync_accounts(accounts_dict: Dict[str, dict]):
    """Đồng bộ tài khoản từ accounts.json vào cả PostgreSQL và SQLite."""
    if not accounts_dict:
        return
    for user, info in accounts_dict.items():
        pwd = info.get("password", "")
        created = info.get("created_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_account(user, pwd, created)


def get_all_accounts() -> List[dict]:
    """Lấy danh sách tài khoản (ưu tiên từ PostgreSQL nếu có, ngược lại từ SQLite)."""
    with _db_lock:
        pg_conn = get_pg_connection()
        if pg_conn:
            try:
                c = pg_conn.cursor(cursor_factory=RealDictCursor)
                c.execute("SELECT username, password, to_char(created_at, 'YYYY-MM-DD HH24:MI:SS') as created_at FROM accounts ORDER BY username ASC;")
                rows = c.fetchall()
                return [dict(r) for r in rows]
            except Exception as e:
                print(f"[POSTGRES ERROR] get_all_accounts: {e}")
            finally:
                pg_conn.close()

        s_conn = get_sqlite_connection()
        try:
            c = s_conn.cursor()
            c.execute("SELECT username, password, created_at FROM accounts ORDER BY username ASC;")
            return [dict(r) for r in c.fetchall()]
        finally:
            s_conn.close()


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
    Lưu email vào CSDL. Ghi đồng thời vào PostgreSQL (hiển thị trên pgAdmin 4) và SQLite.
    Trả về ID của email vừa lưu.
    """
    if not created_at:
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    saved_id = -1
    with _db_lock:
        # 1. Lưu vào PostgreSQL (Dành cho pgAdmin 4)
        pg_conn = get_pg_connection()
        if pg_conn:
            try:
                c = pg_conn.cursor()
                c.execute("""
                    INSERT INTO emails (sender, recipient, subject, content, created_at, delivery_type, status, status_message, file_path)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id;
                """, (sender, recipient, subject, content, created_at, delivery_type, status, status_message, file_path))
                saved_id = c.fetchone()[0]
                pg_conn.commit()
                print(f"[POSTGRES] Đã lưu email #{saved_id} vào PostgreSQL thành công (sẵn sàng hiển thị trên pgAdmin 4)!")
            except Exception as e:
                print(f"[POSTGRES ERROR] save_email: {e}")
            finally:
                pg_conn.close()

        # 2. Luôn lưu vào SQLite để đảm bảo đồng bộ
        s_conn = get_sqlite_connection()
        try:
            c = s_conn.cursor()
            c.execute("""
                INSERT INTO emails (sender, recipient, subject, content, created_at, delivery_type, status, status_message, file_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (sender, recipient, subject, content, created_at, delivery_type, status, status_message, file_path))
            s_conn.commit()
            if saved_id == -1:
                saved_id = c.lastrowid
        except Exception as e:
            print(f"[SQLITE ERROR] save_email: {e}")
        finally:
            s_conn.close()

    return saved_id


def get_emails(
    limit: int = 200,
    search_query: str = "",
    delivery_filter: str = "",
    status_filter: str = ""
) -> List[dict]:
    """Lấy danh sách email (ưu tiên PostgreSQL, fallback SQLite)."""
    with _db_lock:
        pg_conn = get_pg_connection()
        if pg_conn:
            try:
                c = pg_conn.cursor(cursor_factory=RealDictCursor)
                query = "SELECT id, sender, recipient, subject, content, to_char(created_at, 'YYYY-MM-DD HH24:MI:SS') as created_at, delivery_type, status, status_message, file_path FROM emails WHERE 1=1"
                params = []
                if delivery_filter and delivery_filter != "TẤT CẢ":
                    query += " AND delivery_type = %s"
                    params.append(delivery_filter)
                if status_filter and status_filter != "TẤT CẢ":
                    query += " AND status = %s"
                    params.append(status_filter)
                if search_query:
                    like_term = f"%{search_query.strip()}%"
                    query += " AND (sender ILIKE %s OR recipient ILIKE %s OR subject ILIKE %s OR content ILIKE %s)"
                    params.extend([like_term, like_term, like_term, like_term])
                query += " ORDER BY id DESC LIMIT %s"
                params.append(limit)
                c.execute(query, params)
                return [dict(r) for r in c.fetchall()]
            except Exception as e:
                print(f"[POSTGRES ERROR] get_emails: {e}")
            finally:
                pg_conn.close()

        s_conn = get_sqlite_connection()
        try:
            c = s_conn.cursor()
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
            c.execute(query, params)
            return [dict(r) for r in c.fetchall()]
        finally:
            s_conn.close()


def get_email_by_id(email_id: int) -> Optional[dict]:
    """Lấy chi tiết 1 email theo ID."""
    with _db_lock:
        pg_conn = get_pg_connection()
        if pg_conn:
            try:
                c = pg_conn.cursor(cursor_factory=RealDictCursor)
                c.execute("SELECT id, sender, recipient, subject, content, to_char(created_at, 'YYYY-MM-DD HH24:MI:SS') as created_at, delivery_type, status, status_message, file_path FROM emails WHERE id = %s;", (email_id,))
                row = c.fetchone()
                if row:
                    return dict(row)
            except Exception as e:
                print(f"[POSTGRES ERROR] get_email_by_id: {e}")
            finally:
                pg_conn.close()

        s_conn = get_sqlite_connection()
        try:
            c = s_conn.cursor()
            c.execute("SELECT * FROM emails WHERE id = ?", (email_id,))
            row = c.fetchone()
            return dict(row) if row else None
        finally:
            s_conn.close()


def get_total_email_count() -> int:
    """Đếm tổng số email đã lưu trong CSDL."""
    with _db_lock:
        pg_conn = get_pg_connection()
        if pg_conn:
            try:
                c = pg_conn.cursor()
                c.execute("SELECT COUNT(*) FROM emails;")
                return c.fetchone()[0]
            except Exception:
                pass
            finally:
                pg_conn.close()

        s_conn = get_sqlite_connection()
        try:
            c = s_conn.cursor()
            c.execute("SELECT COUNT(*) FROM emails;")
            row = c.fetchone()
            return row[0] if row else 0
        finally:
            s_conn.close()


def delete_email(email_id: int) -> bool:
    """Xóa 1 bản ghi email trong CSDL."""
    with _db_lock:
        pg_conn = get_pg_connection()
        if pg_conn:
            try:
                c = pg_conn.cursor()
                c.execute("DELETE FROM emails WHERE id = %s;", (email_id,))
                pg_conn.commit()
            except Exception as e:
                print(f"[POSTGRES ERROR] delete_email: {e}")
            finally:
                pg_conn.close()

        s_conn = get_sqlite_connection()
        try:
            c = s_conn.cursor()
            c.execute("DELETE FROM emails WHERE id = ?", (email_id,))
            s_conn.commit()
            return True
        except Exception:
            return False
        finally:
            s_conn.close()
