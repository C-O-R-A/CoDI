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
from pathlib import Path
from yaml import safe_load, dump
import json as js

from . import protocol as pt
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

    def __init__(self, filepath:str=None, **kwargs):
        '''
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
        '''
        
        self._running = False 

        if filepath is not None:
            # process the file at given path for parameters
            file = Path(filepath)
            extension = file.suffix
            
            match extension:
                case '.yaml':
                    with open(file, 'r') as f:
                        loaded_file = safe_load(f)
                    pass

                case '.json':
                    with open(file, 'r') as f:
                        loaded_file = js.load(f)
                    pass
            
            self.host = loaded_file["host"]
            self.video_port = loaded_file["video_port"]
            self.command_port = loaded_file["command_port"]
            self.states_port = loaded_file["states_port"]
            self.config_port = loaded_file["config_port"]
            self.vision_port = loaded_file["vision_port"]

        else:
            self.host = kwargs.get("host")
            self.video_port = kwargs.get('video_port')
            self.command_port = kwargs.get('command_port')
            self.states_port = kwargs.get('states_port')
            self.config_port = kwargs.get('config_port')
            self.vision_port = kwargs.get('vision_port')

        self._set_move_status('idle')

        self.video_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)           # TCP socket for video
        self.command_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)         # TCP socket for commands
        self.states_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)          # TCP socket for states
        self.vision_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)          # TCP socket for vision
        self.configuration_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)   # TCP socket for configurations

        try:
            self.arm_host = socket.gethostbyname(self.host)

        except socket.gaierror:
            raise ValueError(f"Could not resolve hostname: {self.arm_host}")
        
    def _set_move_status(self, status: str):
        statuses = ['idle', 'moving', 'homing', 'initializing']

        try:
            self.move_status = statuses[statuses.index(status)]
        except ValueError:
            raise ValueError(f"Status '{status}' unknown")

        
    def _activate(self):
        '''
        Docstring for _connect
        
        :param self: Description
        '''
        self.connect()
        
        self.configure()

        self.setup()  

        self._running = True
        return
    
    def _kill(self):
        if self._running is False:
            print("Client is already stopped.")
            return
        
        print("Stopping Cora client...")        
        self._running = False
        
        for sock in (self.command_socket, self.video_socket, self.states_socket, self.configuration_socket):
            if sock:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                    sock.close()
                except OSError:
                    pass
        
        # Any post-processing steps that need to take place 
        # are contained in this method
        self.cleanup()

        return

class CoraClient(CoraInterface):
    '''        
    :param self: 
    :param file: Yaml or Json socket config file 
    :param kwargs: host: str, video_port: str, command_port: str, states_port: str, config_port:str 
    '''

    def __init__(self, **kwargs):
        super().__init__(self, **kwargs)        
        self.use_controller = kwargs.get("use_controller")
        self.use_camera = kwargs.get("use_camera")
        self.use_vision = kwargs.get("use_vision")
        self.threads = dict()
    
    def connect(self):
        try:
            self.command_socket.connect((self.host, self.command_port))
            self.video_socket.connect((self.host, self.video_port))
            self.vision_socket.connect((self.host, self.vision_port))
            self.states_socket.connect((self.host, self.states_port))
            self.configuration_socket.connect((self.host, self.config_port))
        
        except socket.error as e:
            raise ConnectionError(f"Failed to connect to Cora arm: {e}")
        
    def configure(self):
        self.video_socket.shutdown(socket.SHUT_WR)
        self.states_socket.shutdown(socket.SHUT_WR)
        self.command_socket.shutdown(socket.SHUT_RD)  

    def setup(self):
        self.init_threads()
        self.update_options()

    def init_threads(self):
        self.threads = {
            "video": {
                "target": self.receive_frame,
                "thread": None,
                "stop_event": threading.Event(),
                "active": False,
                "daemon": True
            },

            "states":{
                "target": self.receive_states,
                "thread": None,
                "stop_event": threading.Event(),
                "active": False,
                "daemon": True
            },

            "commands":{
                "target": self.send_command,
                "thread": None,
                "stop_event": threading.Event(),
                "active": False,
                "daemon": True
            },

            "configuration":{
                "target": self.configure_robot,
                "thread": None,
                "stop_event": threading.Event(),
                "active": False,
                "daemon": True
            },

            "vision_poses":{
                "target": self.receive_vision_poses,
                "thread": None,
                "stop_event": threading.Event(),
                "active": False,
                "daemon": True
            }

        }

    def start_thread(self, name):
        entry = self.threads[name]

        if entry["thread"] and entry["thread"].is_alive():
            return  # already running

        entry["stop_event"].clear()

        t = threading.Thread(
            target=entry["target"],
            daemon=entry["daemon"],
            name=name
        )

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
        
    def configure_robot(self, **kwargs):
        '''
        (Re)configures robot's internal parameters 
        
        :param self: Description
        :param kwargs: Description
        '''
        self.use_controller = kwargs.get("use_controller")
        self.use_camera = kwargs.get("use_camera")
        self.use_vision = kwargs.get("use_vision")
        self.update_options()

        payload = pt.encode_configs(use_controller=self.use_controller, 
                                    use_video=self.use_camera, 
                                    use_vision=self.use_vision)
        
        self.configuration_socket.sendall(payload)


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
        '''
        Docstring for update_options
        
        :param self: Description
        '''
        active = set()
        if self.use_vision:
            active.add("vision_poses")

        if self.use_camera:
            active.add("video")

        if True:  # always listen to these
            active.add("states")
            active.add("configuration")
            active.add("commands")

        self.reconcile_threads(active)
    
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
            move_status,self.state_space, self.states = pt.decode_pose_feedback(raw_states)
            self._set_move_status(move_status)

    def receive_vision_poses(self):
        while self._running:
            if not self._running:
                break
            raw_poses = self.vision_socket.recv(1024)

        return

    def get_states(self, print=True):
        """
        Get self.states from Cora client object.
        """
        print(self.states)
        return self.states

    def send_command(self, command, space, rt, interface_type, print=True, gripper_command=None):
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

        gripper_command = gripper_command if gripper_command is not None else np.array([0.0])  # get gripper command from args

        command_string = pt.encode_commands(command, gripper_command, space, rt, interface_type)
        try:
            self.command_socket.sendall(command_string.encode('utf-8'))
        except socket.error as e:
            raise ConnectionError(f"Failed to send command to Cora arm: {e}")
        return
    
    def get_configuration(self):
        self.configuration_socket.sendall(b'config')
        config = pt.decode_configs(self.configuration_socket.recv(1024))
        return config
    
