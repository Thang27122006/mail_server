import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import json
import queue
import shutil
import socket
import subprocess
import threading
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk

import server
import db_manager
import smtp_service
from common import (
    DEFAULT_HOST,
    DEFAULT_SERVER_HOST,
    DEFAULT_PORT,
    WELCOME_EMAIL_CONTENT,
    WELCOME_EMAIL_FILENAME,
    get_lan_ip,
)


class MailServerGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Python Mail Server Dashboard - Trung Tâm Quản Trị Máy Chủ Mail")
        self.root.geometry("1060x720")
        self.root.minsize(920, 600)

        # Trạng thái server & hàng đợi xử lý sự kiện đa luồng
        self.controller = None
        self.is_running = False
        self.msg_queue = queue.Queue()
        self.auto_scroll_var = tk.BooleanVar(value=True)

        # Cấu hình giao diện
        self.setup_styles()
        self.create_header()
        self.create_kpi_dashboard()
        self.create_tabs()

        # Đăng ký nhận log & sự kiện từ server core
        server.set_log_callback(self.on_server_log)
        server.set_client_callback(self.on_client_count_changed)

        # Lắng nghe hàng đợi định kỳ để cập nhật giao diện an toàn
        self.root.after(100, self.process_queue)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Cập nhật thống kê ban đầu
        self.update_storage_stats()
        self.refresh_accounts_list()

    # =========================================================================
    # STYLES & GIAO DIỆN CHÍNH
    # =========================================================================
    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        # Màu sắc chủ đạo
        self.COLOR_BG = "#f4f6f9"
        self.COLOR_PRIMARY = "#1e3d59"
        self.COLOR_ACCENT = "#17b978"
        self.COLOR_DANGER = "#e74c3c"
        self.COLOR_SUCCESS = "#27ae60"
        self.COLOR_WARNING = "#f39c12"

        self.root.configure(bg=self.COLOR_BG)

        style.configure("TFrame", background=self.COLOR_BG)
        style.configure("TLabelframe", background=self.COLOR_BG, font=("Segoe UI", 10, "bold"))
        style.configure("TLabelframe.Label", background=self.COLOR_BG, foreground=self.COLOR_PRIMARY, font=("Segoe UI", 10, "bold"))
        style.configure("TLabel", background=self.COLOR_BG, font=("Segoe UI", 10))

        # Nút bấm
        style.configure("TButton", font=("Segoe UI", 9, "bold"), padding=6)
        style.configure("Start.TButton", foreground="white", background=self.COLOR_SUCCESS)
        style.map("Start.TButton", background=[("active", "#219150"), ("disabled", "#95a5a6")])

        style.configure("Stop.TButton", foreground="white", background=self.COLOR_DANGER)
        style.map("Stop.TButton", background=[("active", "#c0392b"), ("disabled", "#95a5a6")])

        style.configure("Action.TButton", foreground="white", background=self.COLOR_PRIMARY)
        style.map("Action.TButton", background=[("active", "#162e43")])

        # Treeview
        style.configure("Treeview", font=("Segoe UI", 9), rowheight=24)
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), foreground=self.COLOR_PRIMARY)

    def create_header(self):
        """Khung điều khiển Server (Host, Port, Start, Stop, Status)."""
        header_frame = tk.Frame(self.root, bg="#ffffff", bd=1, relief=tk.SOLID, padx=12, pady=10)
        header_frame.pack(fill=tk.X, padx=10, pady=(10, 6))

        # Tiêu đề & Logo
        title_box = tk.Frame(header_frame, bg="#ffffff")
        title_box.pack(side=tk.LEFT)

        lbl_icon = tk.Label(title_box, text="📬", font=("Segoe UI Emoji", 22), bg="#ffffff")
        lbl_icon.pack(side=tk.LEFT, padx=(0, 8))

        title_inner = tk.Frame(title_box, bg="#ffffff")
        title_inner.pack(side=tk.LEFT)
        tk.Label(title_inner, text="HỆ THỐNG QUẢN TRỊ MAIL SERVER", font=("Segoe UI", 13, "bold"), fg=self.COLOR_PRIMARY, bg="#ffffff").pack(anchor=tk.W)
        tk.Label(title_inner, text="Giao thức UDP Socket | Quản lý Hộp thư & Kết nối Real-time", font=("Segoe UI", 9), fg="#666666", bg="#ffffff").pack(anchor=tk.W)

        # Cấu hình Host / Port & Nút Bắt đầu / Dừng
        ctrl_box = tk.Frame(header_frame, bg="#ffffff")
        ctrl_box.pack(side=tk.RIGHT)

        tk.Label(ctrl_box, text="Host:", font=("Segoe UI", 9, "bold"), bg="#ffffff").pack(side=tk.LEFT, padx=(10, 3))
        self.entry_host = ttk.Entry(ctrl_box, width=12, font=("Segoe UI", 9))
        self.entry_host.insert(0, DEFAULT_SERVER_HOST)
        self.entry_host.pack(side=tk.LEFT, padx=(0, 8))

        tk.Label(ctrl_box, text="Port:", font=("Segoe UI", 9, "bold"), bg="#ffffff").pack(side=tk.LEFT, padx=(0, 3))
        self.entry_port = ttk.Entry(ctrl_box, width=6, font=("Segoe UI", 9))
        self.entry_port.insert(0, str(DEFAULT_PORT))
        self.entry_port.pack(side=tk.LEFT, padx=(0, 12))

        self.btn_start = ttk.Button(ctrl_box, text="▶ Khởi Động Server", style="Start.TButton", command=self.action_start_server)
        self.btn_start.pack(side=tk.LEFT, padx=4)

        self.btn_stop = ttk.Button(ctrl_box, text="⏹ Dừng Server", style="Stop.TButton", command=self.action_stop_server, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=4)

        self.btn_open_client = ttk.Button(ctrl_box, text="👤 Mở Client GUI", style="Action.TButton", command=self.open_client_gui)
        self.btn_open_client.pack(side=tk.LEFT, padx=4)

    def open_client_gui(self):
        """Khởi chạy một cửa sổ Client GUI mới độc lập."""
        client_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "client_gui.py")
        try:
            subprocess.Popen([sys.executable, client_script])
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể mở Client GUI: {e}")

    def create_kpi_dashboard(self):
        """Khung thẻ thống kê nhanh (KPI Cards)."""
        kpi_frame = tk.Frame(self.root, bg=self.COLOR_BG)
        kpi_frame.pack(fill=tk.X, padx=10, pady=4)

        # Card 1: Trạng thái Server
        self.card_status_frame, self.lbl_card_status_val = self._create_card(
            kpi_frame, "TRẠNG THÁI SERVER", "ĐANG DỪNG", "#e74c3c", "●"
        )
        self.card_status_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)

        # Card 2: Tài khoản
        self.card_accounts_frame, self.lbl_card_accounts_val = self._create_card(
            kpi_frame, "TỔNG TÀI KHOẢN", "0 Users", "#2980b9", "👥"
        )
        self.card_accounts_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)

        # Card 3: Tổng Email
        self.card_emails_frame, self.lbl_card_emails_val = self._create_card(
            kpi_frame, "TỔNG SỐ EMAIL LƯU", "0 Files", "#8e44ad", "✉️"
        )
        self.card_emails_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)

        # Card 4: Clients đang kết nối
        self.card_clients_frame, self.lbl_card_clients_val = self._create_card(
            kpi_frame, "CLIENTS ONLINE", "0 Đang nối", "#16a085", "🔌"
        )
        self.card_clients_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)

    def _create_card(self, parent, title: str, default_val: str, accent_color: str, icon: str):
        card = tk.Frame(parent, bg="#ffffff", bd=1, relief=tk.SOLID, padx=10, pady=8)

        top_line = tk.Frame(card, bg="#ffffff")
        top_line.pack(fill=tk.X)
        tk.Label(top_line, text=icon, font=("Segoe UI", 12), fg=accent_color, bg="#ffffff").pack(side=tk.LEFT)
        tk.Label(top_line, text=f" {title}", font=("Segoe UI", 8, "bold"), fg="#7f8c8d", bg="#ffffff").pack(side=tk.LEFT)

        lbl_val = tk.Label(card, text=default_val, font=("Segoe UI", 13, "bold"), fg=accent_color, bg="#ffffff")
        lbl_val.pack(anchor=tk.W, pady=(4, 0))

        return card, lbl_val

    def create_tabs(self):
        """Tạo các Tab chính của ứng dụng."""
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(6, 10))

        # Tab 1: Live Logs
        self.tab_logs = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(self.tab_logs, text="📜 Nhật Ký Hoạt Động (Live Logs)")
        self.setup_tab_logs()

        # Tab 2: Quản lý Thư mục & Tài khoản
        self.tab_storage = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(self.tab_storage, text="📁 Quản Lý Tài Khoản & Hộp Thư")
        self.setup_tab_storage()

        # Tab 3: Cơ Sở Dữ Liệu (Database)
        self.tab_database = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(self.tab_database, text="🗄️ Cơ Sở Dữ Liệu (Database)")
        self.setup_tab_database()

        # Tab 4: Cấu Hình Gmail (SMTP)
        self.tab_smtp = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(self.tab_smtp, text="⚙️ Cấu Hình Gmail (SMTP)")
        self.setup_tab_smtp()

        # Tab 5: Clients Online
        self.tab_clients = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(self.tab_clients, text="🔌 Kết Nối Trực Tuyến")
        self.setup_tab_clients()

        # Tab 6: Giao thức & Hướng dẫn
        self.tab_info = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(self.tab_info, text="ℹ️ Hướng Dẫn & Giao Thức")
        self.setup_tab_info()

    # =========================================================================
    # TAB 1: NHẬT KÝ HOẠT ĐỘNG (LIVE LOGS)
    # =========================================================================
    def setup_tab_logs(self):
        # Thanh công cụ trên khung log
        bar = tk.Frame(self.tab_logs, bg=self.COLOR_BG)
        bar.pack(fill=tk.X, pady=(0, 4))

        tk.Label(bar, text="Nhật ký các gói tin & luồng kết nối UDP:", font=("Segoe UI", 9, "italic"), fg="#555555").pack(side=tk.LEFT)

        btn_box = tk.Frame(bar, bg=self.COLOR_BG)
        btn_box.pack(side=tk.RIGHT)

        chk_scroll = ttk.Checkbutton(btn_box, text="Tự động cuộn", variable=self.auto_scroll_var)
        chk_scroll.pack(side=tk.LEFT, padx=6)

        btn_clear = ttk.Button(btn_box, text="Xóa Log", command=self.clear_logs)
        btn_clear.pack(side=tk.LEFT, padx=4)

        btn_export = ttk.Button(btn_box, text="Lưu File Log...", command=self.export_logs)
        btn_export.pack(side=tk.LEFT, padx=4)

        # Khung hiển thị log phong cách Dark Console
        self.txt_logs = scrolledtext.ScrolledText(
            self.tab_logs,
            wrap=tk.WORD,
            bg="#181825",
            fg="#cdd6f4",
            insertbackground="#ffffff",
            font=("Consolas", 10),
            padx=8,
            pady=8
        )
        self.txt_logs.pack(fill=tk.BOTH, expand=True)

        # Cấu hình màu sắc cho các loại thẻ log
        self.txt_logs.tag_config("TAG_TIME", foreground="#6c7086")
        self.txt_logs.tag_config("TAG_CONNECTED", foreground="#89b4fa", font=("Consolas", 10, "bold"))
        self.txt_logs.tag_config("TAG_DISCONNECTED", foreground="#fab387")
        self.txt_logs.tag_config("TAG_SUCCESS", foreground="#a6e3a1", font=("Consolas", 10, "bold"))
        self.txt_logs.tag_config("TAG_ERROR", foreground="#f38ba8", font=("Consolas", 10, "bold"))
        self.txt_logs.tag_config("TAG_EMAIL", foreground="#cba6f7")
        self.txt_logs.tag_config("TAG_HEADER", foreground="#f9e2af", font=("Consolas", 10, "bold"))

        self.append_log("[INFO] Hệ thống Mail Server GUI sẵn sàng. Hãy bấm 'Khởi Động Server' để bắt đầu.")

    def append_log(self, text: str):
        """Thêm dòng log kèm định dạng màu sắc."""
        tag = None
        if "[CONNECTED]" in text:
            tag = "TAG_CONNECTED"
        elif "[DISCONNECTED]" in text or "[CLOSED]" in text or "[STOPPED]" in text:
            tag = "TAG_DISCONNECTED"
        elif "[SUCCESS]" in text or "ĐANG CHẠY" in text:
            tag = "TAG_SUCCESS"
        elif "[ERROR]" in text or "[FATAL" in text or "[FAILED]" in text:
            tag = "TAG_ERROR"
        elif "[READ EMAIL]" in text or "[SEND SUCCESS]" in text:
            tag = "TAG_EMAIL"
        elif "=" * 10 in text:
            tag = "TAG_HEADER"

        self.txt_logs.insert(tk.END, text + "\n", tag)
        if self.auto_scroll_var.get():
            self.txt_logs.see(tk.END)

    def clear_logs(self):
        self.txt_logs.delete("1.0", tk.END)

    def export_logs(self):
        content = self.txt_logs.get("1.0", tk.END).strip()
        if not content:
            messagebox.showinfo("Thông báo", "Nhật ký hiện đang trống!")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text file", "*.txt"), ("All Files", "*.*")],
            initialfile=f"server_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                messagebox.showinfo("Thành công", f"Đã lưu nhật ký ra file:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể lưu file: {e}")

    def setup_tab_storage(self):
        # Thanh điều hướng phía trên
        top_bar = tk.Frame(self.tab_storage, bg=self.COLOR_BG)
        top_bar.pack(fill=tk.X, pady=(0, 6))

        tk.Label(
            top_bar,
            text=f"📂 Thư mục lưu trữ: {server.STORAGE_DIR}",
            font=("Segoe UI", 9, "bold"),
            fg=self.COLOR_PRIMARY
        ).pack(side=tk.LEFT)

        btn_box = tk.Frame(top_bar, bg=self.COLOR_BG)
        btn_box.pack(side=tk.RIGHT)

        ttk.Button(btn_box, text="🔄 Làm Mới Dữ Liệu", command=self.refresh_accounts_list).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_box, text="📂 Mở Trong File Explorer", command=self.open_storage_explorer).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_box, text="➕ Tạo Tài Khoản Mới", command=self.create_account_dialog).pack(side=tk.LEFT, padx=4)

        # PanedWindow chia 2 cột: Cột trái (Tài khoản) - Cột phải (Files & Nội dung)
        paned = ttk.PanedWindow(self.tab_storage, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # CỘT TRÁI: Danh sách tài khoản
        left_frame = ttk.LabelFrame(paned, text=" Danh Sách Tài Khoản ", padding=6)
        paned.add(left_frame, weight=1)

        cols = ("username", "email_count", "created_at")
        self.tree_accounts = ttk.Treeview(left_frame, columns=cols, show="headings", selectmode="browse")
        self.tree_accounts.heading("username", text="Tên tài khoản")
        self.tree_accounts.heading("email_count", text="Số thư")
        self.tree_accounts.heading("created_at", text="Ngày tạo")

        self.tree_accounts.column("username", width=120)
        self.tree_accounts.column("email_count", width=60, anchor=tk.CENTER)
        self.tree_accounts.column("created_at", width=130, anchor=tk.CENTER)

        tree_scroll_y = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.tree_accounts.yview)
        self.tree_accounts.configure(yscrollcommand=tree_scroll_y.set)

        self.tree_accounts.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree_accounts.bind("<<TreeviewSelect>>", self.on_account_selected)

        # Nút xóa tài khoản dưới danh sách
        acc_btn_frame = tk.Frame(left_frame, bg=self.COLOR_BG)
        acc_btn_frame.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(acc_btn_frame, text="🗑️ Xóa Tài Khoản Này", command=self.delete_selected_account).pack(side=tk.RIGHT)

        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=2)

        right_paned = ttk.PanedWindow(right_frame, orient=tk.VERTICAL)
        right_paned.pack(fill=tk.BOTH, expand=True)

        # Danh sách file
        box_files = ttk.LabelFrame(right_paned, text=" Các file trong thư mục tài khoản ", padding=6)
        right_paned.add(box_files, weight=1)

        file_cols = ("filename", "size", "modified")
        self.tree_files = ttk.Treeview(box_files, columns=file_cols, show="headings", selectmode="browse")
        self.tree_files.heading("filename", text="Tên File Email")
        self.tree_files.heading("size", text="Kích thước")
        self.tree_files.heading("modified", text="Thời gian sửa đổi")

        self.tree_files.column("filename", width=220)
        self.tree_files.column("size", width=70, anchor=tk.E)
        self.tree_files.column("modified", width=140, anchor=tk.CENTER)

        file_scroll_y = ttk.Scrollbar(box_files, orient=tk.VERTICAL, command=self.tree_files.yview)
        self.tree_files.configure(yscrollcommand=file_scroll_y.set)

        self.tree_files.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        file_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree_files.bind("<<TreeviewSelect>>", self.on_file_selected)

        # Nội dung file
        box_preview = ttk.LabelFrame(right_paned, text=" Xem Trước Nội Dung Email ", padding=6)
        right_paned.add(box_preview, weight=2)

        self.txt_preview = scrolledtext.ScrolledText(
            box_preview, wrap=tk.WORD, font=("Consolas", 10), bg="#ffffff"
        )
        self.txt_preview.pack(fill=tk.BOTH, expand=True)

    def refresh_accounts_list(self):
        """Cập nhật lại danh sách tài khoản từ file và thư mục."""
        # Xóa các dòng cũ
        for item in self.tree_accounts.get_children():
            self.tree_accounts.delete(item)

        accounts = server.load_accounts()
        server.init_storage()

        # Duyệt thư mục và file accounts.json
        user_dirs = set()
        if os.path.exists(server.STORAGE_DIR):
            for entry in os.listdir(server.STORAGE_DIR):
                full_p = os.path.join(server.STORAGE_DIR, entry)
                if os.path.isdir(full_p) and entry != "__pycache__":
                    user_dirs.add(entry)

        all_users = sorted(set(list(accounts.keys()) + list(user_dirs)))

        total_emails = 0
        for u in all_users:
            u_dir = os.path.join(server.STORAGE_DIR, u)
            email_count = 0
            if os.path.exists(u_dir):
                email_count = len([f for f in os.listdir(u_dir) if os.path.isfile(os.path.join(u_dir, f))])
            total_emails += email_count

            created_at = accounts.get(u, {}).get("created_at", "N/A")
            self.tree_accounts.insert("", tk.END, values=(u, email_count, created_at))

        # Cập nhật số liệu trên thẻ KPI
        total_db_emails = db_manager.get_total_email_count()
        self.lbl_card_accounts_val.config(text=f"{len(all_users)} Users")
        self.lbl_card_emails_val.config(text=f"{total_db_emails} DB ({total_emails} Files)")

    def on_account_selected(self, event):
        """Khi click chọn một tài khoản ở bảng bên trái."""
        selected = self.tree_accounts.selection()
        if not selected:
            return

        item = self.tree_accounts.item(selected[0])
        username = item["values"][0]

        # Xóa danh sách file cũ
        for f_item in self.tree_files.get_children():
            self.tree_files.delete(f_item)
        self.txt_preview.delete("1.0", tk.END)

        user_dir = os.path.join(server.STORAGE_DIR, str(username))
        if not os.path.exists(user_dir):
            return

        files = sorted(os.listdir(user_dir))
        for fname in files:
            fpath = os.path.join(user_dir, fname)
            if os.path.isfile(fpath):
                size = f"{os.path.getsize(fpath)} B"
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%Y-%m-%d %H:%M:%S")
                self.tree_files.insert("", tk.END, values=(fname, size, mtime))

    def on_file_selected(self, event):
        """Khi click chọn một file email ở bảng bên phải."""
        acc_sel = self.tree_accounts.selection()
        file_sel = self.tree_files.selection()
        if not acc_sel or not file_sel:
            return

        username = str(self.tree_accounts.item(acc_sel[0])["values"][0])
        filename = str(self.tree_files.item(file_sel[0])["values"][0])

        filepath = os.path.join(server.STORAGE_DIR, username, filename)
        self.txt_preview.delete("1.0", tk.END)

        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                self.txt_preview.insert(tk.END, content)
            except Exception as e:
                self.txt_preview.insert(tk.END, f"[Lỗi đọc file]: {e}")

    def open_storage_explorer(self):
        """Mở thư mục server_storage trong File Explorer."""
        server.init_storage()
        try:
            if sys.platform == "win32":
                os.startfile(server.STORAGE_DIR)
            else:
                subprocess.Popen(["xdg-open", server.STORAGE_DIR])
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể mở thư mục: {e}")

    def create_account_dialog(self):
        """Hộp thoại tạo tài khoản thủ công từ Server GUI."""
        username = simpledialog.askstring("Tạo Tài Khoản", "Nhập tên tài khoản mới:")
        if not username or not username.strip():
            return
        username = username.strip()

        password = simpledialog.askstring("Tạo Tài Khoản", f"Nhập mật khẩu cho '{username}':", show="*")
        if not password or not password.strip():
            messagebox.showwarning("Cảnh báo", "Mật khẩu không được để trống!")
            return
        password = password.strip()

        accounts = server.load_accounts()
        if username in accounts:
            messagebox.showerror("Lỗi", f"Tài khoản '{username}' đã tồn tại!")
            return

        # Thực hiện tạo thư mục và file new_email.txt đúng đề bài
        user_dir = os.path.join(server.STORAGE_DIR, username)
        try:
            os.makedirs(user_dir, exist_ok=True)
            welcome_file_path = os.path.join(user_dir, WELCOME_EMAIL_FILENAME)
            with open(welcome_file_path, "w", encoding="utf-8") as f:
                f.write(WELCOME_EMAIL_CONTENT)

            accounts[username] = {
                "password": password,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            server.save_accounts(accounts)

            server.log(f"[ADMIN GUI] Đã tạo tài khoản '{username}' và {WELCOME_EMAIL_FILENAME}")
            messagebox.showinfo("Thành công", f"Đã tạo tài khoản '{username}' thành công!")
            self.refresh_accounts_list()
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể tạo tài khoản: {e}")

    def delete_selected_account(self):
        """Xóa tài khoản đang chọn cùng thư mục cá nhân trên server."""
        selected = self.tree_accounts.selection()
        if not selected:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn tài khoản cần xóa!")
            return

        username = str(self.tree_accounts.item(selected[0])["values"][0])
        confirm = messagebox.askyesno(
            "Xác nhận xóa",
            f"Bạn có chắc muốn xóa tài khoản '{username}' cùng toàn bộ email trong thư mục server?\nThao tác này không thể hoàn tác!"
        )
        if not confirm:
            return

        # Xóa khỏi accounts.json
        accounts = server.load_accounts()
        accounts.pop(username, None)
        server.save_accounts(accounts)

        # Xóa khỏi CSDL SQLite
        db_manager.delete_account(username)

        server.log(f"[ADMIN GUI] Đã xóa tài khoản '{username}' khỏi hệ thống.")
        self.refresh_accounts_list()
        self.refresh_database_table()
        self.tree_files.delete(*self.tree_files.get_children())
        self.txt_preview.delete("1.0", tk.END)

    # =========================================================================
    # TAB 3: CƠ SỞ DỮ LIỆU (DATABASE)
    # =========================================================================
    def setup_tab_database(self):
        """Khởi tạo Tab Cơ Sở Dữ Liệu (SQLite Database) hiển thị danh sách email lưu trữ."""
        top_bar = tk.Frame(self.tab_database, bg=self.COLOR_BG)
        top_bar.pack(fill=tk.X, pady=(0, 6))

        tk.Label(top_bar, text="Tìm kiếm:", font=("Segoe UI", 9, "bold"), bg=self.COLOR_BG).pack(side=tk.LEFT, padx=(4, 2))
        self.entry_db_search = ttk.Entry(top_bar, width=20)
        self.entry_db_search.pack(side=tk.LEFT, padx=4)
        self.entry_db_search.bind("<Return>", lambda e: self.refresh_database_table())

        tk.Label(top_bar, text="Hình thức:", font=("Segoe UI", 9, "bold"), bg=self.COLOR_BG).pack(side=tk.LEFT, padx=(6, 2))
        self.cbo_db_delivery = ttk.Combobox(top_bar, values=["TẤT CẢ", "LOCAL", "GMAIL"], state="readonly", width=8)
        self.cbo_db_delivery.set("TẤT CẢ")
        self.cbo_db_delivery.pack(side=tk.LEFT, padx=4)
        self.cbo_db_delivery.bind("<<ComboboxSelected>>", lambda e: self.refresh_database_table())

        tk.Label(top_bar, text="Trạng thái:", font=("Segoe UI", 9, "bold"), bg=self.COLOR_BG).pack(side=tk.LEFT, padx=(6, 2))
        self.cbo_db_status = ttk.Combobox(top_bar, values=["TẤT CẢ", "SUCCESS", "FAILED"], state="readonly", width=8)
        self.cbo_db_status.set("TẤT CẢ")
        self.cbo_db_status.pack(side=tk.LEFT, padx=4)
        self.cbo_db_status.bind("<<ComboboxSelected>>", lambda e: self.refresh_database_table())

        btn_search = ttk.Button(top_bar, text="🔍 Tìm", command=self.refresh_database_table)
        btn_search.pack(side=tk.LEFT, padx=3)

        btn_refresh = ttk.Button(top_bar, text="🔄 Làm Mới", command=self.refresh_database_table)
        btn_refresh.pack(side=tk.LEFT, padx=3)

        btn_del = ttk.Button(top_bar, text="🗑️ Xóa Bản Ghi", command=self.delete_selected_db_email)
        btn_del.pack(side=tk.RIGHT, padx=4)

        btn_view = ttk.Button(top_bar, text="📄 Xem Chi Tiết", command=self.view_selected_db_email)
        btn_view.pack(side=tk.RIGHT, padx=4)

        # Table container
        table_frame = ttk.Frame(self.tab_database)
        table_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("id", "created_at", "sender", "recipient", "subject", "delivery_type", "status", "status_msg")
        self.tree_database = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")
        self.tree_database.heading("id", text="# ID")
        self.tree_database.heading("created_at", text="Thời Gian")
        self.tree_database.heading("sender", text="Người Gửi")
        self.tree_database.heading("recipient", text="Người Nhận")
        self.tree_database.heading("subject", text="Tiêu Đề Email")
        self.tree_database.heading("delivery_type", text="Hình Thức")
        self.tree_database.heading("status", text="Trạng Thái")
        self.tree_database.heading("status_msg", text="Ghi Chú / Phản Hồi")

        self.tree_database.column("id", width=45, anchor=tk.CENTER)
        self.tree_database.column("created_at", width=135, anchor=tk.CENTER)
        self.tree_database.column("sender", width=110, anchor=tk.W)
        self.tree_database.column("recipient", width=160, anchor=tk.W)
        self.tree_database.column("subject", width=220, anchor=tk.W)
        self.tree_database.column("delivery_type", width=85, anchor=tk.CENTER)
        self.tree_database.column("status", width=85, anchor=tk.CENTER)
        self.tree_database.column("status_msg", width=200, anchor=tk.W)

        db_scroll_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree_database.yview)
        db_scroll_x = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.tree_database.xview)
        self.tree_database.configure(yscrollcommand=db_scroll_y.set, xscrollcommand=db_scroll_x.set)

        self.tree_database.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        db_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        db_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)

        self.tree_database.bind("<Double-1>", lambda e: self.view_selected_db_email())

        self.tree_database.tag_configure("TAG_SUCCESS", foreground="#1e7e34")
        self.tree_database.tag_configure("TAG_FAILED", foreground="#dc3545")
        self.tree_database.tag_configure("TAG_GMAIL", font=("Segoe UI", 9, "bold"))

        self.refresh_database_table()

    def refresh_database_table(self):
        """Tải dữ liệu từ SQLite Database và hiển thị lên bảng."""
        if not hasattr(self, "tree_database"):
            return
        for item in self.tree_database.get_children():
            self.tree_database.delete(item)

        search_q = self.entry_db_search.get().strip() if hasattr(self, "entry_db_search") else ""
        deliv = self.cbo_db_delivery.get() if hasattr(self, "cbo_db_delivery") else "TẤT CẢ"
        stat = self.cbo_db_status.get() if hasattr(self, "cbo_db_status") else "TẤT CẢ"

        records = db_manager.get_emails(
            limit=300,
            search_query=search_q,
            delivery_filter=deliv,
            status_filter=stat
        )

        for r in records:
            tag = "TAG_SUCCESS" if r["status"] == "SUCCESS" else "TAG_FAILED"
            tags = [tag]
            if r["delivery_type"] == "GMAIL":
                tags.append("TAG_GMAIL")

            self.tree_database.insert(
                "",
                tk.END,
                values=(
                    r["id"],
                    r["created_at"],
                    r["sender"],
                    r["recipient"],
                    r["subject"] or "(Không tiêu đề)",
                    r["delivery_type"],
                    r["status"],
                    r["status_message"] or r["file_path"] or ""
                ),
                tags=tuple(tags)
            )

    def view_selected_db_email(self):
        """Mở cửa sổ chi tiết email trong CSDL."""
        selected = self.tree_database.selection()
        if not selected:
            messagebox.showinfo("Thông báo", "Vui lòng chọn một email trong bảng để xem chi tiết!")
            return

        item = self.tree_database.item(selected[0])
        email_id = item["values"][0]
        record = db_manager.get_email_by_id(email_id)
        if not record:
            messagebox.showerror("Lỗi", "Không tìm thấy bản ghi email trong CSDL!")
            return

        win = tk.Toplevel(self.root)
        win.title(f"Chi Tiết Email #{record['id']} - CSDL Mail Server")
        win.geometry("640x560")
        win.minsize(500, 400)
        win.transient(self.root)

        meta_frame = ttk.LabelFrame(win, text=" Thông Tin Chi Tiết ", padding=10)
        meta_frame.pack(fill=tk.X, padx=10, pady=6)

        def add_meta_row(row_idx, label, val, color=None):
            lbl_t = tk.Label(meta_frame, text=label, font=("Segoe UI", 9, "bold"), fg="#555555")
            lbl_t.grid(row=row_idx, column=0, sticky=tk.W, padx=4, pady=2)
            lbl_c = tk.Label(meta_frame, text=str(val), font=("Segoe UI", 9), fg=color or "#222222")
            lbl_c.grid(row=row_idx, column=1, sticky=tk.W, padx=4, pady=2)

        add_meta_row(0, "ID Bản ghi:", record["id"])
        add_meta_row(1, "Thời gian:", record["created_at"])
        add_meta_row(2, "Người gửi (From):", record["sender"])
        add_meta_row(3, "Người nhận (To):", record["recipient"])
        add_meta_row(4, "Tiêu đề (Subject):", record["subject"])
        add_meta_row(5, "Hình thức gửi:", record["delivery_type"])
        status_color = "#1e7e34" if record["status"] == "SUCCESS" else "#dc3545"
        add_meta_row(6, "Trạng thái:", record["status"], status_color)
        if record.get("status_message"):
            add_meta_row(7, "Phản hồi/Ghi chú:", record["status_message"])
        if record.get("file_path"):
            add_meta_row(8, "Tên file lưu:", record["file_path"])

        content_frame = ttk.LabelFrame(win, text=" Nội Dung Email ", padding=10)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        txt_body = scrolledtext.ScrolledText(content_frame, wrap=tk.WORD, font=("Consolas", 10), bg="#fcfcfc")
        txt_body.pack(fill=tk.BOTH, expand=True)
        txt_body.insert(tk.END, record.get("content") or "(Nội dung trống)")
        txt_body.config(state=tk.DISABLED)

    def delete_selected_db_email(self):
        """Xóa bản ghi email được chọn trong CSDL."""
        selected = self.tree_database.selection()
        if not selected:
            messagebox.showinfo("Thông báo", "Vui lòng chọn email cần xóa!")
            return
        item = self.tree_database.item(selected[0])
        email_id = item["values"][0]
        if messagebox.askyesno("Xác nhận xóa", f"Bạn có chắc muốn xóa bản ghi email #{email_id} khỏi CSDL?"):
            db_manager.delete_email(email_id)
            self.refresh_database_table()
            self.refresh_accounts_list()

    # =========================================================================
    # TAB 4: CẤU HÌNH GMAIL SMTP
    # =========================================================================
    def setup_tab_smtp(self):
        """Khởi tạo Tab Cấu hình Gmail SMTP để gửi thư thực tế."""
        container = tk.Frame(self.tab_smtp, bg=self.COLOR_BG)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        # Card 1: Form cấu hình
        cfg_frame = ttk.LabelFrame(container, text=" Cấu Hình Tài Khoản Gmail Gửi Thư (SMTP) ", padding=10)
        cfg_frame.pack(fill=tk.X, pady=(0, 8))

        self.smtp_enabled_var = tk.BooleanVar(value=False)
        chk_enable = ttk.Checkbutton(
            cfg_frame,
            text=" Kích hoạt tính năng gửi thư thực tế qua Gmail (SMTP)",
            variable=self.smtp_enabled_var
        )
        chk_enable.grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 6))

        # Email gửi
        tk.Label(cfg_frame, text="Gmail Người Gửi (Sender Email):", font=("Segoe UI", 9, "bold")).grid(row=1, column=0, sticky=tk.W, pady=3)
        self.entry_smtp_email = ttk.Entry(cfg_frame, width=36, font=("Segoe UI", 9))
        self.entry_smtp_email.grid(row=1, column=1, sticky=tk.W, pady=3, padx=6)
        tk.Label(cfg_frame, text="(vd: your_email@gmail.com)", font=("Segoe UI", 8, "italic"), fg="#777777").grid(row=1, column=2, sticky=tk.W)

        # App Password
        tk.Label(cfg_frame, text="Mật Khẩu Ứng Dụng (App Password):", font=("Segoe UI", 9, "bold")).grid(row=2, column=0, sticky=tk.W, pady=3)
        pwd_box = tk.Frame(cfg_frame)
        pwd_box.grid(row=2, column=1, sticky=tk.W, pady=3, padx=6)
        self.entry_smtp_pwd = ttk.Entry(pwd_box, width=28, show="*", font=("Segoe UI", 9))
        self.entry_smtp_pwd.pack(side=tk.LEFT)
        self.show_pwd_var = False

        def toggle_pwd():
            self.show_pwd_var = not self.show_pwd_var
            self.entry_smtp_pwd.config(show="" if self.show_pwd_var else "*")
            btn_show_pwd.config(text="🙈 Ẩn" if self.show_pwd_var else "👁 Hiện")

        btn_show_pwd = ttk.Button(pwd_box, text="👁 Hiện", width=6, command=toggle_pwd)
        btn_show_pwd.pack(side=tk.LEFT, padx=4)
        tk.Label(cfg_frame, text="(16 chữ cái tạo từ Google Account)", font=("Segoe UI", 8, "italic"), fg="#777777").grid(row=2, column=2, sticky=tk.W)

        # Sender display name
        tk.Label(cfg_frame, text="Tên Hiển Thị Người Gửi:", font=("Segoe UI", 9, "bold")).grid(row=3, column=0, sticky=tk.W, pady=3)
        self.entry_smtp_name = ttk.Entry(cfg_frame, width=36, font=("Segoe UI", 9))
        self.entry_smtp_name.grid(row=3, column=1, sticky=tk.W, pady=3, padx=6)

        # SMTP Host
        tk.Label(cfg_frame, text="Máy Chủ SMTP (Host):", font=("Segoe UI", 9, "bold")).grid(row=4, column=0, sticky=tk.W, pady=3)
        self.entry_smtp_host = ttk.Entry(cfg_frame, width=36, font=("Segoe UI", 9))
        self.entry_smtp_host.grid(row=4, column=1, sticky=tk.W, pady=3, padx=6)

        # SMTP Port
        tk.Label(cfg_frame, text="Cổng Kết Nối (Port):", font=("Segoe UI", 9, "bold")).grid(row=5, column=0, sticky=tk.W, pady=3)
        self.entry_smtp_port = ttk.Entry(cfg_frame, width=12, font=("Segoe UI", 9))
        self.entry_smtp_port.grid(row=5, column=1, sticky=tk.W, pady=3, padx=6)

        self.smtp_tls_var = tk.BooleanVar(value=True)
        chk_tls = ttk.Checkbutton(cfg_frame, text="Sử dụng mã hóa STARTTLS (bảo mật cổng 587)", variable=self.smtp_tls_var)
        chk_tls.grid(row=6, column=0, columnspan=2, sticky=tk.W, pady=3)

        # Nút bấm hành động
        btn_action_frame = tk.Frame(cfg_frame)
        btn_action_frame.grid(row=7, column=0, columnspan=3, sticky=tk.W, pady=(8, 2))

        self.btn_save_smtp = ttk.Button(btn_action_frame, text="💾 Lưu Cấu Hình", command=self.save_smtp_settings)
        self.btn_save_smtp.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_test_smtp = ttk.Button(btn_action_frame, text="🧪 Kiểm Tra Kết Nối Gmail", command=self.test_smtp_settings_async)
        self.btn_test_smtp.pack(side=tk.LEFT, padx=4)

        self.lbl_smtp_test_status = tk.Label(btn_action_frame, text="", font=("Segoe UI", 9, "italic"))
        self.lbl_smtp_test_status.pack(side=tk.LEFT, padx=10)

        # Card 2: Hướng dẫn lấy Google App Password
        guide_frame = ttk.LabelFrame(container, text=" 📖 Hướng Dẫn Chi Tiết Lấy Mật Khẩu Ứng Dụng (App Password) Của Google ", padding=10)
        guide_frame.pack(fill=tk.BOTH, expand=True)

        guide_text = (
            "📌 ĐỂ GỬI ĐƯỢC THƯ THỰC TẾ VÀO GMAIL, BẠN CẦN LẤY 'MẬT KHẨU ỨNG DỤNG' THEO CÁC BƯỚC SAU:\n\n"
            "  1. Đăng nhập vào tài khoản Google tại: https://myaccount.google.com\n"
            "  2. Chọn mục 'Bảo mật' (Security) ở cột bên trái.\n"
            "  3. Trong phần 'Cách bạn đăng nhập vào Google', hãy bật 'Xác minh 2 bước' (2-Step Verification) nếu chưa bật.\n"
            "  4. Sau khi bật Xác minh 2 bước, truy cập trực tiếp đường link tạo mật khẩu ứng dụng:\n"
            "         👉 https://myaccount.google.com/apppasswords\n"
            "  5. Đặt tên ứng dụng (Ví dụ: 'Python Mail Server') rồi nhấn 'Tạo' (Create).\n"
            "  6. Google sẽ hiện ra một mật khẩu gồm 16 chữ cái (dạng: abcd efgh ijkl mnop).\n"
            "  7. Sao chép 16 ký tự đó, quay lại màn hình này dán vào ô 'Mật Khẩu Ứng Dụng (App Password)'.\n"
            "  8. Tích vào ô 'Kích hoạt tính năng gửi thư thực tế qua Gmail', nhấn 'Lưu Cấu Hình' và bấm 'Kiểm Tra Kết Nối Gmail'.\n\n"
            "✨ SAU KHI CẤU HÌNH XONG:\n"
            "  - Từ Client GUI hoặc CLI, khi bạn soạn thư và nhập người nhận là địa chỉ email (ví dụ: 'nguoinhan@gmail.com'),\n"
            "    Server sẽ tự động gửi thư thực tế đến đúng hòm thư Gmail đó,\n"
            "    đồng thời lưu toàn bộ email và trạng thái gửi vào Cơ sở dữ liệu SQLite!"
        )
        txt_guide = scrolledtext.ScrolledText(guide_frame, wrap=tk.WORD, font=("Segoe UI", 9), bg="#f8f9fa", fg="#333333")
        txt_guide.pack(fill=tk.BOTH, expand=True)
        txt_guide.insert(tk.END, guide_text)
        txt_guide.config(state=tk.DISABLED)

        self.load_smtp_to_gui()

    def load_smtp_to_gui(self):
        """Đọc file cấu hình SMTP và điền vào các ô trên giao diện."""
        cfg = smtp_service.load_smtp_config()
        self.smtp_enabled_var.set(cfg.get("enabled", False))
        self.entry_smtp_email.delete(0, tk.END)
        self.entry_smtp_email.insert(0, cfg.get("sender_email", ""))
        self.entry_smtp_pwd.delete(0, tk.END)
        self.entry_smtp_pwd.insert(0, cfg.get("sender_password", ""))
        self.entry_smtp_name.delete(0, tk.END)
        self.entry_smtp_name.insert(0, cfg.get("sender_name", "Python Mail Server"))
        self.entry_smtp_host.delete(0, tk.END)
        self.entry_smtp_host.insert(0, cfg.get("smtp_host", "smtp.gmail.com"))
        self.entry_smtp_port.delete(0, tk.END)
        self.entry_smtp_port.insert(0, str(cfg.get("smtp_port", 587)))
        self.smtp_tls_var.set(cfg.get("use_tls", True))

    def save_smtp_settings(self):
        """Lưu các cài đặt SMTP vào smtp_config.json."""
        sender_email = self.entry_smtp_email.get().strip()
        sender_pwd = self.entry_smtp_pwd.get().strip()
        smtp_host = self.entry_smtp_host.get().strip() or "smtp.gmail.com"
        port_str = self.entry_smtp_port.get().strip() or "587"
        sender_name = self.entry_smtp_name.get().strip() or "Python Mail Server"

        try:
            smtp_port = int(port_str)
        except ValueError:
            messagebox.showerror("Lỗi", "Cổng kết nối SMTP phải là số nguyên (mặc định 587)!")
            return

        cfg = {
            "enabled": self.smtp_enabled_var.get(),
            "smtp_host": smtp_host,
            "smtp_port": smtp_port,
            "use_tls": self.smtp_tls_var.get(),
            "sender_email": sender_email,
            "sender_password": sender_pwd,
            "sender_name": sender_name
        }
        smtp_service.save_smtp_config(cfg)
        server.log(f"[CONFIG] Đã cập nhật cấu hình Gmail SMTP (Bật: {cfg['enabled']}, Email: {sender_email})")
        messagebox.showinfo("Thành công", "Đã lưu cấu hình Gmail SMTP thành công!")

    def test_smtp_settings_async(self):
        """Chạy kiểm tra kết nối SMTP trên luồng nền để không gây đơ GUI."""
        sender_email = self.entry_smtp_email.get().strip()
        sender_pwd = self.entry_smtp_pwd.get().strip()
        host = self.entry_smtp_host.get().strip() or "smtp.gmail.com"
        port_str = self.entry_smtp_port.get().strip() or "587"
        use_tls = self.smtp_tls_var.get()

        if not sender_email or not sender_pwd:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập Email người gửi và Mật khẩu ứng dụng trước khi kiểm tra!")
            return

        try:
            port = int(port_str)
        except ValueError:
            messagebox.showerror("Lỗi", "Cổng SMTP không hợp lệ!")
            return

        self.btn_test_smtp.config(state=tk.DISABLED)
        self.lbl_smtp_test_status.config(text="⏳ Đang kiểm tra kết nối với Google SMTP...", fg="#2980b9")

        def run_test():
            ok, msg = smtp_service.test_smtp_connection(
                host=host,
                port=port,
                sender_email=sender_email,
                sender_password=sender_pwd,
                use_tls=use_tls
            )

            def done():
                self.btn_test_smtp.config(state=tk.NORMAL)
                if ok:
                    self.lbl_smtp_test_status.config(text="✅ Kết nối thành công!", fg="#27ae60")
                    messagebox.showinfo("Kết Quả Kiểm Tra", msg)
                else:
                    self.lbl_smtp_test_status.config(text="❌ Thất bại!", fg="#e74c3c")
                    messagebox.showerror("Kết Quả Kiểm Tra", msg)

            self.root.after(0, done)

        threading.Thread(target=run_test, daemon=True).start()

    # =========================================================================
    # TAB 5: CLIENTS ONLINE
    # =========================================================================
    def setup_tab_clients(self):
        top_bar = tk.Frame(self.tab_clients, bg=self.COLOR_BG)
        top_bar.pack(fill=tk.X, pady=(0, 6))

        tk.Label(
            top_bar,
            text="Danh sách các Client UDP Socket đang duy trì kết nối tới Mail Server:",
            font=("Segoe UI", 9, "italic"),
            fg="#555555"
        ).pack(side=tk.LEFT)

        ttk.Button(top_bar, text="🔄 Cập Nhật", command=self.refresh_clients_table).pack(side=tk.RIGHT)

        cols = ("ip_port", "user", "status")
        self.tree_clients = ttk.Treeview(self.tab_clients, columns=cols, show="headings")
        self.tree_clients.heading("ip_port", text="Địa chỉ Client (IP:Port)")
        self.tree_clients.heading("user", text="Tài khoản đăng nhập")
        self.tree_clients.heading("status", text="Trạng thái kết nối")

        self.tree_clients.column("ip_port", width=200)
        self.tree_clients.column("user", width=180)
        self.tree_clients.column("status", width=150, anchor=tk.CENTER)

        self.tree_clients.pack(fill=tk.BOTH, expand=True)

    def refresh_clients_table(self):
        """Lấy danh sách client đang active từ server module."""
        for item in self.tree_clients.get_children():
            self.tree_clients.delete(item)

        active = server.get_active_clients()
        for client_key, info in active.items():
            addr = info.get("addr", client_key)
            if isinstance(addr, (list, tuple)) and len(addr) >= 2:
                addr_str = f"{addr[0]}:{addr[1]}"
            else:
                addr_str = str(addr)
            user = info.get("user") or "(Chưa đăng nhập)"
            self.tree_clients.insert("", tk.END, values=(addr_str, user, "Đang kết nối (UDP)"))

        self.lbl_card_clients_val.config(text=f"{len(active)} Đang nối")

    # =========================================================================
    # TAB 4: HƯỚNG DẪN & GIAO THỨC
    # =========================================================================
    def setup_tab_info(self):
        txt_info = scrolledtext.ScrolledText(self.tab_info, wrap=tk.WORD, font=("Segoe UI", 10), bg="#ffffff")
        txt_info.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        doc = """
========================================================================================
               HỆ THỐNG MAIL SERVER & MAIL CLIENT - ĐỀ BÀI LẬP TRÌNH MẠNG
========================================================================================

1. ĐẶC TẢ YÊU CẦU ĐỀ BÀI:
   - Khi client gửi yêu cầu tạo account mới lên server:
     * Server tạo thư mục tương ứng với account ở máy server.
     * Tạo file 'new_email.txt' có nội dung:
       'Thank you for using this service. we hope that you will feel comfortabl........'
   - Khi client gửi email:
     * Nhận email từ client (người gửi, người nhận, tiêu đề, nội dung).
     * Server xác định gửi đến account nào.
     * Tại thư mục của account đó, tạo một file văn bản chứa nội dung email đó.
   - Khi client đăng nhập vào account:
     * Mở thư mục tương ứng với account đó ở server.
     * Gửi tất cả các tên file của thư mục đó về client.
   - Khi server ấn Dừng server:
     * Server phát thông báo SERVER_STOPPED tới tất cả các client đang online.
     * Các client lập tức bị văng về giao diện đăng nhập.

2. CÁC LỆNH GIAO THỨC JSON (UDP SOCKET):
   - CONNECT:    {"action": "CONNECT"}
   - REGISTER:   {"action": "REGISTER", "username": "<user>", "password": "<pass>"}
   - LOGIN:      {"action": "LOGIN", "username": "<user>", "password": "<pass>"}
   - SEND_EMAIL: {"action": "SEND_EMAIL", "to": "<to_user>", "subject": "<title>", "content": "..."}
   - LIST_FILES: {"action": "LIST_FILES", "username": "<user>"}
   - READ_EMAIL: {"action": "READ_EMAIL", "filename": "<file.txt>", "username": "<user>"}
   - LOGOUT:     {"action": "LOGOUT", "username": "<user>"}
   - QUIT:       {"action": "QUIT"}

3. CÁCH KIỂM THỬ:
   - Bạn có thể chạy 'python client_gui.py' hoặc 'python client.py' để kết nối tới server này.
   - Hoặc chạy 'python demo_test.py' để chạy kịch bản kiểm thử tự động toàn bộ 5 bước.
"""
        txt_info.insert(tk.END, doc.strip())
        txt_info.config(state=tk.DISABLED)

    # =========================================================================
    # ĐIỀU KHIỂN SERVER (START / STOP)
    # =========================================================================
    def action_start_server(self):
        """Khởi động Mail Server."""
        host = self.entry_host.get().strip()
        port_str = self.entry_port.get().strip()

        try:
            port = int(port_str)
        except ValueError:
            messagebox.showerror("Lỗi", "Cổng (Port) phải là một số nguyên hợp lệ!")
            return

        self.controller = server.MailServerController(host, port)
        ok, msg = self.controller.start()

        if not ok:
            messagebox.showerror("Lỗi Khởi Động Server", f"Không thể khởi động Mail Server:\n{msg}")
            return

        self.is_running = True
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.entry_host.config(state=tk.DISABLED)
        self.entry_port.config(state=tk.DISABLED)

        self.lbl_card_status_val.config(text=f"ĐANG CHẠY ({port})", fg=self.COLOR_SUCCESS)
        self.refresh_accounts_list()
        self.refresh_clients_table()

    def action_stop_server(self):
        """Dừng Mail Server."""
        if not self.controller or not self.is_running:
            return

        self.controller.stop()
        self.is_running = False

        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.entry_host.config(state=tk.NORMAL)
        self.entry_port.config(state=tk.NORMAL)

        self.lbl_card_status_val.config(text="ĐANG DỪNG", fg=self.COLOR_DANGER)
        self.refresh_clients_table()

    # =========================================================================
    # XỬ LÝ HÀNG ĐỢI SỰ KIỆN ĐA LUỒNG (THREAD-SAFE EVENT QUEUE)
    # =========================================================================
    def on_server_log(self, formatted_log: str):
        """Callback từ module server khi có log mới."""
        self.msg_queue.put(("LOG", formatted_log))

    def on_client_count_changed(self, count: int):
        """Callback từ module server khi số lượng client thay đổi."""
        self.msg_queue.put(("CLIENT_COUNT", count))

    def process_queue(self):
        """Lấy các sự kiện trong hàng đợi và render lên GUI."""
        while not self.msg_queue.empty():
            try:
                event_type, data = self.msg_queue.get_nowait()
                if event_type == "LOG":
                    self.append_log(str(data))
                    # Nếu có hành động đăng ký, đăng nhập hay gửi thư, tự làm mới danh sách thư mục và CSDL
                    if any(k in str(data) for k in ["[REGISTER SUCCESS]", "[SEND SUCCESS]", "[GMAIL SUCCESS]", "[GMAIL FAILED]", "[GMAIL ERROR]"]):
                        self.refresh_accounts_list()
                        self.refresh_database_table()
                elif event_type == "CLIENT_COUNT":
                    self.lbl_card_clients_val.config(text=f"{data} Đang nối")
                    self.refresh_clients_table()
            except queue.Empty:
                break

        # Lặp lại sau mỗi 100ms
        self.root.after(100, self.process_queue)

    def update_storage_stats(self):
        """Đọc và cập nhật số liệu từ thư mục."""
        self.refresh_accounts_list()

    def on_close(self):
        """Xử lý khi người dùng nhấn nút đóng cửa sổ GUI - Dừng server và thoát hoàn toàn tiến trình."""
        try:
            if self.controller:
                self.controller.stop()
        except Exception as e:
            print(f"[Error stopping server]: {e}")

        try:
            self.root.destroy()
        except Exception:
            pass

        # Giải phóng hoàn toàn cổng socket và thoát tiến trình ngay lập tức
        os._exit(0)


def main():
    root = tk.Tk()
    app = MailServerGUI(root)
    try:
        root.mainloop()
    finally:
        if app.controller:
            try:
                app.controller.stop()
            except Exception:
                pass
        os._exit(0)


if __name__ == "__main__":
    main()