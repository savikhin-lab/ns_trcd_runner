import re
import sys
import time
import click
from math import floor
from serial import Serial


class Monochromator:
    def __init__(self, port):
        """A high level wrapper for the Optometrics SDMC1-04G monochromator.

        In reality this is a wrapper for the stepper motor driver, as the monochromator
        is just controlled by the stepper motor, and the stepper motor knows nothing
        about being connected to a monochromator.

        The monochromator position is calibrated by powering it on in the zero-order position.
        If the monochromator is powered on in ANY other position, the calibration will be
        shifted for all wavelengths.
        """
        self._ser = Serial(port, 9600, 8, 'N', 1, timeout=1)
        self._ser.write(b"\x03")
        time.sleep(0.1)
        self._ser.write(b" ")
        time.sleep(0.1)
        init_response = self._ser.read(100)
        if init_response != b" SMC24 v2.12\r\n":
            click.echo("Monochromator not initialized correctly", err=True)
            sys.exit(-1)
        self._pos_regex = re.compile("^Z\\s+(-?\\d+).*$")

    def move_wl(self, wl):
        """Move to the specified wavelength.

        The stepper motor has a step size of 0.125nm, so the target position is determined by
        multiplying the target wavelength by 8 (8 steps per nm) and rounding down.
        """
        new_pos = floor(wl * 8)
        cmd = f"R {-new_pos}\r\n".encode("utf-8")
        self._ser.write(cmd)
        time.sleep(0.1)
        self._ser.reset_input_buffer()
        stop_time = time.time() + 10
        while time.time() < stop_time:
            current_pos = self.pos()
            if -new_pos == current_pos:
                break

    def pos(self):
        """Returns the position of the stepper motor in steps.

        Note: the position may be positive, negative, or zero.
        """
        self._ser.reset_input_buffer()
        self._ser.write(b"Z\r\n")
        resp = self._ser.read(100).decode("utf-8")
        match = self._pos_regex.search(resp)
        try:
            text_pos = match[1]
        except IndexError:
            click.echo(f"Couldn't parse monochromator position from response: {resp}", err=True)
            sys.exit(-1)
        current_pos = int(text_pos)
        return current_pos

    def go_home(self):
        """Send the monochromator to the zero-order position.
        """
        self.move_wl(0)
