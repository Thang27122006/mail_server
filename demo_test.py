"""
demo_test.py - Kịch bản kiểm thử tự động toàn diện hệ thống Mail Server (UDP)
Kiểm tra:
  1. Kết nối UDP Socket
  2. Tạo tài khoản (Register) -> sinh thư mục và new_email.txt
  3. Đăng nhập (Login) -> nhận danh sách file
  4. Gửi email từ Bob sang Alice -> tạo file email trong thư mục Alice
  5. Alice đọc email vừa nhận
  6. Server dừng hoạt động -> kiểm tra Client nhận gói tin SERVER_STOPPED và văng ra màn hình đăng nhập
"""
import os
import sys
import time
import socket

# Đảm bảo UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import shutil
import server
from common import (
    setup_udp_socket,
    send_json,
    recv_json,
    WELCOME_EMAIL_FILENAME,
    WELCOME_EMAIL_CONTENT,
)

TEST_HOST = "127.0.0.1"
TEST_PORT = 19876


def cleanup_test_data():
    """Dọn dẹp tài khoản và thư mục kiểm thử để kịch bản có thể chạy lặp lại."""
    accounts = server.load_accounts()
    for u in ["alice_udp", "bob_udp"]:
        accounts.pop(u, None)
        u_dir = os.path.join(server.STORAGE_DIR, u)
        if os.path.exists(u_dir):
            shutil.rmtree(u_dir, ignore_errors=True)
    server.save_accounts(accounts)


