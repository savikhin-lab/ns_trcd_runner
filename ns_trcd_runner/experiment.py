import numpy as np
from dataclasses import dataclass
from typing import Tuple, Union


@dataclass
class Preamble:
    """Data needed to reconstruct oscilloscope signals from digitizer levels.
    """

    t_res: float
    v_scale_par: float
    v_offset_par: float
    v_scale_perp: float
    v_offset_perp: float
    v_scale_ref: float
    v_offset_ref: float
    points: int


@dataclass
class DigitizerLevels:
    """Raw digitizer levels from a single acquisition.
    """

    par: np.ndarray
    perp: np.ndarray
    ref: np.ndarray


@dataclass
class Measurement:
    """Reconstructed signals for an entire measurement.
    """
    par_wp: np.ndarray
    par_np: np.ndarray
    perp_wp: np.ndarray
    perp_np: np.ndarray
    ref_wp: np.ndarray
    ref_np: np.ndarray
    da: np.ndarray
    cd: np.ndarray


def measure(scope, shutter, delta, outdir, n) -> None:
    initialize_scope_settings(scope)
    scope.acquisition_start()
    preamble = get_scope_preamble(scope)
    shutter.reset_input_buffer()
    count = 0
    while True:
        scope.acquisition_start()
        wait_until_triggered(scope)
        has_pump = read_pump_state(shutter)
        if has_pump is None:
            print("Invalid message read from shutter.")
            return
        if not has_pump:
            continue
        with_pump_dig_levels = acquire_signals(scope)
        scope.acquisition_start()
        wait_until_triggered(scope)
        has_pump = read_pump_state(shutter)
        if has_pump is None:
            print("Invalid message read from shutter.")
            return
        if has_pump:
            continue
        no_pump_dig_levels = acquire_signals(scope)
        measurement = compute_da(
            preamble, delta, with_pump_dig_levels, no_pump_dig_levels)
        count += 1
        save_measurement(measurement, outdir, count)
        if count > n:
            return


def save_measurement(meas, root, count):
    """Save the measurement as separate *.npy files.
    """
    out = root / str(count)
    out.mkdir()
    np.save(out / "with_pump_par.npy", meas.par_wp)
    np.save(out / "without_pump_par.npy", meas.par_np)
    np.save(out / "with_pump_perp.npy", meas.perp_wp)
    np.save(out / "without_pump_perp.npy", meas.perp_np)
    np.save(out / "with_pump_ref.npy", meas.ref_wp)
    np.save(out / "without_pump_ref.npy", meas.ref_np)
    np.save(out / "da_par.npy", meas.da)
    np.save(out / "da_cd.npy", meas.cd)
    return


def compute_da(pre, delta, with_p, without_p) -> Measurement:
    """Reconstruct signals to compute dA and dAcd.
    """
    par_wp = pre.v_scale_par * with_p.par + pre.v_offset_par
    par_np = pre.v_scale_par * without_p.par + pre.v_offset_par
    perp_wp = pre.v_scale_perp * with_p.perp + pre.v_offset_perp
    perp_np = pre.v_scale_par * without_p.perp + pre.v_offset_perp
    ref_wp = pre.v_scale_ref * with_p.ref + pre.v_offset_ref
    ref_np = pre.v_scale_ref * without_p.ref + pre.v_offset_ref
    da = -np.log10((par_wp / ref_wp) / (par_np / ref_np))
    cd = (4 / (2.3 * delta)) * (perp_wp / par_wp - perp_np / par_np)
    meas = Measurement(par_wp, par_np, perp_wp,
                       perp_np, ref_wp, ref_np, da, cd)
    return meas


def acquire_signals(scope) -> DigitizerLevels:
    """Acquire raw digitizer levels for each channel.
    """
    scope.set_waveform_data_source_single_channel(1)
    par = scope.get_curve()
    scope.set_waveform_data_source_single_channel(2)
    perp = scope.get_curve()
    scope.set_waveform_data_source_single_channel(3)
    ref = scope.get_curve()
    return DigitizerLevels(par, perp, ref)


def read_pump_state(shutter) -> Union[bool, None]:
    """Determine if this measurement is with pump.

    Returns None if an invalid message was read from the shutter.
    """
    state = shutter.read(4)
    if state == b"open":
        return True
    if state == b"shut":
        return False
    return None


def wait_until_triggered(scope) -> None:
    """Block until the oscilloscope has been triggered.
    """
    while True:
        if scope.get_trigger_state() == "save":
            break
    return


def initialize_scope_settings(scope) -> None:
    """Make sure the oscilloscope settings are set for experiment conditions.
    """
    scope.set_hi_res_mode()
    scope.set_single_acquisition_mode()
    scope.set_waveform_data_source_single_channel(1)
    scope.set_waveform_encoding_ascii()
    scope.set_waveform_start_point(1)
    scope.set_waveform_stop_point(scope.get_waveform_length())
    scope.add_immediate_mean_measurement(4)
    scope.set_waveform_start_point(1)
    scope.set_waveform_stop_point(10_000_000)
    return


def get_scope_preamble(scope) -> Preamble:
    """Get the data needed to reconstruct a signal from the oscilloscope.
    """
    time_res = scope.get_time_resolution()
    scope.set_waveform_data_source_single_channel(1)
    v_scale_par = scope.get_voltage_scale_factor()
    v_offset_par = scope.get_vertical_offset_volts()
    scope.set_waveform_data_source_single_channel(2)
    v_scale_perp = scope.get_voltage_scale_factor()
    v_offset_perp = scope.get_vertical_offset_volts()
    scope.set_waveform_data_source_single_channel(3)
    v_scale_ref = scope.get_voltage_scale_factor()
    v_offset_ref = scope.get_vertical_offset_volts()
    points = scope.get_waveform_length()
    pre = Preamble(
        time_res,
        v_scale_par,
        v_offset_par,
        v_scale_perp,
        v_offset_perp,
        v_scale_ref,
        v_offset_ref,
        points,
    )
    return pre
