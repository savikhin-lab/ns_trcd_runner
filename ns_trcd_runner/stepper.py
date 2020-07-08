import struct
import numpy as np
from enum import Enum
from scipy.interpolate import interp1d
from serial import Serial


CAL_WL = [780, 785, 790, 795, 800, 805, 810, 815, 820, 825, 830, 835, 840, 845, 850]
CAL_STEPS = [226996, 227897, 228712, 230259, 231322, 232303, 233216,
             234255, 235493, 236728, 237581, 238474, 239750, 240587, 241487]
interp_steps = interp1d(CAL_WL, CAL_STEPS, kind="cubic")


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
