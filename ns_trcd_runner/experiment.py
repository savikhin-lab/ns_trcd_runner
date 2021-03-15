import itertools
import time
import click
import notifiers
import numpy as np
from dataclasses import dataclass
from typing import Dict, List
from nidaqmx import Task


@dataclass
class Preamble:
    """Data needed to reconstruct oscilloscope signals from digitizer levels.
    """

    t_res: float
    v_scale_par: float
    v_zero_par: float
    v_offset_par: float
    v_scale_perp: float
    v_zero_perp: float
    v_offset_perp: float
    v_scale_ref: float
    v_zero_ref: float
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
class Voltages:
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


def measure_multiwl(scope,
                    etalon,
                    outdir,
                    num_meas,
                    wls,
                    chunk_size=10,
                    phone_num=None,
                    dark_traces=None) -> None:
    """Measure at multiple wavelengths.
    """
    initialize_scope_settings(scope)
    scope.acquisition_start()
    bar_length = num_meas * len(wls)
    dark_sig_records = np.empty((num_meas, len(wls), 3))
    with click.progressbar(length=bar_length, label="Measuring") as bar:
        for meas_chunk in iter_chunks(range(num_meas), chunk_size):
            # Create the directory structure for this chunk
            for shot in meas_chunk:
                shot_dir = outdir / shot_to_str(shot)
                shot_dir.mkdir(exist_ok=True)
                for w in wls:
                    wl_dir = shot_dir / wl_to_str(w)
                    wl_dir.mkdir(exist_ok=True)
            # The motor doesn't accurately move backwards, so you always need
            # to start short of your target wavelength and then move towards it.
            etalon.move(0)
            time.sleep(2)
            # Take the measurements
            for wl_idx, w in enumerate(wls):
                # dark_sigs = measure_dark_while_moving(etalon, w, scope)
                etalon.move_wl(w)
                dark_sigs = measure_dark_signals(scope)
                time.sleep(1)  # This is to solve some timing issue
                optimize_vertical_scale(scope)
                preamble = get_scope_preamble(scope)
                for shot in meas_chunk:
                    scope.acquisition_start()
                    scope.wait_until_triggered()
                    digitizer_levels = transfer_signals_from_scope(scope)
                    meas = reconstruct_voltages_from_dig_levels(
                        preamble, digitizer_levels)
                    meas_dir = outdir / shot_to_str(shot) / wl_to_str(w)
                    save_measurement(meas, meas_dir)
                    dark_sig_records[shot, wl_idx, 0] = dark_sigs.par
                    dark_sig_records[shot, wl_idx, 1] = dark_sigs.perp
                    dark_sig_records[shot, wl_idx, 2] = dark_sigs.ref
                    bar.update(1)
    save_dark_sigs(outdir, dark_sig_records)
    if dark_traces is not None:
        etalon.move(850)
        time.sleep(5)
        measure_spike(outdir, scope, dark_traces)
    if phone_num:
        twilio = notifiers.get_notifier("twilio")
        twilio.notify(message="Experiment complete", to=phone_num)
    return


def measure_spike(out_dir, scope, n) -> None:
    """Measure traces with just the pump pulse and no probe.
    """
    dark_dir = out_dir / "_dark"
    dark_dir.mkdir(exist_ok=True)
    optimize_vertical_scale(scope)
    pre = get_scope_preamble(scope)
    with Task() as task:
        task.ao_channels.add_ao_voltage_chan("Dev1/ao0")
        task.write(0)
        task.start()
        with click.progressbar(range(n), label="Measuring dark traces") as indices:
            for i in indices:
                scope.acquisition_start()
                scope.wait_until_triggered()
                dig_levels = transfer_signals_from_scope(scope)
                meas = reconstruct_voltages_from_dig_levels(pre, dig_levels)
                meas_dir = dark_dir / shot_to_str(i)
                meas_dir.mkdir(exist_ok=True)
                save_measurement(meas, meas_dir)
    with Task() as task:
        task.ao_channels.add_ao_voltage_chan("Dev1/ao0")
        task.write(8, auto_start=True)


def save_dark_sigs(outdir, dark_sigs) -> None:
    """Save the dark signals into a JSON file.
    """
    outfile = outdir / "dark_sigs.npy"
    np.save(outfile, dark_sigs)
    return


def wl_to_str(w: float) -> str:
    """Convert a wavelength to its string representation.

    This turns a wavelength into a string representation suitable for
    filenames, directory names, etc.
    """
    return f"{int(np.floor(w*100))}"


def wl_to_int(w: float) -> int:
    """Convert a wavelength to an integer so that there are no decimals.
    """
    return int(np.floo(w * 100))


def shot_to_str(shot: int) -> str:
    """Convert a shot number to its string representation.

    This turns a shot number into a string representation suitable for
    filenames, directory names, etc.
    """
    return f"{shot+1:04d}"


def get_vertical_res_settings(scope) -> List[Dict[str, float]]:
    """Returns the vertical settings for each data channel.
    """
    settings = list()
    for chan in range(1, 4):
        chan_settings = {}
        chan_settings["offset"] = scope.get_vertical_offset(chan)
        chan_settings["scale"] = scope.get_vertical_scale(chan)
        settings.append(chan_settings)
    return settings


def set_vertical_scale_for_measuring_offsets(scope, scale=100e-3) -> None:
    """Sets the vertical resolution for each data channel large enough that
    the mean of each channel can be measured."""
    for chan in range(1, 4):
        scope.set_vertical_offset(chan, 0)
        scope.set_vertical_scale(chan, scale)
    return


