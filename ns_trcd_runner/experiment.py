import itertools
import sys
import time
import click
import notifiers
import numpy as np
from dataclasses import dataclass
from typing import Tuple, Union
from nidaqmx import Task


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


@dataclass
class DarkSignals:
    """Dark signals collected between measurements.
    """
    par: float
    perp: float
    ref: float


def measure_multiwl(scope, etalon, outdir, num_meas, wls, chunk_size=10, phone_num=None) -> None:
    """Measure at multiple wavelengths.
    """
    initialize_scope_settings(scope)
    scope.acquisition_start()
    preamble = get_scope_preamble(scope)
    bar_length = num_meas * len(wls)
    with click.progressbar(length=bar_length, label="Measuring") as bar:
        for meas_chunk in iter_chunks(range(num_meas), chunk_size):
            # Create the directory structure for this chunk
            for shot in meas_chunk:
                shot_dir = outdir / f"{shot:04d}"
                shot_dir.mkdir(exist_ok=True)
                for w in wls:
                    wl_dir = shot_dir / f"{int(np.floor(w*100))}"
                    wl_dir.mkdir(exist_ok=True)
            # Take the measurements
            for w in wls:
                etalon.move_wl(w)
                dark_sigs = measure_dark_signals(scope)
                for shot in meas_chunk:
                    scope.acquisition_start()
                    scope.wait_until_triggered()
                    digitizer_levels = acquire_signals(scope)
                    meas = compute_signals(preamble, digitizer_levels, dark_sigs=dark_sigs)
                    meas_dir = outdir / f"{shot:04d}" / f"{int(np.floor(w*100))}"
                    save_measurement(meas, meas_dir)
                    bar.update(1)
    if phone_num:
        twilio = notifiers.get_notifier("twilio")
        twilio.notify(message="Experiment complete", to=phone_num)
    return


def measure_dark_signals(scope) -> DarkSignals:
    """Measure the dark signals while the laser isn't present
    """
    settings = list()
    for chan in range(1, 4):
        # Store current settings
        chan_settings = {}
        chan_settings["offset"] = scope.get_vertical_offset(chan)
        chan_settings["scale"] = scope.get_vertical_scale(chan)
        settings.append(chan_settings)
        # Set offset and scale for measurements close to zero
        scope.set_vertical_offset(chan, 0)
        scope.set_vertical_scale(chan, 5e-3)
    preamble = get_scope_preamble(scope)
    with Task() as task:
        task.ao_channels.add_ao_voltage_chan("Dev1/ao0")
        task.write(0)
        task.start()
        time.sleep(0.6)
        scope.wait_until_triggered()
        dark_par = scope.get_displayed_measurement_value(1)
        dark_perp = scope.get_displayed_measurement_value(2)
        dark_ref = scope.get_displayed_measurement_value(3)
        dark_sigs = DarkSignals(dark_par, dark_perp, dark_ref)
    with Task() as task:
        task.ao_channels.add_ao_voltage_chan("Dev1/ao0")
        task.write(8, auto_start=True)
    # Restore previous settings
    for chan in range(1, 4):
        scope.set_vertical_offset(chan, settings[chan - 1]["offset"])
        scope.set_vertical_scale(chan, settings[chan - 1]["scale"])
    return dark_sigs


def make_measurement_dirs(outdir, n, wls) -> None:
    for shot in range(1, n+1):
        shot_dir = outdir / str(shot)
        shot_dir.mkdir()
        for wavelength in wls:
            wl_dir = shot_dir / f"{wavelength:.2f}"
            wl_dir.mkdir()
    return


def save_measurement(meas, root) -> None:
    """Save a measurement taken from a single 'with pump' shot.
    """
    np.save(root / "par.npy", meas.par)
    np.save(root / "perp.npy", meas.perp)
    np.save(root / "ref.npy", meas.ref)
    return


def compute_signals(pre, channels, dark_sigs=None) -> Measurement:
    if dark_sigs is not None:
        par = pre.v_scale_par * channels.par + pre.v_offset_par - dark_sigs.par
        perp = pre.v_scale_perp * channels.perp + pre.v_offset_perp - dark_sigs.perp
        ref = pre.v_scale_ref * channels.ref + pre.v_offset_ref - dark_sigs.ref
    else:
        par = pre.v_scale_par * channels.par + pre.v_offset_par
        perp = pre.v_scale_perp * channels.perp + pre.v_offset_perp
        ref = pre.v_scale_ref * channels.ref + pre.v_offset_ref
    meas = Measurement(par, perp, ref)
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


def initialize_scope_settings(scope) -> None:
    """Make sure the oscilloscope settings are set for experiment conditions.
    """
    scope.set_hi_res_mode()
    scope.set_single_acquisition_mode()
    scope.set_waveform_data_source_single_channel(1)
    scope.set_waveform_encoding_ascii()
    scope.set_waveform_start_point(1)
    scope.set_waveform_stop_point(scope.get_waveform_length())
    scope.set_waveform_start_point(1)
    scope.set_waveform_stop_point(10_000_000)
    scope.turn_off_all_measurements()
    scope.add_displayed_mean_measurement(1, 1)
    scope.add_displayed_mean_measurement(2, 2)
    scope.add_displayed_mean_measurement(3, 3)
    return


def get_scope_preamble(scope) -> Preamble:
    """Get the data needed to reconstruct a signal from the oscilloscope.
    """
    time_res = scope.get_time_resolution()
    scope.set_waveform_data_source_single_channel(1)
    v_scale_par = scope.get_waveform_voltage_scale_factor()
    v_offset_par = scope.get_waveform_vertical_offset_volts()
    scope.set_waveform_data_source_single_channel(2)
    v_scale_perp = scope.get_waveform_voltage_scale_factor()
    v_offset_perp = scope.get_waveform_vertical_offset_volts()
    scope.set_waveform_data_source_single_channel(3)
    v_scale_ref = scope.get_waveform_voltage_scale_factor()
    v_offset_ref = scope.get_waveform_vertical_offset_volts()
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


def iter_chunks(iterable, size):
    """Returns chunks of an iterable at a time.
    """
    it = iter(iterable)
    while True:
        chunk = tuple(itertools.islice(it, size))
        if len(chunk) == 0:
            break
        yield chunk
