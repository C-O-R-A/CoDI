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

from codi.exeptions import ProtocolSchemaError, ProtocolSemanticError
from codi.messages import (
    CommandMessage,
    FeedbackMessage,
    ImageMessage,
    ConfigMessage,
    JointStateObject,
    TransformObject,
    FeedbackObject,
)


class CoraInterface:
    """Base class providing low-level socket management for Cora robot communication.

    Manages five TCP sockets: command, states, video, config, and vision.
    Subclasses :class:`CoraClient` and :class:`CoraServer` extend this with
    client- and server-side lifecycle logic respectively.

    :param filepath: Absolute path to a YAML or JSON config file containing
        ``host`` and ``ports`` keys. If omitted, pass host and ports as kwargs.
    :type filepath: str, optional
    :param kwargs:
        - **host** (*str*) -- TCP hostname or IP of the robot.
        - **ports** (*dict*) -- Mapping of port keys to port numbers:

          - ``video_port`` -- port for video streaming
          - ``command_port`` -- port for sending/receiving commands
          - ``states_port`` -- port for sending/receiving robot states
          - ``config_port`` -- port for setting/receiving robot configuration
          - ``vision_port`` -- port for receiving ArUco marker poses

    :raises ValueError: If the provided hostname cannot be resolved.

    Example config YAML::

        host: 192.168.1.100
        ports:
          command_port: 5000
          states_port: 5001
          video_port: 5002
          config_port: 5003
          vision_port: 5004
    """

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
                "model": CommandMessage,
                "type": "write-only",
            },
            "states_socket": {
                "model": FeedbackMessage,
                "type": "read-only",
            },
            "video_socket": {
                "model": ImageMessage,
                "type": "read-only",
            },
            "config_socket": {
                "model": ConfigMessage,
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
                socket_["port"] = ports.get(socket_name.replace("_socket", "_port"))

        except socket_.gaierror:
            raise ValueError(f"Could not resolve hostname: {host}")

        self._set_move_status("initializing")

    def _create_sockets(self):
        """Instantiate a new TCP socket object for each entry in :attr:`sockets`.

        Called before each connection attempt to ensure fresh socket objects.
        All sockets use ``AF_INET`` and ``SOCK_STREAM`` (TCP).
        """
        for socket_val in self.sockets.values():
            socket_val["socket"] = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def _kill(self, stop_listening=True):
        """Shut down all sockets and stop the receive loops.

        Sets ``_running`` to ``False``, optionally shuts down and closes every
        socket, then calls :meth:`cleanup`.

        :param stop_listening: If ``True`` (default), shut down and close all
            sockets. Pass ``False`` on the server side when you want to keep
            the listening sockets open for the next client connection.
        :type stop_listening: bool
        """
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

    def _set_move_status(self, status: int):
        """Validate and set the robot's current move status.

        :param status: Status string to validate via :func:`validation.status`.
        :type status: str
        """
        self.move_status = status

    def _end_interface(self):
        """Stop the interface and the supervisor loop.

        Calls :meth:`_kill` and sets ``_supervisor_running`` to ``False``.
        """
        self._kill()
        self._supervisor_running = False

    def _is_socket_alive(self, connection, timeout=0.2):
        """Check whether a socket connection is still usable.

        Uses :func:`select.select` to poll for error conditions.

        :param connection: The socket to probe.
        :type connection: socket.socket or None
        :param timeout: Seconds to wait for the select call.
        :type timeout: float
        :returns: ``True`` if the socket appears healthy, ``False`` otherwise.
        :rtype: bool
        """
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
        """Receive exactly ``n`` bytes from a socket.

        Loops on :meth:`socket.recv` until all ``n`` bytes have been
        accumulated, handling partial reads transparently.

        :param connection: The socket to read from.
        :type connection: socket.socket
        :param n: Exact number of bytes to receive.
        :type n: int
        :returns: The received bytes, or ``None`` if the connection closes
            before ``n`` bytes are read.
        :rtype: bytes or None
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
        """Receive a length-prefixed message from a socket.

        Reads a 4-byte big-endian length header, then reads exactly that many
        bytes of payload. This framing protocol is used for all CoDI messages.

        :param connection: The socket to read from.
        :type connection: socket.socket
        :returns: The raw payload bytes, or ``None`` if the connection is
            closed or the length field is invalid.
        :rtype: bytes or None
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
        """Send a length-prefixed message over a socket.

        Prepends a 4-byte big-endian length header to ``payload`` and sends
        the whole buffer atomically with :meth:`socket.sendall`.

        :param connection: The socket to write to.
        :type connection: socket.socket
        :param payload: Raw bytes to send.
        :type payload: bytes
        """
        length = len(payload)
        connection.sendall(length.to_bytes(4, "big") + payload)

    def _socket_receive_loop(self, socket_):
        """Continuously receive and decode messages from a socket.

        Runs until ``_running`` is ``False`` or the thread's stop event is
        set. Each successfully decoded message is stored in
        ``socket_["message"]`` and can be retrieved via :meth:`get_info`.

        If the socket dies, the loop marks it as not alive, sleeps briefly,
        and then continues so the lifecycle handler can reconnect.

        :param socket_: Entry from :attr:`sockets` containing at minimum
            ``socket``, ``decoder``, ``alive``, ``message``, and ``thread``
            keys.
        :type socket_: dict
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

                socket_["message"] = pt.decode(raw_data, socket_["model"])

            except OSError as e:
                if socket_["alive"]:
                    print(f"socket died: {e}")
                    socket_["alive"] = False
                    time.sleep(0.1)
                continue

    def _socket_send(self, socket_, payload):
        """Send a payload over a socket, encoding it if necessary.

        If ``payload`` is not already ``bytes``, it is passed through the
        socket's encoder first. Skips the send silently if ``_running`` is
        ``False`` or the socket is not alive.

        :param socket_: Entry from :attr:`sockets` containing ``socket``,
            ``encoder``, and ``alive`` keys.
        :type socket_: dict
        :param payload: Data to send; will be encoded if not already ``bytes``.
        """
        if self._running:
            try:
                if self._is_socket_alive(socket_["socket"], 1) is False:
                    raise OSError("socket not alive")
                else:
                    socket_["alive"] = True
                    self._send(socket_["socket"], payload)
            except OSError as e:
                if socket_["alive"]:
                    print(f"socket died: {e}")
                    socket_["alive"] = False
                    time.sleep(0.1)
                return

    def get_info(self, name):
        """Return the most recently received message from a named socket.

        :param name: Socket key without the ``_socket`` suffix, e.g.
            ``'command'``, ``'states'``, ``'video'``, ``'config'``,
            or ``'vision'``.

            .. note::
                The full dict key is ``name + '_socket'``, so pass
                ``'states'`` to read from ``states_socket``.

        :type name: str
        :returns: The last decoded message stored by the receive loop, or
            ``None`` if no message has arrived yet.
        """
        return self.sockets[name]["message"]


class CoraClient(CoraInterface):
    """High-level client that connects to a running :class:`CoraServer`.

    Extends :class:`CoraInterface` with a lifecycle handler that
    automatically reconnects, configures, and sets up the robot connection
    after any drop. Provides the public API for sending commands, receiving
    states/frames/vision poses, and updating robot options.

    :param filepath: Absolute path to a YAML or JSON config file.
    :type filepath: str, optional
    :param kwargs:
        - **host** (*str*) -- Robot TCP hostname.
        - **ports** (*dict*) -- Port mapping (see :class:`CoraInterface`).
        - **use_controller** (*bool*) -- Enable gamepad/controller input.
          Default ``False``.
        - **use_camera** (*bool*) -- Enable video streaming. Default ``False``.
        - **use_vision** (*bool*) -- Enable ArUco marker detection.
          Default ``False``.
    """

    def __init__(self, filepath: str = None, **kwargs):
        super().__init__(filepath=filepath, **kwargs)
        self.use_controller = kwargs.get("use_controller", False)
        self.use_camera = kwargs.get("use_camera", False)
        self.use_vision = kwargs.get("use_vision", False)

    def _lifecycle_handler(self):
        """Supervise the connection state machine in a background thread.

        Cycles through the states ``disconnected`` → ``connected`` →
        ``configured`` → ``ready``, calling :meth:`connect`,
        :meth:`configure`, and :meth:`setup` at the appropriate transitions.
        If any of the core sockets die the handler tears down and reconnects
        automatically.
        """
        self._supervisor_running = True
        while self._supervisor_running:
            time.sleep(0.5)
            with self.interface_state_lock:
                if self._interface_state != "disconnected":
                    if not all(
                        [
                            self.sockets["states_socket"]["alive"],
                            self.sockets["command_socket"]["alive"],
                            self.sockets["config_socket"]["alive"],
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
        """Start the lifecycle handler and begin the connection process.

        Sets ``_interface_state`` to ``'disconnected'`` and launches
        :meth:`_lifecycle_handler` as a daemon thread. This is the primary
        entry point for bringing a :class:`CoraClient` online.
        """
        with self.interface_state_lock:
            self._interface_state = "disconnected"
        threading.Thread(
            target=self._lifecycle_handler, daemon=True, name="lifecycle handler"
        ).start()

    def _connect_with_retry(self, socket_, name, retries=50, delay=0.1):
        """Attempt to connect a single socket, retrying on refusal.

        :param socket_: Entry from :attr:`sockets` containing ``socket``
            and ``port`` keys.
        :type socket_: dict
        :param name: Human-readable name used in log/error messages.
        :type name: str
        :param retries: Maximum number of connection attempts.
        :type retries: int
        :param delay: Seconds to wait between attempts.
        :type delay: float
        :raises ConnectionError: If the connection fails for a non-refusal
            reason, or if all retries are exhausted.
        """
        for i in range(retries):
            try:
                socket_["socket"].connect((self.arm_host, socket_["port"]))
                print(f"Connected {name}")
                return True
            except ConnectionRefusedError:
                time.sleep(delay)
            except OSError as e:
                raise ConnectionError(f"{name} failed: {e}")

        raise ConnectionError(f"{name} failed after {retries} retries")

    def connect(self):
        """Connect all sockets to the server with automatic retry.

        Iterates over every entry in :attr:`sockets` and calls
        :meth:`_connect_with_retry`. Marks each socket as alive after a
        successful connection.

        :raises ConnectionError: If any socket cannot connect within the
            retry budget.
        """
        for socket_name, socket_ in self.sockets.items():
            self._connect_with_retry(socket_, socket_name, retries=100, delay=0.1)
            socket_["alive"] = True

        print("Connected to Cora Server")

    def configure(self):
        """Half-close directional sockets to enforce read-only/write-only modes.

        Shuts down the write end of read-only sockets and the read end of
        write-only sockets, preventing accidental use in the wrong direction.
        Applies to ``states_socket``, ``video_socket``, and ``command_socket``.
        """
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
        """Initialise threads and apply current option flags.

        Called once the connection is configured. Runs :meth:`init_threads`
        to register thread targets, then :meth:`update_options` to start
        whichever receive threads are required.
        """
        self.init_threads()
        self.update_options()
        print("Cora Client finished setup")

    def init_threads(self):
        """Register thread metadata and targets for the receive sockets.

        Populates the ``thread`` sub-dict for ``video_socket``,
        ``states_socket``, and ``vision_socket`` with targets pointing to
        :meth:`receive_frame`, :meth:`receive_states`, and
        :meth:`receive_vision_poses` respectively.

        Does **not** start any threads; call :meth:`start_thread` or
        :meth:`update_options` for that.
        """
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
        """Start the receive thread for a named socket if it is not already running.

        Clears the stop event and spawns a new daemon thread using the
        target registered in :meth:`init_threads`.

        :param name: Socket key, e.g. ``'video_socket'`` or ``'states_socket'``.
        :type name: str
        """
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
        """Stop the receive thread for a named socket.

        Sets the stop event, joins the thread with a 1-second timeout, and
        clears the thread reference.

        :param name: Socket key to stop.
        :type name: str
        """
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
        """Start or stop socket threads to match a desired active set.

        Compares each socket's current running state against ``active_set``
        and calls :meth:`start_thread` or :meth:`stop_thread` as needed.
        Sockets without a ``thread`` sub-dict are silently skipped.

        :param active_set: Iterable of socket names that **should** be running,
            e.g. ``{'states_socket', 'video_socket'}``.
        :type active_set: iterable of str
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
        """Disable all optional feature flags.

        Sets :attr:`use_controller`, :attr:`use_camera`, and
        :attr:`use_vision` to ``False``. Called by :meth:`cleanup` before
        tearing down threads.
        """
        self.use_controller = False
        self.use_camera = False
        self.use_vision = False

    def cleanup(self):
        """Disable all options and stop all running threads.

        Called automatically by :meth:`_kill`. Safe to call multiple times.
        """
        # Disable all options
        self.kill_options()

        # Stop all threads
        for name, entry in self.sockets.items():
            self.stop_thread(name)
            entry["thread"]["active"] = False
        return

    def update_options(self):
        """Reconcile running threads with current feature flags.

        Builds the set of sockets that should be active based on
        :attr:`use_vision`, :attr:`use_camera`, and always-on
        ``states_socket``, then calls :meth:`reconcile_threads`.

        Call this after changing any ``use_*`` attribute to apply the update.
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
        """Continuously receive robot state messages from the server.

        Runs :meth:`_socket_receive_loop` on ``states_socket``. Decoded
        messages are stored in ``sockets['states_socket']['message']`` and
        accessible via :meth:`get_states`.

        Intended to run in the dedicated states thread started by
        :meth:`start_thread`.
        """
        self._socket_receive_loop(
            socket_=self.sockets["states_socket"],
        )

    def get_states(self):
        """Return the most recently received robot state message.

        :returns: Decoded pose feedback, or ``None`` if none has arrived yet.
        """
        feedback: FeedbackMessage = self.get_info("states_socket")
        feedback_object = FeedbackObject()
        
        # Joint States
        joint_states = feedback.joint_states
        joint_states_dict = {}
        for i, _ in enumerate(joint_states.name):
            name = joint_states.name[i]
            joint_position = joint_states.position[i]
            velocity = joint_states.velocity[i]
            effort = joint_states.effort[i]

            joint_states_obj = JointStateObject(joint_position, velocity, effort)
            joint_states_dict[name] = joint_states_obj
        
        feedback_object.joint_states = joint_states_dict
        
        # Transforms
        transforms = feedback.transforms
        robot_states = []
        
        for tf in transforms:
            parent = tf.header.frame_id
            child = tf.child_frame_id
            tf_position = tf.transform.translation
            orientation = tf.transdform.rotation
            
            transforms_obj = TransformObject(
                parent,
                child,
                tf_position,
                orientation
            )
            robot_states.append(transforms_obj)

        feedback_object.transforms = robot_states    
        
        feedback_object.status = feedback.status
        return feedback_object

    def receive_frame(self):
        """Continuously receive and decode video frames from the server.

        Runs :meth:`_socket_receive_loop` on ``video_socket``. Decoded
        frames are accessible via :meth:`get_frame`.

        Intended to run in the dedicated video thread started by
        :meth:`start_thread`.
        """
        self._socket_receive_loop(
            socket_=self.sockets["video_socket"],
        )

    def get_frame(self):
        """Return the most recently received video frame.

        :returns: Decoded image (numpy array), or ``None`` if none has
            arrived yet.
        :rtype: numpy.ndarray or None
        """
        return self.get_info("video_socket")

    def send_command(
        self,
        **kwargs,
    ):
        """Encode and send a motion command to the server.

        All parameters are forwarded directly to :func:`protocol.encode_commands`
        before being sent over ``command_socket``.

        :param:     pose_command
        :param:     joint_command
        :param:     interface_type
        :param:     rt
        :param:     target 
        :param:     gripper_command 
        :param:     predef_pose
        """
        try:
            payload = pt.encode(CommandMessage(**kwargs))
            
        except Exception as e:
            raise ProtocolSchemaError(
                f"Invalid command: {e}"
            ) from e
        self._socket_send(self.sockets["command_socket"], payload)

    def configure_robot(self, **kwargs):
        """Update feature flags and send the new configuration to the server.

        Updates :attr:`use_controller`, :attr:`use_camera`, and
        :attr:`use_vision` from ``kwargs``, calls :meth:`update_options` to
        reconcile threads, then encodes and sends the config payload over
        ``config_socket``.

        :param kwargs:
            - **use_controller** (*bool*) -- Enable gamepad input.
            - **use_camera** (*bool*) -- Enable video streaming.
            - **use_vision** (*bool*) -- Enable ArUco marker detection.
        """
        self.use_camera = kwargs.get("use_camera")

        self.update_options()

        config_msg = ConfigMessage(**kwargs)
        payload = pt.encode(config_msg)
        self._socket_send(
            self.sockets["config_socket"],
            payload,
        )


class CoraServer(CoraInterface):
    """Server-side interface that accepts connections from a :class:`CoraClient`.

    Binds all five sockets, listens for the client, and exposes methods to
    push state, vision, and video data back to the client while receiving
    commands and configuration updates.

    The server's lifecycle handler automatically re-accepts a new client
    connection after a disconnect, making it resilient to client restarts.

    :param filepath: Absolute path to a YAML or JSON config file.
    :type filepath: str, optional
    :param kwargs: Host and ports mapping (see :class:`CoraInterface`).
    """

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
        """Bind all sockets and launch the lifecycle handler.

        This is the primary entry point for bringing a :class:`CoraServer`
        online. After this call the server waits for a client to connect.
        """
        self._running = True
        self._create_sockets()
        self.bind()

        threading.Thread(
            target=self._lifecycle_handler,
            daemon=True,
            name="lifecycle handler",
        ).start()

    def connect(self):
        """Accept incoming client connections if the server is running.

        Delegates to :meth:`accept_connections`.
        """
        if self._running:
            self.accept_connections()

    def start_threads(self):
        """Start receive threads for ``command_socket`` and ``config_socket``.

        Populates thread metadata for each socket in :attr:`threaded_sockets`
        and spawns daemon threads targeting :meth:`receive_command` and
        :meth:`receive_config` respectively.
        """
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
        """Stop all threads in :attr:`threaded_sockets`.

        Sets each thread's stop event, joins with a 1-second timeout, and
        clears the thread reference.
        """
        for socket_name in self.threaded_sockets:
            socket_ = self.sockets[socket_name]
            if socket_["thread"] and socket_["thread"]["thread"].is_alive():
                socket_["thread"]["stop_event"].set()
                socket_["thread"]["thread"].join(timeout=1.0)
                socket_["thread"]["thread"] = None

    def _lifecycle_handler(self):
        """Supervise the server connection state machine in a background thread.

        Cycles through ``disconnected`` → ``connected`` → ``ready``,
        calling :meth:`connect` and :meth:`start_threads` at the appropriate
        transitions. If the command or config socket dies, tears down and
        waits for the next client automatically.
        """
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
        """Bind and begin listening on all sockets.

        Calls :meth:`socket.bind` and :meth:`socket.listen` (backlog 1) on
        every socket using the configured host and port. Prints a confirmation
        when all sockets are listening.
        """
        for socket_ in self.sockets.values():
            socket_["socket"].bind((self.arm_host, socket_["port"]))

        print("Sockets bound")

        for socket_ in self.sockets.values():
            socket_["socket"].listen(1)

        print("Listening for Cora Client ...")

    def accept_connections(self):
        """Accept one client connection on each socket.

        Uses :func:`select.select` to wait non-blockingly for incoming
        connections. Loops until all sockets have an accepted connection or
        ``_running`` becomes ``False``. Marks every socket as alive once all
        connections are established.
        """
        print("Waiting for client connections...")

        while self._running and not all(
            socket_["connected"] for socket_ in self.sockets.values()
        ):
            readable, _, _ = select.select(
                [
                    self.sockets[socket_name]["socket"]
                    for socket_name in self.sockets
                    if not self.sockets[socket_name]["connected"]
                ],
                [],
                [],
                1.0,
            )

            for name, socket_ in self.sockets.items():
                if socket_["socket"] in readable:
                    try:
                        conn, addr = socket_["socket"].accept()
                        socket_["socket"] = conn
                        socket_["connected"] = True
                        print(f"Accepted {name} from {addr}")

                    except Exception:
                        continue

        # Mark alive once all connections are in
        for socket_ in self.sockets.values():
            socket_["alive"] = True

        print("All client connections established")

    def cleanup(self):
        """Shut down and close all accepted client connections.

        Iterates over :attr:`sockets`, calling ``shutdown`` and ``close`` on
        each connected socket. Silently ignores ``OSError`` to handle
        already-closed sockets gracefully.
        """
        for socket_ in self.sockets.values():
            conn = socket_["socket"]
            if conn is not None:
                try:
                    conn.shutdown(socket.SHUT_RDWR)
                    conn.close()
                    socket_["socket"] = None
                except OSError as e:
                    print(f"OSError in cleanup: {e}")
                    pass

    def receive_command(self):
        """Continuously receive motion commands from the client.

        Runs :meth:`_socket_receive_loop` on ``command_socket``. Decoded
        commands are stored in ``sockets['command_socket']['message']`` and
        retrievable via :meth:`get_command`.

        Intended to run in the dedicated command thread started by
        :meth:`start_threads`.
        """
        self._socket_receive_loop(
            socket_=self.sockets["command_socket"],
        )

    def get_command(self):
        """Return the most recently received command from the client.

        :returns: Decoded command data, or ``None`` if no command has arrived.
        """
        return self.get_info("command_socket")

    def receive_config(self):
        """Continuously receive configuration updates from the client.

        Runs :meth:`_socket_receive_loop` on ``config_socket``. Decoded
        configs are accessible via :meth:`get_config`.

        Intended to run in the dedicated config thread started by
        :meth:`start_threads`.
        """
        self._socket_receive_loop(
            socket_=self.sockets["config_socket"],
        )

    def get_config(self):
        """Return the most recently received configuration from the client.

        :returns: Decoded configuration tuple/object, or ``None`` if none
            has arrived yet.
        """
        return self.get_info("config_socket")

    def send_state(
        self, transforms: dict, jointstates: dict, status: int
    ):
        """Encode and send the current robot state to the client.

        :param transforms: transforms of the robot as dict
        :param jointstates: joint states of the robot as a dict
        :param status: status of the robot
        """
        feedback = {
            "transforms": transforms,
            "joint_states": jointstates,
            "status": status
        }
        feedback_msg = FeedbackMessage.model_validate(feedback)
        payload = pt.encode(feedback_msg)
        self._socket_send(self.sockets["states_socket"], payload)

    def send_frame(self, image: NDArray, encoding: str = "jpeg", quality: int = 90):
        """Encode and send a video frame to the client.

        :param image: RGB image as a NumPy array with shape ``(H, W, C)``.
        :type image: numpy.ndarray
        :param encoding: Codec to use for compression, e.g. ``'jpeg'`` or
            ``'png'``. Default ``'jpeg'``.
        :type encoding: str
        :param quality: Compression quality (0-100). Only meaningful for
            lossy codecs like JPEG. Default ``90``.
        :type quality: int
        """
        payload = pt.image_to_bytes(image, encoding=encoding, quality=quality)
        self._socket_send(self.sockets["video_socket"], payload)