import time
import numpy as np


class Oscilloscope:
    def __init__(self, instr):
        self._instr = instr

    def cleanup(self):
        self._instr.close()

    ####################################################################################
    # Acquisition Parameters
    ####################################################################################

    def set_hi_res_mode(self):
        self._instr.write("acquire:mode hires")

    def set_single_acquisition_mode(self):
        self._instr.write("acquire:stopafter sequence")

    def set_continuous_acquisition_mode(self):
        self._instr.write("acquire:stopafter runstop")

    def acquisition_start(self):
        self._instr.write("acquire:state run")

    def acquisition_stop(self):
        self._instr.write("acquire:state stop")

    def get_acquisition_state(self):
        return self._instr.query("acquire:state?").lower().strip()

    ####################################################################################
    # Horizontal Parameters
    ####################################################################################

    def set_time_per_div(self, div_time):
        self._instr.write(f"horizontal:main:scale {div_time:.2E}")

    def set_horizontal_position(self, percentage):
        self._instr.write(f"horizontal:position {percentage}")

    def set_horizontal_points(self, points):
        self._instr.write(f"horizontal:resolution {points}")

    def get_time_resolution(self):
        return float(self._instr.query("wfmoutpre:xincr?"))

    ####################################################################################
    # Vertical Parameters
    ####################################################################################

    def set_channel_on(self, channel):
        self._instr.write(f"select:ch{channel} on")

    def set_channel_off(self, channel):
        self._instr.write(f"select:ch{channel} off")

    def set_channels_on(self, channel_list):
        for channel in channel_list:
            self.set_channel_on(channel)

    def set_channels_off(self, channel_list):
        for channel in channel_list:
            self.set_channel_off(channel)

    def set_vertical_scale(self, channel, scale_volts):
        self._instr.write(f"ch{channel}:scale {scale_volts:.4E}")

    def get_vertical_scale(self, channel):
        return float(self._instr.query(f"ch{channel}:scale?"))

    def set_vertical_offset(self, channel, offset_volts):
        self._instr.write(f"ch{channel}:offset {offset_volts:.4E}")

    def get_vertical_offset(self, channel):
        return float(self._instr.query(f"ch{channel}:offset?"))

    def zero_vertical_position(self, channel):
        self._instr.write(f"ch{channel}:position 0")

    def zero_vertical_positions(self, channel_list):
        for channel in channel_list:
            self.zero_vertical_position(channel)

    def zero_all_vertical_positions(self):
        for i in range(1, 5):
            self.zero_vertical_position(i)

    def vertically_center_channel(self, channel):
        avg = self.measure_channel_mean(channel)
        self.set_vertical_offset(channel, avg)

    def get_waveform_voltage_scale_factor(self):
        return float(self._instr.query("wfmoutpre:ymult?"))

    def get_waveform_vertical_offset_dig_levels(self):
        return float(self._instr.query("wfmoutpre:yoff?"))

    def get_waveform_vertical_zero_point(self):
        return float(self._instr.query("wfmoutpre:yzero?"))

    ####################################################################################
    # Measurements
    ####################################################################################

    def turn_off_all_measurements(self):
        for i in range(1, 9):
            self._instr.write(f"measurement:meas{i}:state off")

    def add_displayed_mean_measurement(self, channel, meas_num):
        self._instr.write(f"measurement:meas{meas_num}:source ch{channel}")
        self._instr.write(f"measurement:meas{meas_num}:state on")
        self._instr.write(f"measurement:meas{meas_num}:type mean")

    def add_displayed_max_measurement(self, channel, meas_num):
        self._instr.write(f"measurement:meas{meas_num}:source ch{channel}")
        self._instr.write(f"measurement:meas{meas_num}:state on")
        self._instr.write(f"measurement:meas{meas_num}:type high")

    def add_displayed_min_measurement(self, channel, meas_num):
        self._instr.write(f"measurement:meas{meas_num}:source ch{channel}")
        self._instr.write(f"measurement:meas{meas_num}:state on")
        self._instr.write(f"measurement:meas{meas_num}:type low")

    def get_displayed_measurement_value(self, meas_num):
        return float(self._instr.query(f"measurement:meas{meas_num}:value?"))

    def add_immediate_mean_measurement(self, channel):
        self._instr.write(f"measurement:immed:source ch{channel}")
        self._instr.write("measurement:immed:type mean")

    def add_immediate_max_measurement(self, channel):
        self._instr.write(f"measurement:immed:source ch{channel}")
        self._instr.write("measurement:immed:type high")

    def add_immediate_min_measurement(self, channel):
        self._instr.write(f"measurement:immed:source ch{channel}")
        self._instr.write("measurement:immed:type low")

    def get_immediate_measurement_value(self):
        return float(self._instr.query("measurement:immed:value?"))

    def measure_channel_mean(self, channel):
        self.add_immediate_mean_measurement(channel)
        self.set_scope_to_run()
        self.wait_while_arming()
        self.wait_until_triggered()
        return float(self.get_immediate_measurement_value())

    #################################################
    # Output waveform parameters
    #################################################

    def set_waveform_encoding_ascii(self):
        self._instr.write("data:encdg ascii")

    def set_waveform_encoding_unsigned_le_binary(self):
        self._instr.write("data:encdg srpbinary")

    def set_waveform_encoding_signed_le_binary(self):
        self._instr.write("data:encdg sribinary")

    def set_waveform_encoding_unsigned_be_binary(self):
        self._instr.write("data:encdg rpbinary")

    def set_waveform_encoding_signed_be_binary(self):
        self._instr.write("data:encdg ribinary")

    def get_waveform_encoding(self):
        return self._instr.query("wfmoutpre:encdg?").lower().strip()

    def get_waveform_length(self):
        return int(self._instr.query("wfmoutpre:nr_pt?"))

    ####################################################################################
    # Obtaining Waveforms
    ####################################################################################

    def set_waveform_data_source_single_channel(self, channel):
        self._instr.write(f"data:source ch{channel}")

    def set_waveform_data_source_multiple_channels(self, channel_list):
        channels = ", ".join([f"ch{x}" for x in channel_list])
        self._instr.write(f"data:source {channels}")

    def set_waveform_start_point(self, point):
        self._instr.write(f"data:start {point}")

    def set_waveform_stop_point(self, point):
        self._instr.write(f"data:stop {point}")

    def get_curve(self):
        return self._instr.query_ascii_values("curve?", container=np.array)

    def retrieve_waveform(self):
        value_list = self._instr.query_ascii_values("curve?", delay=0.5)
        array = np.array(value_list)
        y_scale_factor = self.get_waveform_voltage_scale_factor()
        y_offset_volts = self.get_waveform_vertical_zero_point()
        scaled_data = array * y_scale_factor + y_offset_volts
        return scaled_data

    ####################################################################################
    # Triggering
    ####################################################################################

    def set_trigger_source_channel(self, channel):
        self._instr.write(f"trigger:a:edge:source ch{channel}")

    def set_trigger_source_aux(self):
        self._instr.write("trigger:a:edge:source auxiliary")

    def trigger_from_line(self):
        self._instr.write("trigger:a:edge:source line")

    def trigger_on_rising_edge(self):
        self._instr.write("trigger:a:edge:slope rise")

    def trigger_on_falling_edge(self):
        self._instr.write("trigger:a:edge:slope fall")

    def set_trigger_level(self, volts):
        self._instr.write(f"trigger:a:level {volts}")

    def get_trigger_state(self):
        return self._instr.query("trigger:state?").lower().strip()

    def wait_until_triggered(self):
        while self.get_trigger_state() != "save":
            time.sleep(0.01)

    def force_trigger(self):
        self._instr.write("trigger force")
    
    def set_trigger_holdoff(self, t=0.5):
        self._instr.write("trigger:a:holdoff:by time")
        self._instr.write(f"trigger:a:holdoff:time {t}")

    def remove_trigger_holdoff(self):
        self._instr.write("trigger:a:holdoff:by auto")
