import sys
import json
import socket

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_SERVER_HOST = "127.0.0.1"  # Lắng nghe trên tất cả card mạng (Wi-Fi, LAN, localhost)
DEFAULT_PORT = 2345
BUFFER_SIZE = 65507  


def setup_udp_socket(sock: socket.socket):
    if sys.platform == "win32":
        try:
            if hasattr(socket, "SIO_UDP_CONNRESET"):
                sock.ioctl(socket.SIO_UDP_CONNRESET, False)
        except Exception:
            pass



def get_lan_ip() -> str:
    """Lấy địa chỉ IP nội bộ (LAN IP) của máy trong mạng Wi-Fi/Ethernet."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# Nội dung thư chào mừng theo đúng yêu cầu đề bài:
WELCOME_EMAIL_FILENAME = "new_email.txt"
WELCOME_EMAIL_CONTENT = "Thank you for using this service. we hope that you will feel comfortabl........"


def send_json(sock: socket.socket, data: dict, addr=None):
    """Gửi một gói tin JSON qua UDP socket tới địa chỉ chỉ định (hoặc socket đã connect)."""
    payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
    if addr is not None:
        sock.sendto(payload, addr)
    else:
        sock.send(payload)


def recv_json_from(sock: socket.socket, timeout=None) -> tuple:
    """
    Nhận một gói tin JSON qua UDP datagram socket.
    Trả về: (dict_data, client_addr) hoặc (None, None) nếu timeout hoặc lỗi.
    """
    old_timeout = sock.gettimeout()
    if timeout is not None:
        sock.settimeout(timeout)
    try:
        data, addr = sock.recvfrom(BUFFER_SIZE)
        if not data:
            return None, addr
        parsed = json.loads(data.decode("utf-8", errors="replace"))
        return parsed, addr
    except (socket.timeout, BlockingIOError):
        return None, None
    except (ConnectionResetError, ConnectionAbortedError, OSError):
        return None, None
    except json.JSONDecodeError as e:
        print(f"[Error parsing JSON]: {e}")
        return None, None
    finally:
        if timeout is not None:
            sock.settimeout(old_timeout)


def recv_json(sock: socket.socket, timeout=None) -> dict:
    """Nhận một gói tin JSON qua UDP socket và trả về payload dict."""
    data, _ = recv_json_from(sock, timeout=timeout)
    return data

