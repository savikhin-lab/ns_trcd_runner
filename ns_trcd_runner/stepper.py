import os
import struct
import sys
import numpy as np
from enum import Enum
from pathlib import Path
from scipy.interpolate import interp1d
from serial import Serial


cal_file_path = os.environ["ZABERCAL"]
if cal_file_path is None:
    print("ZABERCAL environment variable not found.")
    sys.exit(-1)
cal_file_path = Path(cal_file_path)
cal_data = np.loadtxt(cal_file_path, delimiter=",")
interp_steps = interp1d(cal_data[:, 0], cal_data[:, 1], kind="cubic")


class StepperCmd(Enum):
    MOVE = 20
    INIT = 52
    GETPOS = 60


class Stepper:
    def __init__(self, port):
        self.ser = Serial(port, 9600, 8, 'N', 1, timeout=5)
        self.device = 1

    def _send(self, cmd, data):
        packet = struct.pack("<BBl", self.device, cmd, data)
        self.ser.write(packet)

    def _recv(self):
        response = self.ser.read(6)
        return response

    def move(self, target_pos):
        self._send(StepperCmd.MOVE.value, target_pos)
        curr_pos = 0
        while curr_pos != target_pos:
            curr_pos = self.pos()

    def move_wl(self, wl):
        steps = int(np.floor(interp_steps(wl)))
        self.move(steps)

    def pos(self):
        self._send(StepperCmd.GETPOS.value, 0)
        resp = self._recv()
        value = 256**3 * resp[5] + 256**2 * resp[4] + 256 * resp[3] + resp[2]
        if resp[5] > 127:
            value = -256**4
        return value