def set_vertical_scale_for_exp_signals(scope,
                                       offsets: List[float],
                                       scale=10e-3) -> None:
    """Set the vertical scale for measuring signals.
    """
    for chan in range(1, 4):
        scope.set_vertical_offset(chan, offsets[chan - 1])
        scope.set_vertical_scale(chan, scale)
    return


def set_vertical_scale_for_dark_signals(scope) -> None:
    """Set the vertical scale for measuring dark signals.
    """
    for chan in range(1, 4):
        scope.set_vertical_offset(chan, 0)
        scope.set_vertical_scale(chan, 2e-3)
    return


def optimize_vertical_scale(scope) -> None:
    """Set the DC offset such that the signals fit on the screen with the
    smallest possible vertical resolution.
    """
    # Do a coarse measurement
    set_vertical_scale_for_measuring_offsets(scope, scale=100e-3)
    preamble = get_scope_preamble(scope)
    scope.acquisition_start()
    scope.wait_until_triggered()
    digitizer_levels = transfer_signals_from_scope(scope)
    voltages = reconstruct_voltages_from_dig_levels(preamble, digitizer_levels)
    set_vertical_scale_for_exp_signals(
        scope,
        [voltages.par.mean(),
         voltages.perp.mean(),
         voltages.ref.mean()],
        scale=10e-3)
    return


def measure_dark_signals(scope) -> DarkSignals:
    """Disable the shutter and collect dark signals.
    """
    set_vertical_scale_for_dark_signals(scope)
    preamble = get_scope_preamble(scope)
    with Task() as task:
        task.ao_channels.add_ao_voltage_chan("Dev1/ao0")
        task.write(0)
        task.start()
        scope.acquisition_start()
        scope.wait_until_triggered()
        digitizer_levels = transfer_signals_from_scope(scope)
        voltages = reconstruct_voltages_from_dig_levels(
            preamble, digitizer_levels)
        dark_sigs = DarkSignals(voltages.par.mean(), voltages.perp.mean(),
                                voltages.ref.mean())
    with Task() as task:
        task.ao_channels.add_ao_voltage_chan("Dev1/ao0")
        task.write(8, auto_start=True)
    return dark_sigs


def measure_dark_while_moving(et, w, scope) -> DarkSignals:
    """Disable the shutter and collect dark signals while the motor moves.
    """
    set_vertical_scale_for_dark_signals(scope)
    with Task() as task:
        task.ao_channels.add_ao_voltage_chan("Dev1/ao0")
        task.write(0)
        task.start()
        scope.acquisition_start()
        time_start = time.time_ns()
        et.move_wl(w)
        # The oscilloscope takes some time to update the built-in measurements
        while (time.time_ns() - time_start) < 1e9:
            time.sleep(0.01)
        dark_par = scope.get_displayed_measurement_value(1)
        dark_perp = scope.get_displayed_measurement_value(2)
        dark_ref = scope.get_displayed_measurement_value(3)
        dark_sigs = DarkSignals(dark_par, dark_perp, dark_ref)
    with Task() as task:
        task.ao_channels.add_ao_voltage_chan("Dev1/ao0")
        task.write(8, auto_start=True)
    return dark_sigs


def make_measurement_dirs(outdir, n, wls) -> None:
    for shot in range(1, n + 1):
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


def reconstruct_voltages_from_dig_levels(pre,
                                         channels,
                                         dark_sigs=None) -> Voltages:
    if dark_sigs is not None:
        par = pre.v_scale_par * (channels.par - pre.v_offset_par) + pre.v_zero_par - dark_sigs.par
        perp = pre.v_scale_perp * (channels.perp - pre.v_offset_perp) + pre.v_zero_perp - dark_sigs.perp
        ref = pre.v_scale_ref * (channels.ref - pre.v_offset_ref) + pre.v_zero_ref - dark_sigs.ref
    else:
        par = pre.v_scale_par * (channels.par - pre.v_offset_par) + pre.v_zero_par
        perp = pre.v_scale_perp * (channels.perp - pre.v_offset_perp) + pre.v_zero_perp
        ref = pre.v_scale_ref * (channels.ref - pre.v_offset_ref) + pre.v_zero_ref
    meas = Voltages(par, perp, ref)
    return meas


def transfer_signals_from_scope(scope) -> DigitizerLevels:
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
    scope.zero_all_vertical_positions()
    scope.set_trigger_holdoff()
    return


def get_scope_preamble(scope) -> Preamble:
    """Get the data needed to reconstruct a signal from the oscilloscope.
    """
    time_res = scope.get_time_resolution()
    scope.set_waveform_data_source_single_channel(1)
    v_scale_par = scope.get_waveform_voltage_scale_factor()
    v_zero_par = scope.get_waveform_vertical_zero_point()
    v_offset_par = scope.get_waveform_vertical_offset_dig_levels()
    scope.set_waveform_data_source_single_channel(2)
    v_scale_perp = scope.get_waveform_voltage_scale_factor()
    v_zero_perp = scope.get_waveform_vertical_zero_point()
    v_offset_perp = scope.get_waveform_vertical_offset_dig_levels()
    scope.set_waveform_data_source_single_channel(3)
    v_scale_ref = scope.get_waveform_voltage_scale_factor()
    v_zero_ref = scope.get_waveform_vertical_zero_point()
    v_offset_ref = scope.get_waveform_vertical_offset_dig_levels()
    points = scope.get_waveform_length()
    pre = Preamble(
        time_res,
        v_scale_par,
        v_zero_par,
        v_offset_par,
        v_scale_perp,
        v_zero_perp,
        v_offset_perp,
        v_scale_ref,
        v_zero_ref,
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
