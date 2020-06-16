import argparse
import sys
import pyvisa
from pathlib import Path
from serial import Serial
from .experiment import measure
from .oscilloscope import Oscilloscope


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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", "-o", type=Path,
                        required=True, dest="out_dir")
    parser.add_argument("--num-measurements", "-n",
                        type=int, required=True, dest="num_meas")
    parser.add_argument("--instrument", type=str,
                        default="TCPIP::192.168.20.4::gpib0,1::INSTR")
    parser.add_argument("--shutter-port", type=str,
                        default="COM4", dest="shutter_port")
    parser.add_argument("--delta", "-d", type=float, default=0.038)
    args = parser.parse_args()
    if not args.out_dir.exists():
        args.out_dir.mkdir()
    if not args.out_dir.is_dir():
        print("Output path is not a directory.")
        sys.exit()
    if not dir_is_empty(args.out_dir):
        print("Directory is not empty.")
        sys.exit()
    main(args.out_dir, args.num_meas, args.instrument,
         args.shutter_port, args.delta)
