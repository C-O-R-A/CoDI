"""CoDI (Cora Desktop Interface)

CoDI is an SDK developed by ... to interface with the open source Cora cobot.
    https://github.com/machine0herald/CoDI
;-)
"""

import numpy as np
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import socket
import threading
import matplotlib

from . import utils as ut
from . import exeptions

class CoraInterface:

    # TODO: Make it so that a program can be exited without killing the socket threads. 
    # i.e. ready to use client objects that are always in connection with the server once started.
    # this way other standard programs can also be included in the sdk, 
    # like a controller interface for use with bluetooth controllers

    # TODO: Add initialization step at startup that configures what 
    # optional nodes need to be launched on the robot. 
    # i.e. vision and bt controller nodes. this way when a program is terminated, 
    # these optional nodes are killed and possibly (re)started on another program's startup.

    def __init__(self, **kwargs):
        self._running = False
        self.host = kwargs.get("host")
        self.video_port = kwargs.get('video_port')
        self.command_port = kwargs.get('command_port')
        self.states_port = kwargs.get('states_port')
        self.config_port = kwargs.get('config_port')
        self.move_status = 'idle'  # 'idle', 'moving', 'at_target', 'error', 'homing'
        self.video_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)        # TCP socket for video
        self.command_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)     # TCP socket for commands
        self.states_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)       # TCP socket for states
        self.configuration_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # TCP socket for configurations
        self.extra_threads = dict()

        try:
            self.arm_host = socket.gethostbyname(self.arm_host)

        except socket.gaierror:
            raise ValueError(f"Could not resolve hostname: {self.arm_host}")
        
    def _init_extra_threads(self):
        self.extra_threads = {
            "video": {
                "target": self.video,
                "thread": None,
                "stop_event": threading.Event(),
                "active": False,
                "daemon": True
            }
        }

    def _start_thread(self, name):
        entry = self.extra_threads[name]

        if entry["thread"] and entry["thread"].is_alive():
            return  # already running

        entry["stop_event"].clear()

        t = threading.Thread(
            target=entry["target"],
            daemon=entry["daemon"],
            name=name
        )

        entry["thread"] = t
        t.start()
    
    def _stop_thread(self, name):
        entry = self.extra_threads[name]

        if not entry["thread"]:
            return

        entry["stop_event"].set()

        if entry["thread"].is_alive():
            entry["thread"].join(timeout=1.0)

        entry["thread"] = None

    def _reconcile_threads(self, active_set):
        """
        active_set: iterable of thread names that SHOULD be running
        """

        for name, entry in self.extra_threads.items():
            should_run = name in active_set

            if should_run and not entry["active"]:
                self._start_thread(name)
                entry["active"] = True

            elif not should_run and entry["active"]:
                self._stop_thread(name)
                entry["active"] = False
    
    def _connect(self):
        try:
            self.command_socket.connect((self.host, self.command_port))
            self.video_socket.connect((self.host, self.video_port))
            self.states_socket.connect((self.host, self.states_port))
            self.configuration_socket.connect((self.host, self.config_port))
        
        except socket.error as e:
            raise ConnectionError(f"Failed to connect to Cora arm: {e}")
        
        self.configure_sockets()
        
        self._running = True

        # Start the states Thread
        self.states_thread = threading.Thread(target=self.states, daemon=True)

        return
    
    def _kill(self):
        if self._running is False:
            print("Client is already stopped.")
            return
        
        print("Stopping Cora client...")        
        self._running = False
        
        for sock in (self.command_socket, self.video_socket, self.states_socket):
            if sock:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                    sock.close()
                except OSError:
                    pass

        return


class CoraClient(CoraInterface):
    def __init__(self, **kwargs):
        self.use_camera = False
        self.use_controller = False
        self.use_vision = False

        super().__init__(self, **kwargs)
        
    def configure_sockets(self):
        self.video_socket.shutdown(socket.SHUT_WR)
        self.states_socket.shutdown(socket.SHUT_WR)
        self.command_socket.shutdown(socket.SHUT_RD)

    def configure_robot(self, **kwargs):
        self.use_controller = kwargs.get("use_controller")
        self.use_camera = kwargs.get("use_camera")
        self.use_vision = kwargs.get("use_vision")

    def kill_options(self):
        self.use_controller = False
        self.use_camera = False
        self.use_vision = False
    
    def update_options(self):
        active = set()

        if self.use_camera:
            active.add("video")

        if True:  # always listen to states
            active.add("states")

        self.reconcile_threads(active)

    def  connect(self):
        try:
            self.command_socket.connect((self.arm_host, self.command_port))
            self.video_socket.connect((self.arm_host, self.video_port))
            self.states_socket.connect((self.arm_host, self.states_port))
        
        except socket.error as e:
            raise ConnectionError(f"Failed to connect to Cora arm: {e}")
        
        self.configure_sockets()
        
        self._running = True
        self._start_threads()
        return

    def kill(self):
        if self._running is False:
            print("Client is already stopped.")
            return
        
        print("Stopping Cora client...")        
        self._running = False
        
        for sock in (self.command_socket, self.video_socket, self.states_socket):
            if sock:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                    sock.close()
                except OSError:
                    pass

        return
    
    def receive_frame(self):
        chunk_size = 8192
        while self._running:
            length_bytes = self.video_socket.recv(4)
            ## Get the frame

            ## Decode the frame from bytes to image

            if not self._running:
                break
        return
    
    def receive_states(self):
        """
        While socket is connected to server it listens 
        over Ethernet TCP socket for state information 
        and stores it as self.states in the Cora client object.
        """
        
        while self._running:
            if not self._running:
                break            
            raw_states = self.states_socket.recv(1024)
            self.move_status,self.state_space, self.states = ut.decode_pose_feedback(raw_states)


    def get_states(self, print=True):
        """
        Get self.states from Cora client object.
        """
        print(self.states)
        return self.states

    async def send_command(self, command, space, rt, interface_type, print=True, gripper_command=None):
        """
        Takes the command array and descriptive information, \n
        encodes it into json format and sends it as raw bytes \n
        over Ethernet TCP to the server. \n
        
        :param self: Description
        :param space: 'JS' for joint space or 'TS' for task (cartesian) space

        :param commands: numpy array of the values wrt the selected space\n
                format:\n 
                        [x, y, z, rx, ry, rz] for position \n
                        or [vx, vy, vz, wx, wy, wz] for velocity \n
                        or [Fx, Fy, Fz, Mx, My, Mz] for effort \n

        :param rt: True for real-time, False for non-real-time\n

        :param interface_type: command interface type; 'position', 'velocity', 'effort'\n
        
        :param print: If True, prints the command being sent.\n

        :param args: Additional arguments, e.g., gripper commands.
        """
        if print:
            print(f"Sending {interface_type} command to Cora, {command} in {space} space.")

        gripper_command = gripper_command if gripper_command is not None else np.array(0.0)  # get gripper command from args

        command_string = ut.encode_commands(command, gripper_command, space, rt, interface_type)
        try:
            self.command_socket.sendall(command_string.encode('utf-8'))
        except socket.error as e:
            raise ConnectionError(f"Failed to send command to Cora arm: {e}")
        return
    
class CoraServer(CoraInterface):

    # TODO: Implement cora server derived class with appropriate methods

    def __init__(self, **kwargs):
        super().__init__(self, **kwargs)
        
# class GuiClient(CoraClient):
#     def __init__(self, **kwargs):
#         super().__init__(**kwargs)
#         self.root = tk.TK()
#         self.root.title('Cora Control Panel')

#         self._build_layout()
#         self._update_states_loop()

        
