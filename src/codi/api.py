from .runtime import get_client


def send_joint_position(rt, space, interface_type, target, gripper_command, command):
    get_client().send_command(
        rt=rt,
        space=space,
        interface_type=interface_type,
        target=target,
        gripper_command=gripper_command,
        command=command,
    )


def reconfig_robot(use_camera, use_vision, use_controller):
    get_client().configure_robot(
        use_camera=use_camera, use_vision=use_vision, use_controller=use_controller
    )


def get_state():
    return get_client().get_states()
