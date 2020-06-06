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
