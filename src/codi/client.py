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


class CoraInterface:

    def __init__(self, filepath: str = None, **kwargs):
        """
        Docstring for __init__

        :param self: Description
        :param filepath: absolute path to json or yaml config file
        :type filepath: str
        :param kwargs: \n
            host: tcp hostname \n
            video_port: port for video \n
            command_port: port for sending/receiving commands \n
            states_port: port for sending/receiving states \n
            config_port: port for setting/receiving robot param configs \n
            vision_port: port for receiving marker poses
        """

        self._running = False
        self.interface_state_lock = threading.Lock()
        with self.interface_state_lock:
            self._interface_state = "unconnected"

        self.states_alive = False
        self.commands_alive = False
        self.config_alive = False
        self.video_alive = False
        self.vision_alive = False

        if filepath is not None:

            file = Path(filepath)
            extension = file.suffix

            match extension:
                case ".yaml":
                    with open(file, "r") as f:
                        loaded_file = safe_load(f)
                    pass

                case ".json":
                    with open(file, "r") as f:
                        loaded_file = js.load(f)
                    pass
            try:
                self.arm_host = socket.gethostbyname(loaded_file["host"])
                print(f"Host found at {self.arm_host}")

            except socket.gaierror:
                raise ValueError(f"Could not resolve hostname: {loaded_file["host"]}")

            self.video_port = loaded_file["video_port"]
            self.command_port = loaded_file["command_port"]
            self.states_port = loaded_file["states_port"]
            self.config_port = loaded_file["config_port"]
            self.vision_port = loaded_file["vision_port"]

        else:
            try:
                self.arm_host = socket.gethostbyname(kwargs.get("host"))
                print(f"Host found at {self.arm_host}")

            except socket.gaierror:
                raise ValueError(f"Could not resolve hostname: {self.arm_host}")

            self.video_port = kwargs.get("video_port")
            self.command_port = kwargs.get("command_port")
            self.states_port = kwargs.get("states_port")
            self.config_port = kwargs.get("config_port")
            self.vision_port = kwargs.get("vision_port")

        self._set_move_status("initializing")

    def _create_sockets(self):
        self.command_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.states_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.video_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.vision_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.configuration_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def _kill(self, stop_listening=True):
        if self._running is False:
            print("Client is already stopped.")
            return

        print("Stopping Cora client...")

        self._running = False
        time.sleep(0.05)

        # Stop listening sockets
        if stop_listening:
            for sock in (
                self.command_socket,
                self.states_socket,
                self.video_socket,
                self.vision_socket,
                self.configuration_socket,
            ):
                if sock:
                    try:
                        sock.shutdown(socket.SHUT_RDWR)
                        sock.close()
                    except OSError:
                        pass

        self.cleanup()

        return

    def _set_move_status(self, status: str):
        statuses = ["idle", "moving", "homing", "initializing"]
        try:
            self.move_status = statuses[statuses.index(status)]
        except ValueError:
            raise ValueError(f"Status '{status}' unknown")

    def _end_interface(self):
        self._kill()
        self._supervisor_running = False

    def _is_socket_alive(self, connection, timeout=0.2):
        if connection is None:  
            return False

        try:
            fd = sock.fileno()
            if fd < 0:
                print('incorrect fd')
                return False

            _, _, errored = select.select([sock], [], [sock], timeout)
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

    def _socket_receive_loop(
        self, sock, alive_flag_attr, decode_func=None, store_attr=None, stop_event=None
    ):
        """
        Generic method to continuously receive data from a socket.

        :param sock: socket object to read from
        :param alive_flag_attr: string, name of the alive flag attribute (e.g., 'states_alive')
        :param decode_func: function to decode raw bytes into data
        :param store_attr: string, name of the attribute to store decoded data
        :param stop_event: threading.Event to stop the loop (optional)
        """
        print('initiating receive loop')
        while self._running and (stop_event is None or not stop_event.is_set()):
            try:
                if self._is_socket_alive(sock, 1) is False:
                    raise OSError("socket not alive")
                else:
                    setattr(self, alive_flag_attr, True)
                    raw_data = self._receive(sock)

                if not raw_data:
                    raise OSError("socket closed")

                if decode_func and store_attr:
                    decoded = decode_func(raw_data)
                    setattr(self, store_attr, decoded)

            except OSError as e:
                if getattr(self, alive_flag_attr):
                    print(f"{alive_flag_attr} socket died: {e}")
                    setattr(self, alive_flag_attr, False)
                    time.sleep(0.1)
                continue

    def _socket_send(self, sock, alive_flag_attr, payload):
        """
        Generic method to send data over a socket safely.

        :param sock: socket object
        :param alive_flag_attr: string, name of alive flag attribute
        :param payload: bytes to send
        """
        if self._running:
            try:
                if self._is_socket_alive(sock, 1) is False:
                    raise OSError("socket not alive")
                else:
                    setattr(self, alive_flag_attr, True)
                    self._send(sock, payload)
            except OSError as e:
                if getattr(self, alive_flag_attr):
                    print(f"{alive_flag_attr} socket died: {e}")
                    setattr(self, alive_flag_attr, False)
                    time.sleep(0.1)
                return


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
        self.threads = dict()
        self.states = None
        self.last_frame = None
        self.aruco_poses = None

    def _lifecycle_handler(self):
        self._supervisor_running = True
        while self._supervisor_running:
            time.sleep(0.5)
            with self.interface_state_lock:
                if self._interface_state != "disconnected":
                    if not all(
                        [self.states_alive, self.commands_alive, self.config_alive]
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

    def _connect_with_retry(self, sock, addr, name, retries=50, delay=0.1):
        for i in range(retries):
            try:
                sock.connect(addr)
                print(f"Connected {name}")
                return True
            except ConnectionRefusedError:
                time.sleep(delay)
            except OSError as e:
                raise ConnectionError(f"{name} failed: {e}")

        raise ConnectionError(f"{name} failed after {retries} retries")

    def connect(self):
        self._connect_with_retry(
            self.command_socket, (self.arm_host, self.command_port), "command"
        )

        self._connect_with_retry(
            self.states_socket, (self.arm_host, self.states_port), "states"
        )

        self._connect_with_retry(
            self.video_socket, (self.arm_host, self.video_port), "video"
        )

        self._connect_with_retry(
            self.vision_socket, (self.arm_host, self.vision_port), "vision"
        )

        self._connect_with_retry(
            self.configuration_socket, (self.arm_host, self.config_port), "config"
        )

        self.states_alive = True
        self.commands_alive = True
        self.config_alive = True
        self.video_alive = True
        self.vision_alive = True

        print("Connected to Cora Server")

    def configure(self):
        self.video_socket.shutdown(socket.SHUT_WR)
        self.states_socket.shutdown(socket.SHUT_WR)
        self.command_socket.shutdown(socket.SHUT_RD)
        print("Configured Cora Client")

    def setup(self):
        self.init_threads()
        self.update_options()
        print("Cora Client finished setup")

    def init_threads(self):
        self.threads = {
            "video": {
                "target": self.receive_frame,
                "thread": None,
                "stop_event": threading.Event(),
                "active": False,
                "daemon": True,
            },
            "states": {
                "target": self.receive_states,
                "thread": None,
                "stop_event": threading.Event(),
                "active": False,
                "daemon": True,
            },
            "vision_poses": {
                "target": self.receive_vision_poses,
                "thread": None,
                "stop_event": threading.Event(),
                "active": False,
                "daemon": True,
            },
        }

    def start_thread(self, name):
        entry = self.threads[name]

        if entry["thread"] and entry["thread"].is_alive():
            return  # already running

        entry["stop_event"].clear()

        t = threading.Thread(target=entry["target"], daemon=entry["daemon"], name=name)

        # Set 'thread' dict entry to the thread object
        entry["thread"] = t
        t.start()

    def stop_thread(self, name):
        entry = self.threads[name]

        if not entry["thread"]:
            return

        entry["stop_event"].set()

        if entry["thread"].is_alive():
            entry["thread"].join(timeout=1.0)

        entry["thread"] = None

    def reconcile_threads(self, active_set):
        """
        active_set: iterable of thread names that SHOULD be running
        """

        for name, entry in self.threads.items():
            should_run = name in active_set

            if should_run and not entry["active"]:
                self.start_thread(name)
                entry["active"] = True

            elif not should_run and entry["active"]:
                self.stop_thread(name)
                entry["active"] = False

    def kill_options(self):
        self.use_controller = False
        self.use_camera = False
        self.use_vision = False

    def cleanup(self):
        # Disable all options
        self.kill_options()

        # Stop all threads
        for name, entry in self.threads.items():
            self.stop_thread(name)
            entry["active"] = False
        return

    def update_options(self):
        """
        Docstring for update_options

        :param self: Description
        """
        active = set()
        if self.use_vision:
            active.add("vision_poses")

        if self.use_camera:
            active.add("video")

        if True:  # always listen to these
            active.add("states")

        self.reconcile_threads(active)

    # ----------------------

    def receive_states(self):
        """
        While socket is connected to server it listens
        over Ethernet TCP socket for state information
        and stores it as self.states in the Cora client object.
        """
        stop_event = self.threads["states"]["stop_event"]
        self._socket_receive_loop(
            sock=self.states_socket,
            alive_flag_attr="states_alive",
            decode_func=pt.decode_pose_feedback,
            store_attr="states",
            stop_event=stop_event,
        )

    def get_states(self, verbose=True):
        """
        Get self.states from Cora client object.
        """
        return self.states

    def receive_vision_poses(self):
        stop_event = self.threads["vision_poses"]["stop_event"]
        self._socket_receive_loop(
            sock=self.vision_socket,
            alive_flag_attr="vision_alive",
            decode_func=pt.decode_aruco_poses,
            store_attr="aruco_poses",
            stop_event=stop_event,
        )

    def get_vision_poses(self):
        return self.aruco_poses

    def receive_frame(self):
        """
        Continuously receive frames from the video socket and decode them.
        """
        stop_event = self.threads["video"]["stop_event"]
        self._socket_receive_loop(
            sock=self.video_socket,
            alive_flag_attr="video_alive",
            decode_func=pt.bytes_to_image,
            store_attr="last_frame",
            stop_event=stop_event
            )

    def get_frame(self):
        return self.last_frame

    def send_command(
        self, rt, space, interface_type, target, gripper_command, command, predef_pose, verbose=True
    ):
        payload = pt.encode_commands(
            rt, space, interface_type, target, gripper_command, command, predef_pose
        )
        self._socket_send(self.command_socket, "commands_alive", payload)

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
            self.configuration_socket,
            "config_alive",
            payload,
        )


