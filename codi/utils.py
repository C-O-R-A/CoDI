import numpy as np
import json as js

def bytes_to_image(byte_data, width, height):
      return 

def encode_commands(commands, space, rt, interface_type):
        """
        Serialize  goal pose command and gripper command into string format.

        :param space: 'JS' for joint space or 'TS' for task (cartesian) space

        :param commands: numpy array of the values wrt the selected space;
                format: 
                        [x, y, z, rx, ry, rz] for position 
                        or [vx, vy, vz, wx, wy, wz] for velocity
                        or [Fx, Fy, Fz, Mx, My, Mz] for effort

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
               'data': commands.tolist()
        }

        raw_json_commands = (js.dumps(command_data)).encode('utf-8')
        return raw_json_commands

def decode_pose_feedback(raw_json_states):
        """
        Load pose with json, convert from list to numpy array

        :param raw_json_states: states in json format as raw bytes
                format: b'{'space': space, 'shape': [rows, columns], 'type': dtype, 'data_array': [[x, y, z, rx, ry, rz], [vx, vy, vz, wx, wy, wz]]}'

        returns [space, states_array] of type [string, numpy_array]

        """
        json_states = js.loads(raw_json_states.decode('utf-8'))
        states_array = np.array([json_states["data"]], float)
        space = json_states["space"]
        
        return space, states_array