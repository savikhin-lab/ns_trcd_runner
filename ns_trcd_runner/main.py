import argparse
import os
import sys
import click
import numpy as np
import pyvisa
from pathlib import Path
from typing import List
from serial import Serial
from .experiment import measure_multiwl
from .oscilloscope import Oscilloscope
from .stepper import Stepper


@click.command()
@click.option("-o", "--output-dir", "outdir", type=click.Path(file_okay=False, dir_okay=True), help="The output directory in which the raw data will be stored.")
@click.option("-n", "--num-measurements", "num_meas", type=click.INT, help="The number of measurements to collect at each wavelength.")
@click.option("--wstart", type=click.INT, default=790, help="The first wavelength for data collection.")
@click.option("--wstop", type=click.INT, default=840, help="The last wavelength for data collection.")
@click.option("--wstep", type=click.INT, default=2, help="The step between wavelengths.")
@click.option("-d", "--delta", type=click.FLOAT, default=0.038, help="The retardation of the stress plate.")
def run(outdir, num_meas, wstart, wstop, wstep, delta):
    """Do a TRCD experiment.
    """
    if outdir is None:
        print("An output directory is required.")
        sys.exit(-1)
    outdir = Path(outdir)
    if not outdir.exists():
        outdir.mkdir()
    if len(os.listdir(outdir)) != 0:
        print("Output directory is not empty.")
        sys.exit(-1)
    if num_meas is None:
        print("A number of measurements is required.")
        sys.exit(-1)
    validate_wavelengths(wstart, wstop, wstep)
    slit_port = get_slit_port()
    slit = Stepper(slit_port)
    scope_name = get_scope_name()
    wls = [x for x in range(wstart, wstop+1, wstep)]
    rm = pyvisa.ResourceManager()
    instr = rm.open_resource(scope_name)
    instr.timeout = 5_000  # ms
    scope = Oscilloscope(instr)
    measure_multiwl(scope, slit, delta, outdir, num_meas, wls)
    instr.close()
    return


def validate_wavelengths(start, stop, step):
    if start is None:
        print("An initial wavelength is required.")
        sys.exit(-1)
    if stop is None:
        print("A final wavelength is required.")
        sys.exit(-1)
    if step is None:
        print("A wavelength step is required.")
        sys.exit(-1)
    if (start < 780) or (start > 850) or (stop < 780) or (stop > 850):
        print("Wavelengths must be in the range [780, 850]nm.")
        sys.exit(-1)
    if start >= stop:
        print("Final wavelength must be greater than initial wavelength.")
        sys.exit(-1)
    if step == 0:
        print("Wavelength step must be > 0.")
        sys.exit(-1)
    return


def get_scope_name() -> str:
    """Looks for the oscilloscope instrument name in the SCOPE environment variable.
    """
    instr_name = os.getenv("SCOPE")
    if instr_name is None:
        print("Oscilloscope instrument string not found. Please set the SCOPE environment variable.")
        sys.exit(-1)
    else:
        return instr_name


def get_slit_port() -> str:
    """Looks for the Zaber stepper port in the ZABERPORT environment variable.
    """
    portname = os.getenv("ZABERPORT")
    if portname is None:
        print("Zaber port name not found. Please set the ZABERPORT environment variable.")
        sys.exit(-1)
    else:
        return portname


def main(save_path, num_meas, instrument_name, shutter_port, delta):
    rm = pyvisa.ResourceManager()
    instr = rm.open_resource(instrument_name)
    instr.timeout = 5_000  # ms
    scope = Oscilloscope(instr)
    shutter = Serial(shutter_port, baudrate=9_600, timeout=5)
    measure(scope, delta, save_path, num_meas)
    instr.close()
    shutter.close()


def dir_is_empty(path):
    for _ in path.iterdir():
        return False
    return True