class CoraServer(CoraInterface):

    # TODO: Implement cora server derived class with appropriate methods

    def __init__(self, filepath: str = None, **kwargs):
        super().__init__(filepath=filepath, **kwargs)
        self.command_conn = None
        self.states_conn = None
        self.video_conn = None
        self.vision_conn = None
        self.config_conn = None
        self.command_msg = None
        self.command_lock = threading.Lock()
        self.config_lock = threading.Lock()
        self.use_controller = False
        self.use_video = False
        self.use_vision = False
        self.config_msg = (self.use_controller, self.use_video, self.use_vision)
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
            self.commands_alive = True
            self.config_alive = True
            self.command_stop = threading.Event()
            self.config_stop = threading.Event()
            self.command_thread = threading.Thread(
                target=self.receive_command,
                daemon=True,
                name="commands",
            )
            self.command_thread.start()

            self.config_thread = threading.Thread(
                target=self.receive_config,
                daemon=True,
                name="config",
            )
            self.config_thread.start()

    def stop_threads(self):
        self.config_stop.set()
        self.command_stop.set()
        self.command_thread.join()
        self.config_thread.join()

    def _lifecycle_handler(self):
        with self.interface_state_lock:
            self._interface_state = 'disconnected'
        while True:
            if self._interface_state != "disconnected":
                if self._running and not all(
                    [
                        self.commands_alive,
                        self.config_alive,
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
        self.command_socket.bind((self.arm_host, self.command_port))
        self.states_socket.bind((self.arm_host, self.states_port))
        self.video_socket.bind((self.arm_host, self.video_port))
        self.vision_socket.bind((self.arm_host, self.vision_port))
        self.configuration_socket.bind((self.arm_host, self.config_port))

        print("Sockets bound")

        self.command_socket.listen(1)
        self.states_socket.listen(1)
        self.video_socket.listen(1)
        self.vision_socket.listen(1)
        self.configuration_socket.listen(1)

        print("Listening for Cora Client ...")

    def accept_connections(self):
        sockets = {
            self.command_socket: "command_conn",
            self.states_socket: "states_conn",
            self.video_socket: "video_conn",
            self.vision_socket: "vision_conn",
            self.configuration_socket: "config_conn",
        }

        print("Waiting for client connections...")

        while self._running and sockets:
            readable, _, _ = select.select(list(sockets.keys()), [], [], 1.0)

            for sock in readable:
                try:
                    conn, addr = sock.accept()
                    name = sockets[sock]
                    setattr(self, name, conn)
                    sockets.pop(sock)

                    print(f"Accepted {name} from {addr}")

                except OSError as e:
                    print(f"Accept failed: {e}")

        # Mark alive once all connections are in
        self.states_alive = True
        self.commands_alive = True
        self.config_alive = True
        self.video_alive = True
        self.vision_alive = True

        print("All client connections established")

    def setup(self):
        self.accept_connections()
        threading.Thread(
            target=self.receive_command, daemon=True, name="commands"
        ).start()
        threading.Thread(target=self.receive_config, daemon=True, name="config").start()
        return

    def cleanup(self):
        for name in (
            "command_conn",
            "states_conn",
            "video_conn",
            "vision_conn",
            "config_conn",
        ):
            conn = getattr(self, name)
            if conn:
                try:
                    conn.shutdown(socket.SHUT_RDWR)
                    conn.close()
                except OSError:
                    print("OSError in cleanup")
                    pass
            setattr(self, name, None)

    def receive_command(self):
        self._socket_receive_loop(
            sock=self.command_conn,
            alive_flag_attr="commands_alive",
            decode_func=pt.decode_commands,
            store_attr="command_msg",
            stop_event=self.command_stop,
        )

    def get_command(self):
        return self.command_msg

    def receive_config(self):
        self._socket_receive_loop(
            sock=self.config_conn,
            alive_flag_attr="config_alive",
            decode_func=pt.decode_configs,
            store_attr="config_msg",
            stop_event=self.config_stop,
        )

    def get_config(self):
        return self.config_msg

    def send_state(
        self, status, space, end_effector_state, camera_frame_state, gripper_frame_state
    ):
        payload = pt.encode_pose_feedback(
            status, space, end_effector_state, camera_frame_state, gripper_frame_state
        )
        self._socket_send(self.states_conn, "states_alive", payload)

    def send_vision_poses(self, ids, poses: NDArray):
        payload = pt.encode_aruco_poses(ids, poses)
        self._socket_send(self.vision_conn, "vision_alive", payload)

    def send_frame(self, image: NDArray, encoding: str = "jpeg", quality: int = 90):
        """
        Encode a frame and send it over the video TCP socket.
        :param image: numpy array (H x W x C)
        """
        payload = pt.image_to_bytes(image, encoding=encoding, quality=quality)
        self._socket_send(self.video_conn, "video_alive", payload)