from .runtime import get_client

def send_joint_position(q, rt=True):
    get_client().send_command(
        command=q,
        space="JS",
        rt=rt,
        interface_type="position"
    )

def get_state():
    return get_client().get_states()
