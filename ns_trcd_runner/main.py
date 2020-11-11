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
from .actuator import Actuator


@click.command()
@click.option("-o", "--output-dir", "outdir", required=True, type=click.Path(file_okay=False, dir_okay=True), help="The output directory in which the raw data will be stored.")
@click.option("-n", "--num-measurements", "num_meas", required=True, type=click.INT, help="The number of measurements to collect at each wavelength.")
@click.option("--wstart", type=click.FLOAT, help="The first wavelength for data collection.")
@click.option("--wstop", type=click.FLOAT, help="The last wavelength for data collection.")
@click.option("--wstep", type=click.FLOAT, help="The step between wavelengths.")
@click.option("-w", "wlist", type=click.FLOAT, multiple=True, help="A set of individual wavelengths to measure at. May be specified multiple times.")
def run(outdir, num_meas, wstart, wstop, wstep, wlist):
    """Do a TRCD experiment.
    """
    outdir = Path(outdir)
    if not outdir.exists():
        outdir.mkdir()
    if len(os.listdir(outdir)) != 0:
        print("Output directory is not empty.")
        sys.exit(-1)
    wl_list = make_wavelength_list(wstart, wstop, wstep, wlist)
    act = Actuator()
    click.echo("Homing etalon...", nl=False)
    act.home()
    click.echo("done")
    scope_name = get_scope_name()
    rm = pyvisa.ResourceManager()
    instr = rm.open_resource(scope_name)
    instr.timeout = 5_000  # ms
    scope = Oscilloscope(instr)
    measure_multiwl(scope, act, outdir, num_meas, wl_list)
    instr.close()
    act.close()
    return


def make_wavelength_list(start, stop, step, wl_list):
    if all(map(lambda x: x is not None, [start, stop, step])) and len(wl_list) != 0:
        print("Cannot specify both a wavelength range and individual wavelengths.")
        sys.exit(-1)
    if all(map(lambda x: x is None, [start, stop, step])) and len(wl_list) == 0:
        print("No wavelengths specified.")
        sys.exit(-1)
    if len(wl_list) != 0:
        return wl_list
    else:
        validate_wavelength_range(start, stop, step)
        wls = [x for x in np.arange(start, stop+1, step)]
        return wls


def validate_wavelength_range(start, stop, step):
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


def dir_is_empty(path):
    for _ in path.iterdir():
        return False
    return True


def main(save_path, num_meas, instrument_name, shutter_port, delta):
    rm = pyvisa.ResourceManager()
    instr = rm.open_resource(instrument_name)
    instr.timeout = 5_000  # ms
    scope = Oscilloscope(instr)
    shutter = Serial(shutter_port, baudrate=9_600, timeout=5)
    measure(scope, delta, save_path, num_meas)
    instr.close()
    shutter.close()
