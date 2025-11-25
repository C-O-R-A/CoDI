import numpy as np

def bytes_to_image(byte_data, width, height):
      return 

def serialize_commands(commands, space, rt):
        """
        Serialize  goal pose command and gripper command into string format.
        space: 'JS' for joint space or 'TS' for task space
        commands: list of floats representing the command values
        rt: True for real-time, False for non-real-time
        """

        command_string = f"{space} {rt} "
        for i in commands:
            command_string += f"{i:.4f} "
        command_string = command_string.strip() + "\n"   

        return command_string

def parse_pose_feedback(state_string):
        """
        Parse pose string into appropriately sized array.
        """

        string_array=np.fromstring(state_string, dtype=np.float32, sep=' ')

        # Divide string array into rows of pose vectors (x, y, z, rx, ry, rz) or (joint1, joint2, joint3, joint4, joint5, joint6)
        rows = int(len(string_array)/6) 

        string_array=string_array.reshape((3,6))

        return string_array