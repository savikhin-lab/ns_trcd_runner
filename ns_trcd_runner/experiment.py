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
    """Reconstructed signals for a measurement taken with only a 'with pump' shot.
    """
    par: np.ndarray
    perp: np.ndarray
    ref: np.ndarray
    da: np.ndarray
    cd: np.ndarray


def measure(scope, shutter, delta, outdir, n) -> None:
    initialize_scope_settings(scope)
    scope.acquisition_start()
    preamble = get_scope_preamble(scope)
    count = 0
    while True:
        scope.acquisition_start()
        wait_until_triggered(scope)
        digitizer_levels = acquire_signals(scope)
        meas = compute_da(preamble, delta, digitizer_levels)
        count += 1
        save_measurement(meas, outdir, count)
        print(f"Completed {count}/{n}")
        if count == n:
            return


def save_measurement(meas, root, count):
    """Save a measurement taken from a single 'with pump' shot.
    """
    out = root / str(count)
    out.mkdir()
    np.save(out / "par.npy", meas.par)
    np.save(out / "perp.npy", meas.perp)
    np.save(out / "ref.npy", meas.ref)
    np.save(out / "da.npy", meas.da)
    np.save(out / "cd.npy", meas.cd)
    return


def compute_da(pre, delta, channels) -> Measurement:
    par = pre.v_scale_par * channels.par + pre.v_offset_par
    perp = pre.v_scale_perp * channels.perp + pre.v_offset_perp
    ref = pre.v_scale_ref * channels.ref + pre.v_offset_ref
    divided_par = par / ref
    num_points = len(divided_par)
    da_without_pump = np.mean(divided_par[:int(np.floor(0.09*num_points))])
    da = -np.log10(divided_par / da_without_pump)
    divided_perp = perp / par
    cd_without_pump = np.mean(divided_perp[:int(np.floor(0.09*num_points))])
    cd = (4 / (2.3 * delta)) * (divided_perp - cd_without_pump)
    meas = Measurement(par, perp, ref, da, cd)
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
