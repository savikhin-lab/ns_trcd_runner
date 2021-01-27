# ns_trcd_runner

This is a GUI-less version of the program that collects data in the nanosecond TRCD experiments.

## Dependencies
You'll need `pyvisa`, `numpy`, `pyserial`, and Python 3.7+. 

The recommended method of installing dependencies is `poetry`. If you have the `poetry` virtual environment manager, you can get started with
```
$ poetry install
```

This will read the `pyproject.toml` file and install the dependencies. If you're not using `poetry`, then you can install the depedencies using `pip` or `conda`, though the versions installed are not guaranteed to be compatible.
```
$ python -m pip install --user numpy pyserial pyvisa
```

## Running the program
Run the program as a Python module:
```
$ python -m ns_trcd_runner -o <output dir> -n <num measurements>
```

If you're using `poetry` you must use `poetry run` to run the program.
```
$ poetry run python -m ns_trcd_runner -o <output dir> -n <num measurements>
```

## Oscilloscope
Getting the oscilloscope set up properly can be tricky as there are lots of interactions between this software, the configurations of the host computer and the oscilloscope, drivers, etc.

### IP address
At different points in time it's been necessary to set a static IP address on the oscilloscope, or let the IP address be configured by Windows (the default). If you're having an issue connecting, try switching between static and dynamic IP addresses on the oscilloscope.

### VXI-11 server
The VXI-11 server is a program included with the oscilloscope and allows it to receive commands over an ethernet connection. If you're having connection issues, make sure this program is running (it will appear in the system tray). The program should start when the oscilloscope is powered on.

## VISA drivers
The VISA driver is what lets you send commands from the computer to the oscilloscope. VISA is a protocol/interface, so there can be multiple implementations. Tektronix provides an implementation called TekVISA, which we originally used. At some point there was an error and we switched to the National Instruments VISA driver.

The oscilloscope is not automatically detected with the NI-VISA driver, so you must add it manually. To add the instrument, open NI MAX and find "My System > Devices and Interfaces > Network Devices". Right-click on "Network Devices" and select "Create New VISA TCP/IP Resource...". This will open a wizard for adding the instrument. It will try to detect the instrument automatically, but it will fail. Follow the instructions in the wizard to add the instrument manually.

## Shutter driver
In order to collect the dark signals you need to be able to collect measurements with the shutter closed. The "MODE" switch on the front of the shutter driver must be set to "B". In this mode the shutter will be enabled only while +8V DC is applied to pin 4 of the terminal block on the front of the shutter driver. We apply this voltage with a National Instruments USB-6003 device, which has programmable analog outputs. Connect the "AO/ao0" pin of the NI device to pin 4 and the "AO/gnd" pin to pin 3. You can use the provided NI software to switch the analog output between +8V DC and 0V DC to make sure that the shutter is disabled properly without needing to run a full experiment.
