"""
client_gui.py - Giao diện đồ họa (GUI) cho Mail Client bằng Tkinter (Giao thức UDP Socket)
Cung cấp giao diện trực quan: Đăng ký, Đăng nhập, Hộp thư, Xem email, Soạn và gửi email.
Khi Mail Server nhấn 'Dừng server', client sẽ tự động nhận thông báo và bị văng ra giao diện đăng nhập.

Cách chạy:
    python client_gui.py                      # 1 client
    python client_gui.py -n 3                 # mở 3 client cùng lúc
    python client_gui.py -n 3 --host 127.0.0.1 --port 2345
"""
import os
import sys
import time
import queue
import uuid
import threading
import argparse
import subprocess
import socket
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from common import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    setup_udp_socket,
    send_json,
    recv_json_from,
)


class MailClientGUI:
    def __init__(self, root, host=DEFAULT_HOST, port=DEFAULT_PORT, index=0):
        self.root = root
        self.default_host = host
        self.default_port = port
        self.index = index          # thứ tự cửa sổ, dùng để lệch vị trí
        self.child_count = 0        # số cửa sổ con đã mở từ cửa sổ này

        self.root.title("Python Mail Client - Hệ Thống Mail Server (UDP)")
        offset = 40 * index
        self.root.geometry(f"820x620+{50 + offset}+{50 + offset}")
        self.root.minsize(700, 500)

        self.sock = None
        self.server_host = host
        self.server_port = port
        self.server_addr = (host, port)
        self.current_user = None
        self.cached_files = []
        self.is_running = True
        self.listener_thread = None
        self.pending_requests = {}
        self.pending_lock = threading.Lock()
        self.compose_win = None

        self.create_styles()
        self.create_connection_frame()
        self.create_main_container()

        # Xử lý đóng cửa sổ
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TButton", font=("Segoe UI", 9, "bold"), padding=5)
        style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"), foreground="#1e3d59")
        style.configure("SubHeader.TLabel", font=("Segoe UI", 10, "bold"), foreground="#17b978")

    def create_connection_frame(self):
        top_frame = ttk.Frame(self.root, padding=8)
        top_frame.pack(fill=tk.X, side=tk.TOP)

        ttk.Label(top_frame, text="Máy chủ (Host):").pack(side=tk.LEFT, padx=3)
        self.host_entry = ttk.Entry(top_frame, width=14)
        self.host_entry.insert(0, self.default_host)
        self.host_entry.pack(side=tk.LEFT, padx=3)

        ttk.Label(top_frame, text="Cổng (Port):").pack(side=tk.LEFT, padx=3)
        self.port_entry = ttk.Entry(top_frame, width=6)
        self.port_entry.insert(0, str(self.default_port))
        self.port_entry.pack(side=tk.LEFT, padx=3)

        self.btn_connect = ttk.Button(top_frame, text="Kết nối Server (UDP)", command=self.connect_server)
        self.btn_connect.pack(side=tk.LEFT, padx=6)

        self.btn_new_window = ttk.Button(top_frame, text="➕ Mở Cửa Sổ Mới", command=self.open_new_client_window)
        self.btn_new_window.pack(side=tk.LEFT, padx=4)

        self.lbl_status = ttk.Label(top_frame, text="Chưa kết nối", foreground="red", font=("Segoe UI", 9, "italic"))
        self.lbl_status.pack(side=tk.RIGHT, padx=5)

    def open_new_client_window(self):
        """Mở thêm một cửa sổ Client GUI mới độc lập hoàn toàn (kế thừa host/port)."""
        script_path = os.path.abspath(__file__)
        self.child_count += 1
        try:
            subprocess.Popen([
                sys.executable, script_path,
                "--host", self.host_entry.get().strip(),
                "--port", self.port_entry.get().strip(),
                "--index", str(self.index + self.child_count),
            ])
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể mở thêm cửa sổ Client: {e}")

    def create_main_container(self):
        self.main_container = ttk.Frame(self.root, padding=10)
        self.main_container.pack(fill=tk.BOTH, expand=True)

        # 1. Khung Đăng nhập / Đăng ký
        self.auth_frame = ttk.LabelFrame(self.main_container, text=" Đăng ký / Đăng nhập Tài khoản ", padding=15)
        self.auth_frame.pack(fill=tk.X, pady=10)

        auth_grid = ttk.Frame(self.auth_frame)
        auth_grid.pack(anchor=tk.CENTER)

        ttk.Label(auth_grid, text="Tên tài khoản (Account):", font=("Segoe UI", 10)).grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.entry_username = ttk.Entry(auth_grid, width=28, font=("Segoe UI", 10))
        self.entry_username.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(auth_grid, text="Mật khẩu (Password):", font=("Segoe UI", 10)).grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.entry_password = ttk.Entry(auth_grid, width=28, font=("Segoe UI", 10), show="*")
        self.entry_password.grid(row=1, column=1, padx=5, pady=5)

        btn_box = ttk.Frame(auth_grid)
        btn_box.grid(row=2, column=0, columnspan=2, pady=10)

        self.btn_register = ttk.Button(btn_box, text="Đăng Ký Tài Khoản Mới", command=self.action_register)
        self.btn_register.pack(side=tk.LEFT, padx=8)

        self.btn_login = ttk.Button(btn_box, text="Đăng Nhập Hộp Thư", command=self.action_login)
        self.btn_login.pack(side=tk.LEFT, padx=8)

        # 2. Khung Hộp Thư (Sau khi đăng nhập)
        self.mailbox_frame = ttk.Frame(self.main_container)

        # Thanh tiêu đề hộp thư
        self.mailbox_header_frame = ttk.Frame(self.mailbox_frame)
        self.mailbox_header_frame.pack(fill=tk.X, pady=(0, 8))

        self.lbl_mailbox_title = ttk.Label(self.mailbox_header_frame, text="", style="Header.TLabel")
        self.lbl_mailbox_title.pack(side=tk.LEFT)

        self.btn_logout = ttk.Button(self.mailbox_header_frame, text="Đăng xuất", command=self.action_logout)
        self.btn_logout.pack(side=tk.RIGHT, padx=5)

        self.btn_refresh = ttk.Button(self.mailbox_header_frame, text="Làm mới danh sách", command=self.action_refresh)
        self.btn_refresh.pack(side=tk.RIGHT, padx=5)

        self.btn_compose = ttk.Button(self.mailbox_header_frame, text="+ Soạn Email Mới", command=self.open_compose_window)
        self.btn_compose.pack(side=tk.RIGHT, padx=5)

        # Chia 2 cột: trái (danh sách file) - phải (nội dung file)
        paned = ttk.PanedWindow(self.mailbox_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Cột trái: Danh sách file email
        left_box = ttk.LabelFrame(paned, text=" Các file email trong thư mục server ", padding=6)
        paned.add(left_box, weight=1)

        self.file_listbox = tk.Listbox(left_box, font=("Segoe UI", 10), selectmode=tk.SINGLE)
        self.file_listbox.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self.file_listbox.bind("<<ListboxSelect>>", self.on_file_selected)

        list_scroll = ttk.Scrollbar(left_box, orient=tk.VERTICAL, command=self.file_listbox.yview)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.file_listbox.config(yscrollcommand=list_scroll.set)

        # Cột phải: Xem nội dung email
        right_box = ttk.LabelFrame(paned, text=" Nội dung file email ", padding=6)
        paned.add(right_box, weight=2)

        self.txt_content = scrolledtext.ScrolledText(right_box, wrap=tk.WORD, font=("Consolas", 10))
        self.txt_content.pack(fill=tk.BOTH, expand=True)

    def close_socket(self):
        """Đóng socket UDP hiện tại nếu có."""
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def connect_server(self, show_msg=True) -> bool:
        """Khởi tạo socket UDP và kiểm tra kết nối với server."""
        host = self.host_entry.get().strip()
        try:
            port = int(self.port_entry.get().strip())
        except ValueError:
            messagebox.showerror("Lỗi", "Cổng (Port) phải là số nguyên!")
            return False

        try:
            self.close_socket()
            self.server_host = host
            self.server_port = port
            self.server_addr = (host, port)

            new_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            setup_udp_socket(new_sock)
            new_sock.settimeout(0.5)
            self.sock = new_sock
            self.is_running = True

            # Khởi động luồng nền lắng nghe phản hồi và thông báo từ Server
            if not self.listener_thread or not self.listener_thread.is_alive():
                self.listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
                self.listener_thread.start()

            # Gửi gói tin CONNECT / PING để kiểm tra server
            req = {"action": "CONNECT"}
            res = self.send_request(req, timeout=2.5)

            if res and res.get("status") == "SUCCESS":
                self.lbl_status.config(text=f"Đã kết nối UDP: {host}:{port}", foreground="green")
                self.btn_connect.config(state=tk.DISABLED)
                if show_msg:
                    messagebox.showinfo("Thành công", f"Đã kết nối thành công tới Mail Server (UDP) tại {host}:{port}")
                return True
            else:
                self.lbl_status.config(text="Server không phản hồi", foreground="red")
                self.close_socket()
                if show_msg:
                    messagebox.showerror(
                        "Lỗi kết nối",
                        f"Không nhận được phản hồi UDP từ {host}:{port}.\nHãy chắc chắn Mail Server đang bật!"
                    )
                return False
        except Exception as e:
            self.close_socket()
            self.lbl_status.config(text="Kết nối thất bại", foreground="red")
            if show_msg:
                messagebox.showerror("Lỗi kết nối", f"Không thể kết nối server: {e}")
            return False

    def ensure_connected(self) -> bool:
        """Đảm bảo socket UDP đã sẵn sàng kết nối."""
        if not self.sock:
            return self.connect_server()
        return True

    def send_request(self, req: dict, timeout=3.0) -> dict:
        """Gửi gói tin JSON qua UDP và đợi phản hồi theo req_id (không làm đơ giao diện)."""
        if not self.sock:
            return {"status": "ERROR", "message": "Chưa kết nối tới Mail Server!"}

        req_id = req.get("req_id") or str(uuid.uuid4())
        req["req_id"] = req_id

        resp_queue = queue.Queue()
        with self.pending_lock:
            self.pending_requests[req_id] = resp_queue

        try:
            send_json(self.sock, req, self.server_addr)
            res = resp_queue.get(timeout=timeout)
            return res
        except queue.Empty:
            return {"status": "ERROR", "message": "Hết thời gian chờ phản hồi từ server (UDP Timeout)."}
        except Exception as e:
            return {"status": "ERROR", "message": f"Lỗi gửi dữ liệu UDP: {e}"}
        finally:
            with self.pending_lock:
                self.pending_requests.pop(req_id, None)

    def _listen_loop(self):
        """Luồng nền liên tục lắng nghe datagram UDP từ Server."""
        while self.is_running:
            if not self.sock:
                time.sleep(0.1)
                continue
            try:
                msg, addr = recv_json_from(self.sock)
                if not msg:
                    continue

                action = msg.get("action", "")
                status = msg.get("status", "")

                # Trường hợp: Server ấn Dừng server -> nhận thông báo SERVER_STOPPED
                if action == "SERVER_STOPPED" or status == "SERVER_STOPPED":
                    notice = msg.get(
                        "message",
                        "Máy chủ (Mail Server) đã dừng hoạt động. Bạn đã bị đưa về giao diện đăng nhập!"
                    )
                    # Chuyển xử lý giao diện về main thread của Tkinter
                    self.root.after(0, self.on_server_stopped, notice)
                    continue

                # Phản hồi cho request đang đợi
                req_id = msg.get("req_id")
                with self.pending_lock:
                    if req_id and req_id in self.pending_requests:
                        self.pending_requests[req_id].put(msg)

            except (socket.timeout, BlockingIOError):
                continue
            except (ConnectionResetError, OSError):
                continue
            except Exception:
                time.sleep(0.05)

    def on_server_stopped(self, notice: str):
        """
        Xử lý khi server ấn Dừng server:
        Văng ngay lập tức ra giao diện đăng nhập và thông báo cho người dùng.
        """
        was_logged_in = (self.current_user is not None)

        # 1. Reset thông tin tài khoản đang đăng nhập
        self.current_user = None
        self.cached_files = []

        # 2. Đóng cửa sổ soạn email nếu đang mở
        if self.compose_win and self.compose_win.winfo_exists():
            try:
                self.compose_win.destroy()
            except Exception:
                pass
            self.compose_win = None

        # 3. Đặt lại tiêu đề cửa sổ
        self.root.title("Python Mail Client - Hệ Thống Mail Server (UDP)")

        # 4. Ẩn giao diện hộp thư, hiện lại giao diện đăng nhập
        self.mailbox_frame.pack_forget()
        self.auth_frame.pack(fill=tk.X, pady=10)
        self.entry_password.delete(0, tk.END)

        # 5. Cập nhật nhãn trạng thái và cho phép bấm nút Kết nối lại
        self.lbl_status.config(text="Server đã dừng", foreground="red")
        self.btn_connect.config(state=tk.NORMAL)

        # 6. Đóng socket cũ
        self.close_socket()

        # 7. Hiển thị cảnh báo cho người dùng
        if was_logged_in:
            messagebox.showwarning(
                "Máy Chủ Đã Dừng",
                f"{notice}\n\nBạn đã bị đưa về giao diện đăng nhập."
            )
        else:
            self.lbl_status.config(text="Server đã dừng", foreground="red")

    def action_register(self):
        if not self.ensure_connected():
            return
        username = self.entry_username.get().strip()
        password = self.entry_password.get().strip()
        if not username or not password:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập đầy đủ tên tài khoản và mật khẩu!")
            return

        res = self.send_request({
            "action": "REGISTER",
            "username": username,
            "password": password
        })
        if res and res.get("status") == "SUCCESS":
            messagebox.showinfo("Đăng ký thành công", res.get("message"))
        else:
            msg = res.get("message") if res else "Không phản hồi từ server."
            messagebox.showerror("Đăng ký thất bại", msg)

    def action_login(self):
        if not self.ensure_connected():
            return
        username = self.entry_username.get().strip()
        password = self.entry_password.get().strip()
        if not username or not password:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập tên tài khoản và mật khẩu!")
            return

        res = self.send_request({
            "action": "LOGIN",
            "username": username,
            "password": password
        })
        if res and res.get("status") == "SUCCESS":
            self.current_user = username
            self.cached_files = res.get("files", [])
            self.root.title(f"Python Mail Client (UDP) - [{self.current_user}]")

            # Ẩn khung đăng nhập, hiện khung hộp thư
            self.auth_frame.pack_forget()
            self.lbl_mailbox_title.config(text=f"HỘP THƯ: {self.current_user}")
            self.mailbox_frame.pack(fill=tk.BOTH, expand=True)

            self.update_file_listbox()
            messagebox.showinfo(
                "Đăng nhập thành công",
                f"Chào mừng {username}!\nServer đã gửi danh sách {len(self.cached_files)} file email."
            )
        else:
            msg = res.get("message") if res else "Không phản hồi từ server."
            messagebox.showerror("Đăng nhập thất bại", msg)

    def update_file_listbox(self):
        self.file_listbox.delete(0, tk.END)
        for fname in self.cached_files:
            self.file_listbox.insert(tk.END, fname)

        if self.cached_files:
            # Chọn và hiển thị file đầu tiên
            self.file_listbox.selection_set(0)
            self.load_email_content(self.cached_files[0])
        else:
            self.txt_content.delete("1.0", tk.END)
            self.txt_content.insert(tk.END, "(Hộp thư trống, chưa có file nào)")

    def on_file_selected(self, event):
        selection = self.file_listbox.curselection()
        if selection:
            fname = self.file_listbox.get(selection[0])
            self.load_email_content(fname)

    def load_email_content(self, filename: str):
        if not self.sock or not self.current_user:
            return
        res = self.send_request({
            "action": "READ_EMAIL",
            "filename": filename,
            "username": self.current_user
        })
        self.txt_content.delete("1.0", tk.END)
        if res and res.get("status") == "SUCCESS":
            self.txt_content.insert(tk.END, res.get("content", ""))
        else:
            msg = res.get("message") if res else "Không phản hồi từ server."
            self.txt_content.insert(tk.END, f"Lỗi: {msg}")

    def action_refresh(self):
        if not self.sock or not self.current_user:
            return
        res = self.send_request({
            "action": "LIST_FILES",
            "username": self.current_user
        })
        if res and res.get("status") == "SUCCESS":
            self.cached_files = res.get("files", [])
            self.update_file_listbox()
        else:
            messagebox.showerror("Lỗi", "Không thể làm mới danh sách file.")

    def action_logout(self):
        if self.sock and self.current_user:
            try:
                self.send_request({
                    "action": "LOGOUT",
                    "username": self.current_user
                }, timeout=1.5)
            except Exception:
                pass
        self.current_user = None
        self.cached_files = []
        self.root.title("Python Mail Client - Hệ Thống Mail Server (UDP)")
        self.mailbox_frame.pack_forget()
        self.auth_frame.pack(fill=tk.X, pady=10)
        self.entry_password.delete(0, tk.END)

    def open_compose_window(self):
        """Mở cửa sổ soạn thảo email mới (hỗ trợ gửi nội bộ hoặc Gmail thực tế)."""
        self.compose_win = tk.Toplevel(self.root)
        self.compose_win.title("Soạn Email Mới")
        self.compose_win.geometry("540x480")
        self.compose_win.minsize(450, 400)
        self.compose_win.transient(self.root)

        frame = ttk.Frame(self.compose_win, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=f"Người gửi (From): {self.current_user}", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, pady=2)

        ttk.Label(frame, text="Gửi đến account nội bộ hoặc Gmail (To):", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, pady=(6, 2))
        entry_to = ttk.Entry(frame, width=45)
        entry_to.pack(fill=tk.X)
        ttk.Label(frame, text="* Ví dụ tài khoản nội bộ: 'bob' | Ví dụ gửi Gmail thực tế: 'nguoinhan@gmail.com'", font=("Segoe UI", 8, "italic"), foreground="#666666").pack(anchor=tk.W, pady=(2, 4))

        ttk.Label(frame, text="Tiêu đề (Subject):", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, pady=(4, 2))
        entry_subject = ttk.Entry(frame, width=45)
        entry_subject.pack(fill=tk.X)

        ttk.Label(frame, text="Nội dung (Content):", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, pady=(4, 2))
        txt_body = scrolledtext.ScrolledText(frame, height=9, wrap=tk.WORD)
        txt_body.pack(fill=tk.BOTH, expand=True, pady=4)

        bottom_bar = tk.Frame(frame)
        bottom_bar.pack(fill=tk.X, pady=6)

        lbl_sending = tk.Label(bottom_bar, text="", font=("Segoe UI", 9, "italic"), fg="#2980b9")
        lbl_sending.pack(side=tk.LEFT)

        def do_send():
            recipient = entry_to.get().strip()
            subject = entry_subject.get().strip()
            body = txt_body.get("1.0", tk.END).strip()

            if not recipient:
                messagebox.showwarning("Cảnh báo", "Vui lòng nhập tài khoản người nhận hoặc địa chỉ Gmail!", parent=self.compose_win)
                return

            btn_send.config(state=tk.DISABLED, text="⏳ Đang gửi...")
            lbl_sending.config(text="Đang xử lý gửi qua Mail Server...")

            def send_worker():
                res = self.send_request({
                    "action": "SEND_EMAIL",
                    "to": recipient,
                    "subject": subject,
                    "content": body,
                    "from": self.current_user
                }, timeout=20.0)

                def callback():
                    btn_send.config(state=tk.NORMAL, text="Gửi Email")
                    lbl_sending.config(text="")
                    if res and res.get("status") == "SUCCESS":
                        messagebox.showinfo("Thành công", res.get("message"), parent=self.compose_win)
                        if self.compose_win and self.compose_win.winfo_exists():
                            self.compose_win.destroy()
                            self.compose_win = None
                    else:
                        msg = res.get("message") if res else "Không nhận được phản hồi từ Server (Timeout)."
                        messagebox.showerror("Thất bại", msg, parent=self.compose_win)

                self.root.after(0, callback)

            threading.Thread(target=send_worker, daemon=True).start()

        btn_send = ttk.Button(bottom_bar, text="Gửi Email", command=do_send)
        btn_send.pack(side=tk.RIGHT)

    def on_close(self):
        self.is_running = False
        if self.sock:
            try:
                send_json(self.sock, {"action": "QUIT"}, self.server_addr)
            except Exception:
                pass
            self.close_socket()
        try:
            self.root.destroy()
        except Exception:
            pass
        os._exit(0)


def parse_args():
    parser = argparse.ArgumentParser(description="Python Mail Client GUI (UDP)")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Địa chỉ mail server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Cổng mail server")
    parser.add_argument("-n", "--clients", type=int, default=1,
                        help="Số cửa sổ client muốn mở cùng lúc")
    parser.add_argument("--index", type=int, default=0,
                        help="(nội bộ) thứ tự cửa sổ để lệch vị trí")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # Tiến trình gốc (index=0) sinh thêm n-1 tiến trình client độc lập
    if args.index == 0 and args.clients > 1:
        script_path = os.path.abspath(__file__)
        for i in range(1, args.clients):
            subprocess.Popen([
                sys.executable, script_path,
                "--host", args.host,
                "--port", str(args.port),
                "--index", str(i),
            ])

    root = tk.Tk()
    app = MailClientGUI(root, args.host, args.port, args.index)
    try:
        root.mainloop()
    finally:
        os._exit(0)