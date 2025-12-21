"""CoDI (Colossus Desktop Interface)

CoDI is an SDK developed by ... to interface with the open source Colossus cobot.
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

import utils as ut
import exeptions

class ColossusClient:
    def __init__(self, **kwargs):
        self._running = False
        self.arm_host = kwargs.get("host")
        self.video_port = kwargs.get('video_port')
        self.command_port = kwargs.get('command_port')
        self.states_port = kwargs.get('states_port')
        self.receive_video_bool = kwargs.get('receive_video', True)
        self.receive_states_bool = kwargs.get('receive_states', True)

        try:
            self.arm_host = socket.gethostbyname(self.arm_host)
        except socket.gaierror:
            raise ValueError(f"Could not resolve hostname: {self.arm_host}")
        
        self.video_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)        # TCP socket for video
        self.command_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)     # TCP socket for commands
        self.states_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)       # TCP socket for states

    def configure_sockets(self):
        self.video_socket.shutdown(socket.SHUT_WR)
        self.states_socket.shutdown(socket.SHUT_WR)
        self.command_socket.shutdown(socket.SHUT_RD)

    def  connect(self):
        try:
            self.command_socket.connect((self.arm_host, self.command_port))
            self.video_socket.connect((self.arm_host, self.video_port))
            self.states_socket.connect((self.arm_host, self.states_port))
        
        except socket.error as e:
            raise ConnectionError(f"Failed to connect to Colossus arm: {e}")
        
        self.configure_sockets()
        
        self._running = True
        self._start_threads()
        return

    def _start_threads(self):
        self.video_thread = threading.Thread(target=self.receive_video, daemon=True)
        self.states_thread = threading.Thread(target=self.receive_states, daemon=True)

        self.video_thread.start()
        self.states_thread.start()
        return

    def kill(self):
        if self._running is False:
            print("Client is already stopped.")
            return
        
        print("Stopping Colossus client...")        
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
        and stores it as self.states in the colossus client object.
        """
        
        while self._running:
            if not self._running:
                break            
            raw_states = self.states_socket.recv(1024)
            self.state_space, self.states = ut.decode_pose_feedback(raw_states)

    
    def get_states(self, print=True):
        """
        Get self.states from colossus client object.
        """
        print(self.states)
        return self.states
    
    def send_command(self, command, space, rt, interface_type, print=True):
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

        :param rt: True for real-time, False for non-real-time

        :param interface_type: command interface type; 'position', 'velocity', 'effort'
        """
        if print == True:
            print(f"Sending {interface_type} command to Colossus, {command} in {space} space.")

        command_string = ut.encode_commands(command, space, rt, interface_type)
        try:
            self.command_socket.sendall(command_string.encode('utf-8'))
        except socket.error as e:
            raise ConnectionError(f"Failed to send command to Colossus arm: {e}")
        return
    
class GuiClient(ColossusClient):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.root = tk.TK()
        self.root.title('Colossus Control Panel')

        self._build_layout()
        self._update_states_loop()

        
