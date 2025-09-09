nova-can CLI
=============

Overview
--------
`nova-can` is a small Typer-based CLI wrapper that runs the `nova_can_cli` Typer app.
The launcher script is `nova-can` (a tiny executable that calls `nova_can_cli.app`).

This README explains how to make the CLI runnable from your shell, how to ensure Python can import `nova_can_cli`, and how to get help from the Typer-generated CLI.

Checklist
---------
- Make the `nova-can` launcher executable
- Ensure Python can import `nova_can_cli` (PYTHONPATH)
- Add the launcher directory to your `PATH` so you can type `nova-can` anywhere
- Access Typer help for commands and subcommands

Prerequisites
-------------
- A Python environment (virtualenv or system Python). Example venv in this repo: `/home/pi/myenv`.
- Optional: install required python packages in your environment (project's `requirements.txt` or using `pip install -e`).

Make the launcher executable
---------------------------
The launcher script is located at:

`/home/pi/nova-can/src/python/tooling/nova_can_cli/nova-can`

Make sure it has a valid shebang (it should look like `#!/home/pi/myenv/bin/python` or `#!/usr/bin/env python3`). Then make it executable:

```bash
chmod +x /home/pi/nova-can/src/python/tooling/nova_can_cli/nova-can
```

Add `nova_can_cli` to PYTHONPATH
-------------------------------
The `nova-can` launcher does "from nova_can_cli import app". When you run the launcher from a directory that is not the same folder as `nova_can_cli.py`, Python may not find the module. Add the folder containing `nova_can_cli.py` to `PYTHONPATH` so Python can import it from anywhere.

Add this to your `~/.bashrc` or `~/.profile` (adjust the path if you placed the code elsewhere):

```bash
# make sure python can import the CLI module
export PYTHONPATH="$PYTHONPATH:/home/pi/nova-can/src/python/tooling/nova_can_cli"
```

Then reload your shell settings:

```bash
source ~/.bashrc
```

Alternative (recommended for development): install the package or the CLI in editable mode so imports work automatically:

```bash
# from repository root (if a proper setup.py/pyproject exists)
cd /home/pi/nova-can
pip install -e src/python
# or install just requirements for running the CLI
pip install -r requirements.txt
```

Add the launcher to your PATH
----------------------------
So you can simply type `nova-can` from any folder, add the folder that contains the `nova-can` script to your `PATH`:

```bash
# add to PATH in ~/.bashrc
export PATH="$PATH:/home/pi/nova-can/src/python/tooling/nova_can_cli"
source ~/.bashrc
```

Verify the shell sees the command:

```bash
type -a nova-can
which -a nova-can
readlink -f "$(which nova-can)"  # show the real path
```

Run the CLI
-----------
Activate your virtualenv if required, then run the CLI or ask for help:

```bash
# activate venv (example)
source /home/pi/myenv/bin/activate

# show top-level help
nova-can --help

# show help for a subcommand (example)
nova-can tx --help

# run a command
nova-can tx --device-name mydevice --port-name myport --data '{"foo": 1}'
```

Typer help and documentation
----------------------------
Typer auto-generates help text based on your app and options. The `--help` flag is the primary way to access usage information:

```bash
nova-can --help            # top-level commands and options
nova-can <command> --help  # help for a specific subcommand
```

If you want to inspect the Typer library documentation locally, you can use Python's `pydoc` or `help()`:

```bash
# view docstring using pydoc
python -m pydoc typer

# or interactively
python -c "import typer; help(typer)"
```

Troubleshooting
---------------
- "module 'can' has no attribute 'Bus'": a local module named `can` may be shadowing the external `python-can` package — check `import can; print(can.__file__)` to see which file is being imported. Rename any local `can.py` or package named `can`.

- "Bad interpreter" or `^M` errors: convert Windows CRLF to LF with `dos2unix`.

- Command not found: ensure the `nova-can` script folder is in your `PATH` and that the file is executable.

- Import errors for `nova_can_cli`: ensure the folder containing `nova_can_cli.py` is on `PYTHONPATH` or install the package in editable mode.

Quick checks
------------
```bash
# check executable and location
ls -l /home/pi/nova-can/src/python/tooling/nova_can_cli/nova-can

# check which file Python uses for imports
python - <<'PY'
import nova_can_cli, sys
print('module:', nova_can_cli)
print('file:', getattr(nova_can_cli, '__file__', None))
PY

# check python-can (SocketCAN) availability
python - <<'PY'
import can
print('can module file:', getattr(can, '__file__', None))
print('has Bus?', hasattr(can, 'Bus'))
PY
```

Contact / Notes
----------------
This CLI is a thin wrapper around the Typer app defined in `nova_can_cli.py`. For development, using `pip install -e` is usually more convenient than manually manipulating `PYTHONPATH` and `PATH`.

If you want, I can add a simple `setup.cfg`/`pyproject.toml` and an entry-point so `pip install .` will create the `nova-can` console script automatically.