class CoraServer(CoraInterface):

    # TODO: Implement cora server derived class with appropriate methods

    def __init__(self, **kwargs):
        super().__init__(self, **kwargs)
        self.command_conn = None
        self.states_conn = None
        self.video_conn = None
        self.vision_conn = None
        self.config_conn = None
        return

    def connect(self):
        self.command_socket.bind((self.host, self.command_port))
        self.states_socket.bind((self.host, self.states_port))
        self.video_socket.bind((self.host, self.video_port))
        self.vision_socket.bind((self.host, self.vision_port))
        self.configuration_socket.bind((self.host, self.config_port))

        self.command_socket.listen(1)
        self.states_socket.listen(1)
        self.video_socket.listen(1)
        self.vision_socket.listen(1)
        self.configuration_socket.listen(1)
        
    
    def accept_connections(self):
        print("Waiting for client connections...")

        self.command_conn, _ = self.command_socket.accept()
        self.states_conn, _ = self.states_socket.accept()
        self.video_conn, _ = self.video_socket.accept()
        self.vision_conn, _ = self.vision_socket.accept()
        self.config_conn, _ = self.configuration_socket.accept()

        print("All client connections established")
        

    
    def configure(self):
        self.video_socket.shutdown(socket.SHUT_RD)
        self.states_socket.shutdown(socket.SHUT_RD)
        self.command_socket.shutdown(socket.SHUT_WR) 
        return
    
    def startup(self):
        return
    
    def cleanup(self):
        for conn in (
            self.command_conn,
            self.states_conn,
            self.video_conn,
            self.vision_conn,
            self.config_conn
        ):
            if conn:
                try:
                    conn.close()
                except OSError:
                    pass

        for srv in (
            self.command_socket,
            self.states_socket,
            self.video_socket,
            self.vision_socket,
            self.configuration_socket
        ):
            try:
                srv.close()
            except OSError:
                pass

    
    def receive_command(self):
        raw = self.command_conn.recv(4096)
        if not raw:
            return None

        command = pt.decode_command(raw)
        return command
    
    def send_state(self, state_msg):
        payload = pt.encode_pose_feedback(state_msg)
        self.states_conn.sendall(payload)

    def send_vision_poses(self, poses):
        payload = pt.encode_vision_poses(poses)
        self.vision_conn.sendall(payload)
    
    def receive_config(self):
        raw = self.config_conn.recv(1024)
        if not raw:
            return None

        config = pt.decode_configs(raw)
        return config



