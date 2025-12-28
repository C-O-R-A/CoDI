import numpy as np
import json as js
import sys
from pathlib import Path as pth

ROOT = pth().resolve().parents[1]
sys.path.append(ROOT)

import codi.src.codi.protocol as ut

def test_encode_commands():
    command = np.array(([1.11,2.22,3.33],[4.44,5.55,6.66]))
    assert (ut.encode_commands(np.array(command, float), 'TS', False, 'position') 
            == 
            b'{"space": "TS", "rt": false, "interface_type": "position", "shape": [6], "dtype": "float64", "data": [[1.11, 2.22, 3.33], [4.44, 5.55, 6.66]]}')
    

def test_decode_states():
    raw_json = b'{"space": "TS", "shape": [6, 2], "dtype": "float64", "data": [[1.11, 2.22, 3.33, 4.44, 5.55, 6.66], [1.11, 2.22, 3.33, 4.44, 5.55, 6.66]]}'

    space, arr = ut.decode_pose_feedback(raw_json)

    assert space == "TS"
    assert np.allclose(arr, np.array([[1.11, 2.22, 3.33, 4.44, 5.55, 6.66], [1.11, 2.22, 3.33, 4.44, 5.55, 6.66]]))