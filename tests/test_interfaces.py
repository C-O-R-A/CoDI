import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from codi.interfaces import CoraClient, CoraInterface, CoraServer
from codi.messages import CommandMessage, ConfigMessage, ImageMessage, FeedbackMessage


class DummySocket:
    def __init__(self):
        self.closed = False

    def shutdown(self, *args, **kwargs):
        self.closed = True

    def close(self):
        self.closed = True


@pytest.fixture
def interface_kwargs():
    return {
        "host": "localhost",
        "ports": {
            "command_port": 5000,
            "states_port": 5001,
            "video_port": 5002,
            "config_port": 5003,
        },
    }


def test_cora_interface_initializes_socket_registry(interface_kwargs, monkeypatch):
    monkeypatch.setattr("socket.gethostbyname", lambda host: "127.0.0.1")

    iface = CoraInterface(**interface_kwargs)

    assert iface.arm_host == "127.0.0.1"
    assert set(iface.sockets) == {
        "command_socket",
        "states_socket",
        "video_socket",
        "config_socket",
    }
    assert iface.sockets["command_socket"]["model"] is CommandMessage
    assert iface.sockets["config_socket"]["model"] is ConfigMessage
    assert iface.sockets["video_socket"]["model"] is ImageMessage
    assert iface.sockets["states_socket"]["model"] is FeedbackMessage


def test_cora_client_configure_and_update_options(interface_kwargs, monkeypatch):
    monkeypatch.setattr("socket.gethostbyname", lambda host: "127.0.0.1")

    client = CoraClient(**interface_kwargs)
    client.init_threads()

    client.configure_robot(use_camera=True)
    assert client.sockets["states_socket"]["thread"]["active"] is True
    assert client.sockets["video_socket"]["thread"]["active"] is True
    
    client.configure_robot(use_camera=False)
    assert client.sockets["video_socket"]["thread"]["active"] is False


def test_cora_server_initializes_server_state(interface_kwargs, monkeypatch):
    monkeypatch.setattr("socket.gethostbyname", lambda host: "127.0.0.1")

    server = CoraServer(**interface_kwargs)

    assert server.use_video is False
    assert server.threaded_sockets == ["command_socket", "config_socket"]
    assert server.sockets["command_socket"]["connected"] is False


def test_cora_server_cleanup_closes_connected_sockets(interface_kwargs, monkeypatch):
    monkeypatch.setattr("socket.gethostbyname", lambda host: "127.0.0.1")

    server = CoraServer(**interface_kwargs)
    server.sockets["command_socket"]["socket"] = DummySocket()
    server.sockets["config_socket"]["socket"] = DummySocket()

    server.cleanup()

    assert server.sockets["command_socket"]["socket"] is None
    assert server.sockets["config_socket"]["socket"] is None
