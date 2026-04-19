"""CoDI (Cora Desktop Interface)

CoDI is an SDK developed by ... to interface with the open source Cora cobot.
    https://github.com/machine0herald/CoDI
;-)
"""

import socket
import select
import threading
from pathlib import Path
from yaml import safe_load
import json as js
from numpy.typing import NDArray
import time

from . import protocol as pt
from . import validation as val


class CoraInterface:

    def __init__(self, filepath: str = None, **kwargs):
        """
        :param filepath: absolute path to json or yaml config file
        :type filepath: str
        :param kwargs: \n
            ports: \n
                    [
                        host: tcp hostname \n
                        video_port: port for video \n
                        command_port: port for sending/receiving commands \n
                        states_port: port for sending/receiving states \n
                        config_port: port for setting/receiving robot param configs \n
                        vision_port: port for receiving marker poses
                    ]
        """

        self._running = False
        self.interface_state_lock = threading.Lock()
        with self.interface_state_lock:
            self._interface_state = "unconnected"

        self.sockets = {
            "command_socket": {
                "decoder": pt.decode_commands,
                "encoder": pt.encode_commands,
                "type": "write-only",
            },
            "states_socket": {
                "decoder": pt.decode_pose_feedback,
                "encoder": pt.encode_pose_feedback,
                "type": "read-only",
            },
            "video_socket": {
                "decoder": pt.bytes_to_image,
                "encoder": pt.image_to_bytes,
                "type": "read-only",
            },
            "config_socket": {
                "decoder": pt.decode_configs,
                "encoder": pt.encode_configs,
            },
            "vision_socket": {
                "decoder": pt.decode_aruco_poses,
                "encoder": pt.encode_aruco_poses,
            },
        }

        for socket_ in self.sockets.values():
            socket_["socket"] = None
            socket_["port"] = None
            socket_["alive"] = False
            socket_["message"] = None

        if filepath is not None:

            file = Path(filepath)
            extension = file.suffix

            match extension:
                case ".yaml":
                    with open(file, "r") as f:
                        loaded_file = safe_load(f)

                case ".json":
                    with open(file, "r") as f:
                        loaded_file = js.load(f)

            host = loaded_file.get("host")
            ports = loaded_file.get("ports", {})

        else:
            host = kwargs.get("host")
            ports = kwargs.get("ports", {})

        try:
            self.arm_host = socket.gethostbyname(host)
            print(f"Host found at {self.arm_host}")

            for socket_name, socket_ in self.sockets.items():
                socket_["port"] = ports.get(
                    socket_name.replace("_socket", "_port")
                )

        except socket_.gaierror:
            raise ValueError(f"Could not resolve hostname: {host}")

        self._set_move_status("initializing")

    def _create_sockets(self):
        for socket_val in self.sockets.values():
            socket_val["socket"] = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def _kill(self, stop_listening=True):
        if self._running is False:
            print("Client is already stopped.")
            return

        print("Stopping Cora interface...")

        self._running = False
        time.sleep(0.05)

        # Stop listening sockets
        if stop_listening:
            for sock in self.sockets.values():
                if sock["socket"]:
                    try:
                        sock["socket"].shutdown(socket.SHUT_RDWR)
                        sock["socket"].close()
                    except OSError:
                        pass

        self.cleanup()

        return

    def _set_move_status(self, status: str):
        self.move_status = val.status(status)

    def _end_interface(self):
        self._kill()
        self._supervisor_running = False

    def _is_socket_alive(self, connection, timeout=0.2):
        if connection is None:
            return False

        try:
            fd = connection.fileno()
            if fd < 0:
                print("incorrect fd")
                return False

            _, _, errored = select.select([connection], [], [connection], timeout)
            return not errored

        except (OSError, ValueError) as e:
            print(e)
            return False

    def _recv_exact(self, connection, n) -> bytes | None:
        """
        Receive exactly n bytes from the socket.
        Returns None if the connection is closed before n bytes are read.
        """
        data = bytearray()
        while len(data) < n:
            try:
                chunk = connection.recv(n - len(data))
                if not chunk:  # socket closed
                    return None
                data.extend(chunk)
            except OSError:
                return None
        return bytes(data)

    def _receive(self, connection) -> bytes | None:
        """
        Receive a length-prefixed message from the socket.
        Returns None if the connection is closed or data is invalid.
        """
        # Read 4-byte length prefix
        raw_length = self._recv_exact(connection, 4)
        if not raw_length:
            return None

        length = int.from_bytes(raw_length, "big")
        if length <= 0:
            return None

        # Read the full payload
        payload = self._recv_exact(connection, length)
        if not payload:
            return None

        return payload

    def _send(self, connection, payload: bytes):
        length = len(payload)
        connection.sendall(length.to_bytes(4, "big") + payload)

    def _socket_receive_loop(self, socket_):
        """
        Generic method to continuously receive data from a socket.

        :param socket_: socket to read from
        """
        print("initiating receive loop")
        stop_event = socket_["thread"]["stop_event"] if socket_["thread"] else None
        while self._running and (stop_event is None or not stop_event.is_set()):
            try:
                if self._is_socket_alive(socket_["socket"], 1) is False:
                    raise OSError("socket not alive")
                else:
                    socket_["alive"] = True
                    raw_data = self._receive(socket_["socket"])

                if not raw_data:
                    raise OSError("socket closed")

                socket_["message"] = socket_["decoder"](raw_data)

            except OSError as e:
                if socket_["alive"]:
                    print(f"socket died: {e}")
                    socket_["alive"] = False
                    time.sleep(0.1)
                continue

    def _socket_send(self, socket_, payload):
        """
        Generic method to send data over a socket safely.

        :param socket_: socket object to send through
        :param payload: bytes to send
        """
        if self._running:
            payload = (
                socket_["encoder"](payload)
                if not isinstance(payload, bytes)
                else payload
            )
            try:
                if self._is_socket_alive(socket_["socket"], 1) is False:
                    raise OSError("socket not alive")
                else:
                    socket_["alive"] = True
                    self._send(socket_["socket"], payload)
            except OSError as e:
                if socket_["alive"]:
                    print(f"{socket_} socket died: {e}")
                    socket_["alive"] = False
                    time.sleep(0.1)
                return

    def get_info(self, name):
        """
        Generic getter for the latest message from a socket. Name should be one of:
        'command', 'states', 'video', 'config', 'vision'
        """
        return self.sockets[name]["message"]


