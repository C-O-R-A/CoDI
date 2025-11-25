import numpy as np
import socket
import threading

import utils
import exeptions

UDP_IP = '0.0.0.0'

class ColossusClient:
    def __init__(self, **kwargs):
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
        
        self.video_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)        # UDP socket for video
        self.command_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)     # TCP socket for commands
        self.states_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)       # UDP socket for states
        self._running = False

    def connect(self):
        try:
            self.command_socket.connect((self.arm_host, self.command_port))
            self.video_socket.connect((UDP_IP, self.video_port))
            self.states_socket.connect((UDP_IP, self.states_port))
        
        except socket.error as e:
            raise ConnectionError(f"Failed to connect to Colossus arm: {e}")
        
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
        if self.command_socket:
            self.command_socket.close()
        if self.video_socket:
            self.video_socket.close()
        if self.states_socket:
            self.states_socket.close()
        return
    
    def receive_video(self):
        while self._running:
            break
        return
    
    def receive_states(self):
        while self._running:
            break
        return
    
    def send_command(self, command, space, rt):
        print(f"Sending command to Colossus {command} in {space} space.")
        command_string = utils.serialize_commands(command, space, rt)
        try:
            self.command_socket.sendall(command_string.encode('utf-8'))
        except socket.error as e:
            raise ConnectionError(f"Failed to send command to Colossus arm: {e}")
        return
    
class GuiClient(ColossusClient):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        