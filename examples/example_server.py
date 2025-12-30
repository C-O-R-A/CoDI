from codi import CoraServer

cora_srv = CoraServer(host='0.0.0.0', video_port=5001, command_port = 5002, states_port = 5003, config_port = 5004, vision_port = 5005)
cora_srv._activate()
