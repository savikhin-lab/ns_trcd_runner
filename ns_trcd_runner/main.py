import os
import sys
import click
import numpy as np
import pyvisa
from pathlib import Path
from .experiment import measure_multiwl
from .oscilloscope import Oscilloscope
from .actuator import Actuator
from .monochromator import Monochromator


@click.command()
@click.option("-o", "--output-dir", "outdir", required=True, type=click.Path(file_okay=False, dir_okay=True), help="The output directory in which the raw data will be stored.")
@click.option("-n", "--num-measurements", "num_meas", required=True, type=click.INT, help="The number of measurements to collect at each wavelength.")
@click.option("--wstart", type=click.FLOAT, help="The first wavelength for data collection.")
@click.option("--wstop", type=click.FLOAT, help="The last wavelength for data collection.")
@click.option("--wstep", type=click.FLOAT, help="The step between wavelengths.")
@click.option("-w", "wlist", type=click.FLOAT, multiple=True, help="A set of individual wavelengths to measure at. May be specified multiple times.")
@click.option("-c", "--chunk-size", type=click.INT, default=10, help="The number of measurements to take at a time at each wavelength.")
@click.option("--notify", "phone_num", type=click.STRING, help="The phone number to SMS when the experiment is done.")
@click.option("--overwrite", is_flag=True, help="Overwrite the contents of the output directory.")
@click.option("--no-monochromator", "no_mon", is_flag=True, help="Don't move the monochromator.")
def run(outdir, num_meas, wstart, wstop, wstep, wlist, chunk_size, phone_num, overwrite, no_mon):
    """Do a TRCD experiment.

    It is up to the user to make sure that the actuator has been homed before running the experiment.
    """
    outdir = Path(outdir)
    if not outdir.exists():
        outdir.mkdir()
    if (not overwrite) and (len(os.listdir(outdir)) != 0):
        print("Output directory is not empty.")
        sys.exit(-1)
    wl_list = make_wavelength_list(wstart, wstop, wstep, wlist)
    act = Actuator()
    scope_name = get_scope_name()
    rm = pyvisa.ResourceManager()
    instr = rm.open_resource(scope_name)
    instr.timeout = 5_000  # ms
    scope = Oscilloscope(instr)
    monochromator_port = os.environ.get("MONOCHROMATOR_PORT")
    if monochromator_port is None:
        click.echo("MONOCHROMATOR_PORT environment variable is not defined.", err=True)
        sys.exit(-1)
    if no_mon:
        mon = None
    else:
        mon = Monochromator(monochromator_port)
    try:
        mon_offset = float(os.environ.get("MONOCHROMATOR_OFFSET"))
    except TypeError:
        mon_offset = 0
    measure_multiwl(scope, act, mon, outdir, num_meas, wl_list,
                    chunk_size=chunk_size, phone_num=phone_num, mon_offset=mon_offset)
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
