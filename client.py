import sys

# Đảm bảo UTF-8 hoạt động trên console Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import socket
from common import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    setup_udp_socket,
    send_json,
    recv_json,
)


class MailClient:
    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self.server_addr = (host, port)
        self.sock = None
        self.current_user = None
        self.cached_files = []

    def connect(self) -> bool:
        """Khởi tạo socket UDP và kiểm tra kết nối tới Mail Server."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            setup_udp_socket(self.sock)
            self.sock.settimeout(2.5)

            # Gửi gói CONNECT để kiểm tra server
            send_json(self.sock, {"action": "CONNECT"}, self.server_addr)
            res = recv_json(self.sock, timeout=2.5)
            if res and res.get("status") == "SUCCESS":
                print(f"[+] Đã kết nối thành công tới Mail Server (UDP) tại {self.host}:{self.port}")
                return True
            else:
                print(f"[-] Không nhận được phản hồi từ Mail Server tại {self.host}:{self.port}")
                return False
        except Exception as e:
            print(f"[-] Không thể kết nối tới Mail Server tại {self.host}:{self.port}: {e}")
            return False

    def close(self):
        """Đóng kết nối UDP."""
        if self.sock:
            try:
                send_json(self.sock, {"action": "QUIT"}, self.server_addr)
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
            print("[*] Đã đóng kết nối với Mail Server.")

    def send_request(self, req: dict, timeout=3.0) -> dict:
        """Gửi yêu cầu qua UDP và nhận phản hồi (có kiểm tra SERVER_STOPPED)."""
        if not self.sock:
            return None
        try:
            send_json(self.sock, req, self.server_addr)
            res = recv_json(self.sock, timeout=timeout)
            if res and (res.get("action") == "SERVER_STOPPED" or res.get("status") == "SERVER_STOPPED"):
                print(f"\n[!] THÔNG BÁO: {res.get('message', 'Server đã dừng.')}")
                print("[!] Bạn đã bị đăng xuất khỏi hệ thống!")
                self.current_user = None
                self.cached_files = []
                return None
            return res
        except Exception as e:
            print(f"[-] Lỗi gửi nhận UDP: {e}")
            return None

    def register(self):
        """Gửi yêu cầu đăng ký tài khoản mới lên server qua UDP."""
        print("\n" + "=" * 45)
        print("          ĐĂNG KÝ TÀI KHOẢN MỚI (UDP)")
        print("=" * 45)
        username = input("Nhập tên tài khoản mới: ").strip()
        if not username:
            print("[-] Tên tài khoản không được để trống!")
            return

        password = input("Nhập mật khẩu: ").strip()
        if not password:
            print("[-] Mật khẩu không được để trống!")
            return

        req = {
            "action": "REGISTER",
            "username": username,
            "password": password
        }
        res = self.send_request(req)

        if res and res.get("status") == "SUCCESS":
            print(f"\n[OK] {res.get('message')}")
            print(f"[!] Server đã tạo thư mục '{username}' và file 'new_email.txt'.")
        else:
            msg = res.get("message") if res else "Không nhận được phản hồi từ server (UDP Timeout)."
            print(f"\n[-] Đăng ký thất bại: {msg}")

    def login(self) -> bool:
        """
        Đăng nhập vào một account qua UDP:
        Server sẽ mở thư mục tương ứng và gửi tất cả các tên file về client.
        """
        print("\n" + "=" * 45)
        print("             ĐĂNG NHẬP (UDP)")
        print("=" * 45)
        username = input("Tên tài khoản: ").strip()
        password = input("Mật khẩu: ").strip()

        req = {
            "action": "LOGIN",
            "username": username,
            "password": password
        }
        res = self.send_request(req)

        if res and res.get("status") == "SUCCESS":
            self.current_user = username
            self.cached_files = res.get("files", [])
            print(f"\n[OK] {res.get('message')}")
            self.display_email_files()
            return True
        else:
            msg = res.get("message") if res else "Không nhận được phản hồi từ server (UDP Timeout)."
            print(f"\n[-] Đăng nhập thất bại: {msg}")
            return False

    def display_email_files(self):
        """Hiển thị tất cả các tên file do server gửi về."""
        print("\n" + "-" * 55)
        print(f" DANH SÁCH FILE EMAIL TRONG THƯ MỤC [{self.current_user}]:")
        print("-" * 55)
        if not self.cached_files:
            print("  (Thư mục trống, chưa có file nào)")
        else:
            for idx, fname in enumerate(self.cached_files, 1):
                print(f"  [{idx}] {fname}")
        print("-" * 55)

    def refresh_file_list(self):
        """Yêu cầu server gửi lại danh sách file mới nhất."""
        req = {"action": "LIST_FILES", "username": self.current_user}
        res = self.send_request(req)
        if res and res.get("status") == "SUCCESS":
            self.cached_files = res.get("files", [])
            self.display_email_files()
        else:
            print("[-] Không thể tải lại danh sách file.")

    def read_email(self):
        """Chọn và đọc nội dung một file email qua UDP."""
        if not self.cached_files:
            print("[-] Hiện tại không có file email nào để đọc.")
            return

        print("\nNhập số thứ tự file bạn muốn đọc (hoặc nhập tên file):")
        choice = input("Lựa chọn: ").strip()
        target_filename = None

        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(self.cached_files):
                target_filename = self.cached_files[idx - 1]
        elif choice in self.cached_files:
            target_filename = choice

        if not target_filename:
            print("[-] Lựa chọn file không hợp lệ!")
            return

        req = {
            "action": "READ_EMAIL",
            "filename": target_filename,
            "username": self.current_user
        }
        res = self.send_request(req)

        if res and res.get("status") == "SUCCESS":
            print("\n" + "=" * 60)
            print(f" NỘI DUNG FILE: {res.get('filename')}")
            print("=" * 60)
            print(res.get("content"))
            print("=" * 60)
        else:
            msg = res.get("message") if res else "Lỗi đọc file."
            print(f"[-] {msg}")

    def send_email(self):
        """Gửi email tới một account khác trên server qua UDP."""
        print("\n" + "=" * 45)
        print(f"        SOẠN VÀ GỬI EMAIL (Từ: {self.current_user})")
        print("=" * 45)
        recipient = input("Gửi đến account nội bộ hoặc Gmail (vd: bob, user@gmail.com): ").strip()
        if not recipient:
            print("[-] Chưa nhập người nhận!")
            return

        subject = input("Tiêu đề email: ").strip()
        print("Nhập nội dung email (Nhấn Enter rồi gõ 'END' trên một dòng riêng để kết thúc):")
        lines = []
        while True:
            line = input()
            if line.strip() == "END":
                break
            lines.append(line)
        content = "\n".join(lines)

        req = {
            "action": "SEND_EMAIL",
            "to": recipient,
            "subject": subject,
            "content": content,
            "from": self.current_user
        }
        print("[*] Đang gửi qua Mail Server...")
        res = self.send_request(req, timeout=20.0)

        if res and res.get("status") == "SUCCESS":
            print(f"\n[OK] {res.get('message')}")
        else:
            msg = res.get("message") if res else "Không nhận được phản hồi (Timeout)."
            print(f"\n[-] Gửi email thất bại: {msg}")

    def logout(self):
        """Đăng xuất tài khoản hiện tại."""
        req = {"action": "LOGOUT", "username": self.current_user}
        res = self.send_request(req)
        msg = res.get("message", "Đã đăng xuất.") if res else "Đã đăng xuất."
        print(f"\n[*] {msg}")
        self.current_user = None
        self.cached_files = []

    def run_mailbox_menu(self):
        """Menu xử lý sau khi người dùng đã đăng nhập."""
        while self.current_user:
            print(f"\n===== HỘP THƯ: [{self.current_user}] =====")
            print("1. Xem danh sách các file email")
            print("2. Đọc nội dung một email")
            print("3. Soạn và gửi email mới")
            print("4. Đăng xuất (Logout)")
            choice = input("Mời chọn chức năng (1-4): ").strip()

            if choice == "1":
                self.refresh_file_list()
            elif choice == "2":
                self.read_email()
            elif choice == "3":
                self.send_email()
            elif choice == "4":
                self.logout()
                break
            else:
                print("[-] Lựa chọn không hợp lệ, vui lòng chọn lại.")

    def run(self):
        """Vòng lặp giao diện chính của Client."""
        if not self.connect():
            return

        try:
            while True:
                print("\n" + "=" * 45)
                print("         CHƯƠNG TRÌNH MAIL CLIENT (UDP)")
                print("=" * 45)
                print("1. Tạo tài khoản mới (Register)")
                print("2. Đăng nhập (Login)")
                print("0. Thoát (Exit)")
                print("-" * 45)
                choice = input("Mời chọn chức năng (0-2): ").strip()

                if choice == "1":
                    self.register()
                elif choice == "2":
                    if self.login():
                        self.run_mailbox_menu()
                elif choice == "0":
                    print("[*] Tạm biệt!")
                    break
                else:
                    print("[-] Lựa chọn không hợp lệ.")
        finally:
            self.close()


if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HOST
    port = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_PORT
    client = MailClient(host, port)
    client.run()

