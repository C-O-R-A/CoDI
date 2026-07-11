from .interfaces import CoraClient
_client = None


def start_client(config_path=None, **kwargs):
    global _client
    if _client is None:
        _client = CoraClient(filepath=config_path, **kwargs)
        _client._activate()
    else:
        print("Client active from previous session")
    return _client


def get_client():
    if _client is None:
        raise RuntimeError("Cora client not started")
    return _client


def stop_client():
    global _client
    if _client:
        _client._end_interface()
        _client = None
