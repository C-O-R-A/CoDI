_client = None

def start_client(config_path=None, **kwargs):
    global _client
    if _client is None:
        from .client import CoraClient
        _client = CoraClient(filepath=config_path, **kwargs)
        _client._activate()
    return _client

def get_client():
    if _client is None:
        raise RuntimeError("Cora client not started")
    return _client

def stop_client():
    global _client
    if _client:
        _client._kill()
        _client = None
