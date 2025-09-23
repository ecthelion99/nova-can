# Nova Can Environment Setup

Follow these steps to set up a development environment for this project.

## 1. Create a Python virtual environment

From the project root run:

```bash
python -m venv .venv
```

## 2. Add required environment variables to the venv activate script

Replace the example paths below with the correct absolute paths for your machine.

- Linux  (edit .venv/bin/activate):

```bash
export PYTHONPATH=/home/username/path/to/nova-can/dsdl_python_bindings:$PYTHONPATH
export NOVA_CAN_SYSTEMS_PATH=/home/username/path/to/nova-can/examples/systems
export NOVA_CAN_INTERFACES_PATH=/home/username/path/to/nova-can/examples/interfaces
export NOVA_DATABASE_PATH=/home/username/path/to/nova-can/examples/databases/nova.db
```


## 3. Activate the virtual environment

- Linux:

```bash
source .venv/bin/activate
```

## 4. Install the package in editable mode

```bash
pip install -e .
```

## 5. Generate Python bindings

From the project root directory run:

```bash
nnvg --target-language py --outdir dsdl_python_bindings examples/dsdl/nova_dsdl
```

Notes

- Update the paths in the activate script to match your local repository layout.
- If you prefer not to modify the activate script, you can export/set the environment variables manually in your shell before activating or starting