class CoraClient(CoraInterface):
    """
    :param self:
    :param file: Yaml or Json socket config file
    :param kwargs: host: str, video_port: str, command_port: str, states_port: str, config_port:str
    """

    def __init__(self, filepath: str = None, **kwargs):
        super().__init__(filepath=filepath, **kwargs)
        self.use_controller = kwargs.get("use_controller", False)
        self.use_camera = kwargs.get("use_camera", False)
        self.use_vision = kwargs.get("use_vision", False)

    def _lifecycle_handler(self):
        self._supervisor_running = True
        while self._supervisor_running:
            time.sleep(0.5)
            with self.interface_state_lock:
                if self._interface_state != "disconnected":
                    if not all(
                        [
                            self.sockets["states"]["alive"],
                            self.sockets["command"]["alive"],
                            self.sockets["config"]["alive"],
                        ]
                    ):
                        self._kill()
                        self._interface_state = "disconnected"
                        continue

                if self._interface_state == "disconnected":
                    self._running = True
                    self._create_sockets()
                    self.connect()
                    self._interface_state = "connected"
                    continue

                elif self._interface_state == "connected":
                    self.configure()
                    self._interface_state = "configured"
                    continue

                elif self._interface_state == "configured":
                    self.setup()
                    self._interface_state = "ready"
                    continue

    def _activate(self):
        """
        Docstring for _connect

        :param self: Description
        """
        with self.interface_state_lock:
            self._interface_state = "disconnected"
        threading.Thread(
            target=self._lifecycle_handler, daemon=True, name="lifecycle handler"
        ).start()

    def _connect_with_retry(self, socket_, name, retries=50, delay=0.1):
        for i in range(retries):
            try:
                socket_["socket"].connect(self.arm_host, socket_["port"])
                print(f"Connected {name}")
                return True
            except ConnectionRefusedError:
                time.sleep(delay)
            except OSError as e:
                raise ConnectionError(f"{name} failed: {e}")

        raise ConnectionError(f"{name} failed after {retries} retries")

    def connect(self):
        for socket_name, socket_ in self.sockets.items():
            self._connect_with_retry(socket_, socket_name, retries=100, delay=0.1)
            socket_["alive"] = True

        print("Connected to Cora Server")

    def configure(self):
        for socket_name in ["states_socket", "video_socket", "command_socket"]:
            try:
                socket_ = self.sockets[socket_name]
                if socket_["type"] == "read-only":
                    socket_["socket"].shutdown(socket.SHUT_WR)
                elif socket_["type"] == "write-only":
                    socket_["socket"].shutdown(socket.SHUT_RD)
            except OSError:
                continue

        print("Configured Cora Client")

    def setup(self):
        self.init_threads()
        self.update_options()
        print("Cora Client finished setup")

    def init_threads(self):
        for socket_name in ["video_socket", "states_socket", "vision_socket"]:
            self.sockets[socket_name]["thread"] = {
                "target": None,
                "thread": None,
                "stop_event": threading.Event(),
                "active": False,
                "daemon": True,
            }

        self.sockets["video_socket"]["thread"]["target"] = self.receive_frame
        self.sockets["states_socket"]["thread"]["target"] = self.receive_states
        self.sockets["vision_socket"]["thread"]["target"] = self.receive_vision_poses

    def start_thread(self, name):
        try:
            entry = self.sockets[name]["thread"]

            if entry["thread"] and entry["thread"].is_alive():
                return  # already running

            entry["stop_event"].clear()

            t = threading.Thread(
                target=entry["target"], daemon=entry["daemon"], name=name
            )

            # Set 'thread' dict entry to the thread object
            entry["thread"] = t
            t.start()
        except KeyError:
            return

    def stop_thread(self, name):
        try:
            entry = self.sockets[name]["thread"]

            if not entry["thread"]:
                return

            entry["stop_event"].set()

            if entry["thread"].is_alive():
                entry["thread"].join(timeout=1.0)

            entry["thread"] = None
        except KeyError:
            return

    def reconcile_threads(self, active_set):
        """
        active_set: iterable of thread names that SHOULD be running
        """

        for name, entry in self.sockets.items():
            try:
                should_run = name in active_set

                if should_run and not entry["thread"]["active"]:
                    self.start_thread(name)
                    entry["thread"]["active"] = True

                elif not should_run and entry["thread"]["active"]:
                    self.stop_thread(name)
                    entry["thread"]["active"] = False
            except KeyError:
                continue

    def kill_options(self):
        self.use_controller = False
        self.use_camera = False
        self.use_vision = False

    def cleanup(self):
        # Disable all options
        self.kill_options()

        # Stop all threads
        for name, entry in self.sockets.items():
            self.stop_thread(name)
            entry["thread"]["active"] = False
        return

    def update_options(self):
        """
        Docstring for update_options

        :param self: Description
        """
        active = set()
        if self.use_vision:
            active.add("vision_socket")

        if self.use_camera:
            active.add("video_socket")

        if True:  # always listen to these
            active.add("states_socket")

        self.reconcile_threads(active)

    # ----------------------

    def receive_states(self):
        """
        While socket is connected to server it listens
        over Ethernet TCP socket for state information
        and stores it in the sockets dict in the Cora client object.
        """
        self._socket_receive_loop(
            socket_=self.sockets["states_socket"],
        )

    def get_states(self):
        return self.get_info("states_socket")

    def receive_vision_poses(self):
        self._socket_receive_loop(
            socket_=self.sockets["vision_socket"],
        )

    def get_vision_poses(self):
        return self.get_info("vision_socket")

    def receive_frame(self):
        """
        Continuously receive frames from the video socket and decode them.
        """
        self._socket_receive_loop(
            socket_=self.sockets["video_socket"],
        )

    def get_frame(self):
        return self.get_info("video_socket")

    def send_command(
        self,
        rt,
        space,
        interface_type,
        target,
        gripper_command,
        command,
        predef_pose,
        verbose=True,
    ):
        payload = pt.encode_commands(
            rt, space, interface_type, target, gripper_command, command, predef_pose
        )
        self._socket_send(self.sockets["command_socket"], payload)

    def configure_robot(self, **kwargs):
        self.use_controller = kwargs.get("use_controller")
        self.use_camera = kwargs.get("use_camera")
        self.use_vision = kwargs.get("use_vision")

        self.update_options()

        payload = pt.encode_configs(
            use_controller=self.use_controller,
            use_video=self.use_camera,
            use_vision=self.use_vision,
        )

        self._socket_send(
            self.sockets["config_socket"],
            payload,
        )


