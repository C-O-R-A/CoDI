import codi.runtime as rt
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = HERE.parent / "config" / "example_client.json"

# test send/receive with instance
rt.start_client(str(CONFIG))
