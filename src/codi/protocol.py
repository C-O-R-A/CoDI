import numpy as np
import json as js

'''
TODO: we can use this module on the desktop as well as on the robot. 
add utility fucntions for encoding states and decoding commands as needed. 
also add options for reading/writing from files for offline testing.
'''

def bytes_to_image(byte_data, width, height):
      return 

def image_to_bytes(image):
       return

def encode_commands(commands, gripper_commands, space, rt, interface_type):
        """
        Serialize  goal pose command and gripper command into string format.

        :param space: 'JS' for joint space or 'TS' for task (cartesian) space

        :param commands: 1D numpy array of the values wrt the selected space;
                format: 
                        [x, y, z, rx, ry, rz] for position 
                        or [vx, vy, vz, wx, wy, wz] for velocity
                        or [Fx, Fy, Fz, Mx, My, Mz] for effort

        :param gripper_commands: 1D numpy array of the gripper commands
                                format: [gripper_position] <between 0.0 (open) and 1.0 (closed)>

        :param rt: True for real-time, False for non-real-time

        :param interface_type: command interface type; 'position', 'velocity', 'effort'

        returns: UTF-8 encoded json formatted commands;
                format: b'{'space': space, 'rt': rt, 'interface_type':interface_type, 'shape': [rows, columns],
                                'type': dtype, 'data_array': [x, y, z, rx, ry, rz]}'        
        

        """
        command_data={
               'space': space,
               'rt': rt,
               'interface_type': interface_type,               
               'shape': list(commands.shape),
               'dtype': str(commands.dtype),
               'data': commands.tolist(),
               'gripper_data': gripper_commands.tolist()
        }

        raw_json_commands = (js.dumps(command_data)).encode('utf-8')
        return raw_json_commands

def decode_commands(raw_json_commands: bytes):
        '''
        Docstring for decode_commands
        
        :param raw_json_commands: Description
        :type raw_json_commands: bytes
        '''
        json_commands = js.loads(raw_json_commands.decode('utf-8'))
        commands_array = np.array(json_commands["data"], float)
        gripper_array = np.array(json_commands["gripper_data"], float)
        interface_type = json_commands["interface_type"]
        rt = json_commands["rt"]
        space = json_commands["space"]
        return rt, space, interface_type, commands_array, gripper_array

def encode_pose_feedback(status:str, space:str, states:list):
       '''
       Docstring for encode_pose_feedback
       
       :param status: Robot move status. 'idle', 'moving', 'homing', 'initializing'
       :type status: str
       :param space: 'JS' for joint space or 'TS' for task (cartesian) space
       :type space: str
       :param states: robot states. [[x, y, z, rx, ry, rz], [vx, vy, vz, wx, wy, wz]]
       :type states: list
       '''
       states_data = {
              'space': space,
              'status': status,
              'shape': states.shape,
              'type': states.type,
              'data': states.tolist()
       }
       raw_json_states = (js.dumps(states_data)).encode('utf-8')
       return raw_json_states

def decode_pose_feedback(raw_json_states:bytes):
        """
        Load pose with json, convert from list to numpy array\n

        :param raw_json_states: states in json format as raw bytes\n
                format: b'{\n
                'space': space,\n
                'status': status,\n 
                'shape': [rows, columns],\n 
                'type': dtype, \n
                'states_array': [[x, y, z, rx, ry, rz], [vx, vy, vz, wx, wy, wz]]\n
                }'\n

        returns status, space, states_array of type string, string, numpy_array;
                status: 'idle', 'at_target', 'moving', 'error'\n
                space: 'JS' for joint space or 'TS' for task (cartesian) space\n
                states_array: numpy array of the states values;
                        format:\n
                                [[x, y, z, rx, ry, rz],\n
                                 [vx, vy, vz, wx, wy, wz]]\n

        """
        json_states = js.loads(raw_json_states.decode('utf-8'))
        states_array = np.array(json_states["data"], float)
        space = json_states["space"]
        status = json_states["status"]

        return status, space, states_array


def encode_configs(use_controller=False, use_video=False, use_vision=False):
        '''
        Docstring for encode_configs
        
        :param use_controller: Description
        :param use_video: Description
        :param use_vision: Description
        '''
        config_data = {
               "use_controller": use_controller,
               "use_video": use_video,
               "use_vision":use_vision
        }

        raw_json_configs = (js.dumps(config_data)).encode('utf-8')
        return raw_json_configs

def decode_configs(raw_json_configs:bytes):
       config_data = js.loads(raw_json_configs.decode('utf-8'))
       return config_data["use_controller"], config_data["use_video"], config_data["use_vision"]