class CoraServer(CoraInterface):

    def __init__(self, filepath: str = None, **kwargs):
        super().__init__(filepath=filepath, **kwargs)

        for socket_ in self.sockets.values():
            socket_["connected"] = False

        self.command_lock = threading.Lock()
        self.config_lock = threading.Lock()
        self.use_controller = False
        self.use_video = False
        self.use_vision = False
        self.config_msg = (self.use_controller, self.use_video, self.use_vision)
        self.threaded_sockets = ["command_socket", "config_socket"]
        return

    def start(self):
        self._running = True
        self._create_sockets()
        self.bind()

        threading.Thread(
            target=self._lifecycle_handler,
            daemon=True,
            name="lifecycle handler",
        ).start()

    def connect(self):
        if self._running:
            self.accept_connections()

    def start_threads(self):
        if self._running:
            for socket_name in self.threaded_sockets:
                self.sockets[socket_name]["alive"] = True
                self.sockets[socket_name]["stop"] = threading.Event()
                self.sockets[socket_name]["thread"] = {
                    "target": None,
                    "thread": None,
                    "stop_event": self.sockets[socket_name]["stop"],
                    "active": False,
                    "daemon": True,
                }

            self.sockets["command_socket"]["thread"]["target"] = self.receive_command
            self.sockets["config_socket"]["thread"]["target"] = self.receive_config

            for socket_name in self.threaded_sockets:
                self.sockets[socket_name]["thread"]["thread"] = threading.Thread(
                    target=self.sockets[socket_name]["thread"]["target"],
                    daemon=self.sockets[socket_name]["thread"]["daemon"],
                    name=socket_name.replace("_socket", ""),
                )
                self.sockets[socket_name]["thread"]["thread"].start()

    def stop_threads(self):
        for socket_name in self.threaded_sockets:
            socket_ = self.sockets[socket_name]
            if socket_["thread"] and socket_["thread"]["thread"].is_alive():
                socket_["thread"]["stop_event"].set()
                socket_["thread"]["thread"].join(timeout=1.0)
                socket_["thread"]["thread"] = None

    def _lifecycle_handler(self):
        with self.interface_state_lock:
            self._interface_state = "disconnected"
        while True:
            if self._interface_state != "disconnected":
                if self._running and not all(
                    [
                        self.sockets["command_socket"]["alive"],
                        self.sockets["config_socket"]["alive"],
                    ]
                ):

                    print("Client disconnected")
                    self.stop_threads()
                    self._kill(stop_listening=False)
                    with self.interface_state_lock:
                        self._interface_state = "disconnected"
                        continue

            if self._interface_state == "disconnected":
                self._running = True
                self.connect()
                with self.interface_state_lock:
                    self._interface_state = "connected"
                    continue

            elif self._interface_state == "connected":
                self.start_threads()
                self._interface_state = "ready"
                continue

    def bind(self):
        for socket_ in self.sockets.values():
            socket_["socket"].bind((self.arm_host, socket_["port"]))

        print("Sockets bound")

        for socket_ in self.sockets.values():
            socket_["socket"].listen(1)

        print("Listening for Cora Client ...")

    def accept_connections(self):
        print("Waiting for client connections...")

        while self._running:
            readable, _, _ = select.select(
                [self.sockets[socket_name]["socket"] for socket_name in self.sockets if not self.sockets[socket_name]["connected"]],
                [],
                [],
                1.0,
            )

            for socket_ in readable:
                try:
                    if not socket_["connected"]:
                        conn, addr = socket_["socket"].accept()
                        socket_["socket"] = conn
                        socket_["connected"] = True
                        name = next(
                            name
                            for name, s in self.sockets.items()
                            if s["socket"] == socket_
                        )
                        print(f"Accepted {name} from {addr}")

                except OSError as e:
                    print(f"Accept failed: {e}")

        # Mark alive once all connections are in
        for socket_ in self.sockets.values():
            socket_["alive"] = True

        print("All client connections established")

    def cleanup(self):
        for socket_ in self.sockets.values():
            conn = socket_["socket"]
            if conn:
                try:
                    conn.shutdown(socket.SHUT_RDWR)
                    conn.close()
                    socket_["socket"] = None
                except OSError:
                    print("OSError in cleanup")
                    pass

    def receive_command(self):
        self._socket_receive_loop(
            socket_=self.sockets["command_socket"],
        )

    def get_command(self):
        return self.get_info("command_socket")

    def receive_config(self):
        self._socket_receive_loop(
            socket_=self.sockets["config_socket"],
        )

    def get_config(self):
        return self.get_info("config_socket")

    def send_state(
        self, status, space, end_effector_state, camera_frame_state, gripper_frame_state
    ):
        payload = pt.encode_pose_feedback(
            status, space, end_effector_state, camera_frame_state, gripper_frame_state
        )
        self._socket_send(self.sockets["states_socket"], payload)

    def send_vision_poses(self, ids, poses: NDArray):
        payload = pt.encode_aruco_poses(ids, poses)
        self._socket_send(self.sockets["vision_socket"], payload)

    def send_frame(self, image: NDArray, encoding: str = "jpeg", quality: int = 90):
        """
        Encode a frame and send it over the video TCP socket.
        :param image: numpy array (H x W x C)
        """
        payload = pt.image_to_bytes(image, encoding=encoding, quality=quality)
        self._socket_send(self.sockets["video_socket"], payload)
