# CoDI (Colossus Desktop Interface)

A Python SDK for communicating with the Colossus robotic arm over TCP sockets.  
The package provides:

- `ColossusClient` for command transmission, state feedback, and video streaming  
- `GuiClient` for a basic Tkinter-based interface  
- Utility functions for encoding commands and decoding robot state messages  

This SDK is designed to be simple, modular, and suitable for integration into larger robotics applications.

---

## Features

- TCP communication for commands, state feedback, and video
- Threaded background receivers
- Optional Tkinter GUI for monitoring and testing
- Command encoding and state decoding utilities

---
## Implementation Architecture

![Colossus Logo](assets/Robot_Architecture.png)

---

## Project Structure

```

src/
codi/
client.py
utils.py
exceptions.py
README.md
pyproject.toml

````

---

## Installation

### Install directly from GitHub

```bash
pip install git+https://github.com/yourusername/CoDI.git@main
````

Or install a specific release:

```bash
pip install git+https://github.com/yourusername/CoDI.git@v0.1.0
```

### Local installation (development)

```bash
git clone https://github.com/yourusername/CoDI.git
cd codi
pip install -e .
```

---

## Dependencies

* `numpy`
* `Pillow`

Both will be installed automatically when installing via `pip`.

---

## Basic Usage

### Connecting and sending commands

```python
from codi.client import ColossusClient

client = ColossusClient(
    host="192.168.0.10",
    video_port=8001,
    command_port=8002,
    states_port=8003
)

client.connect()

client.send_command(
    command=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
    space="JS",
    rt=False,
    interface_type="position"
)

states = client.get_states()
print(states)
```

### GUI usage

```python
from codi.client import GuiClient

gui = GuiClient(
    host="192.168.0.10",
    video_port=8001,
    command_port=8002,
    states_port=8003
)

gui.run()
```
---

## Troubleshooting

* Ensure correct IP address and port configuration.
* GUI functions require a Python installation that includes Tkinter.
* Video display requires Pillow for image conversion.

---

## License

This project is released under the MIT License.

