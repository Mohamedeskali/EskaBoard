"""Find the local LAN IPv4 address."""
import socket


def get_lan_ip():
    """Return the LAN IPv4 address by connecting to an external IP (no packet sent)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