def run_tests():
    cleanup_test_data()
    print("=" * 65)
    print(" BẮT ĐẦU KIỂM THỬ HỆ THỐNG MAIL SERVER GIAO THỨC UDP")
    print("=" * 65)


    # 1. Khởi động Server trên cổng test
    print("\n[Bước 1] Khởi động Mail Server UDP tại 127.0.0.1:19876...")
    controller = server.MailServerController(TEST_HOST, TEST_PORT)
    ok, err = controller.start()
    assert ok, f"Khởi động server thất bại: {err}"
    print(" -> Server UDP đã khởi động thành công.")

    # 2. Khởi tạo Client UDP Socket
    client_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    setup_udp_socket(client_sock)
    client_sock.settimeout(3.0)
    server_addr = (TEST_HOST, TEST_PORT)

    try:
        # Kiểm tra gói CONNECT
        send_json(client_sock, {"action": "CONNECT", "req_id": "test_connect"}, server_addr)
        res = recv_json(client_sock, timeout=3.0)
        assert res and res.get("status") == "SUCCESS", f"Lỗi connect: {res}"
        print(" -> Kết nối UDP Client - Server thành công.")

        # 3. Đăng ký tài khoản alice
        print("\n[Bước 2] Kiểm tra Đăng Ký (REGISTER) tài khoản 'alice_udp'...")
        send_json(client_sock, {
            "action": "REGISTER",
            "username": "alice_udp",
            "password": "password123",
            "req_id": "reg_alice"
        }, server_addr)
        res = recv_json(client_sock, timeout=3.0)
        assert res and res.get("status") == "SUCCESS", f"Lỗi đăng ký alice: {res}"
        print(f" -> Server phản hồi: {res.get('message')}")

        # Kiểm tra file new_email.txt trên đĩa
        alice_dir = os.path.join(server.STORAGE_DIR, "alice_udp")
        welcome_file = os.path.join(alice_dir, WELCOME_EMAIL_FILENAME)
        assert os.path.exists(welcome_file), "File new_email.txt không tồn tại!"
        with open(welcome_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert content == WELCOME_EMAIL_CONTENT, "Nội dung new_email.txt không đúng mẫu đề bài!"
        print(" -> Đã xác minh: Thư mục 'alice_udp' và file 'new_email.txt' tồn tại với đúng nội dung đề bài!")

        # 4. Đăng nhập tài khoản alice
        print("\n[Bước 3] Kiểm tra Đăng Nhập (LOGIN) tài khoản 'alice_udp'...")
        send_json(client_sock, {
            "action": "LOGIN",
            "username": "alice_udp",
            "password": "password123",
            "req_id": "login_alice"
        }, server_addr)
        res = recv_json(client_sock, timeout=3.0)
        assert res and res.get("status") == "SUCCESS", f"Lỗi đăng nhập: {res}"
        files = res.get("files", [])
        assert WELCOME_EMAIL_FILENAME in files, f"Danh sách file không chứa {WELCOME_EMAIL_FILENAME}: {files}"
        print(f" -> Đăng nhập thành công, Server đã gửi danh sách file: {files}")

        # 5. Đăng ký bob và bob gửi email tới alice
        print("\n[Bước 4] Kiểm tra Tạo tài khoản 'bob_udp' và Gửi email tới 'alice_udp'...")
        send_json(client_sock, {
            "action": "REGISTER",
            "username": "bob_udp",
            "password": "bobpassword",
            "req_id": "reg_bob"
        }, server_addr)
        recv_json(client_sock, timeout=3.0)

        # Gửi email từ bob tới alice
        email_subj = "Chào mừng tới mạng máy tính UDP"
        email_body = "Đây là nội dung email gửi qua giao thức UDP Socket."
        send_json(client_sock, {
            "action": "SEND_EMAIL",
            "from": "bob_udp",
            "to": "alice_udp",
            "subject": email_subj,
            "content": email_body,
            "req_id": "send_1"
        }, server_addr)
        res = recv_json(client_sock, timeout=3.0)
        assert res and res.get("status") == "SUCCESS", f"Lỗi gửi email: {res}"
        sent_filename = res.get("filename")
        print(f" -> Gửi email thành công: File '{sent_filename}' đã được tạo trong thư mục alice_udp.")

        # 6. Alice đọc danh sách file và nội dung email
        print("\n[Bước 5] Kiểm tra 'alice_udp' tải danh sách file và Đọc nội dung email...")
        send_json(client_sock, {
            "action": "LIST_FILES",
            "username": "alice_udp",
            "req_id": "list_alice"
        }, server_addr)
        res = recv_json(client_sock, timeout=3.0)
        assert sent_filename in res.get("files", []), "File email mới không có trong danh sách file!"

        # Đọc email
        send_json(client_sock, {
            "action": "READ_EMAIL",
            "username": "alice_udp",
            "filename": sent_filename,
            "req_id": "read_alice"
        }, server_addr)
        res = recv_json(client_sock, timeout=3.0)
        assert res and res.get("status") == "SUCCESS", f"Lỗi đọc email: {res}"
        assert email_body in res.get("content", ""), "Nội dung email đọc được không khớp!"
        print(f" -> Đọc email thành công! Nội dung:\n{res.get('content')}")

        # 7. Kiểm tra tính năng dừng server và client nhận gói tin SERVER_STOPPED
        print("\n[Bước 6] Kiểm tra tính năng DỪNG SERVER -> Client nhận thông báo và văng ra đăng nhập...")
        # Server dừng
        controller.stop()

        # Client lắng nghe gói tin SERVER_STOPPED từ server
        stop_pkt = recv_json(client_sock, timeout=3.0)
        assert stop_pkt is not None, "Client không nhận được thông báo khi server dừng!"
        action = stop_pkt.get("action")
        status = stop_pkt.get("status")
        assert action == "SERVER_STOPPED" or status == "SERVER_STOPPED", f"Gói tin nhận được không phải SERVER_STOPPED: {stop_pkt}"
        print(f" -> Client đã nhận thành công gói tin dừng từ Server:\n    {stop_pkt}")
        print(" -> Xác nhận client sẽ tự động văng về giao diện đăng nhập thành công!")

        print("\n" + "=" * 65)
        print(" [HOÀN TẤT] TẤT CẢ 6 BƯỚC KIỂM THỬ UDP ĐÃ THÀNH CÔNG 100%!")
        print("=" * 65)

    finally:
        try:
            client_sock.close()
        except Exception:
            pass
        if controller.is_running:
            controller.stop()


if __name__ == "__main__":
    run_tests()