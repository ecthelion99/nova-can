nova_can CLI
=============

Overview
--------
`nova_can` is a small Typer-based CLI wrapper that runs the `nova_can_cli` Typer app.

This README explains how to make the CLI runnable from your shell and how to get help from the Typer-generated CLI.

Prerequisites
-------------
- A Python environment (virtualenv or system Python) with the required packages. Refer to [DEV_ENV_SETUP.md](../../../../DEV_ENV_SETUP.md).

Run the CLI
-----------
Activate your virtualenv if required, then run the CLI or ask for help:

```bash
# activate venv (example)
source /home/pi/myenv/bin/activate

# install Typer autocompletion
nova_can --install-completion

# show top-level help
nova_can --help

# show help for a subcommand (example)
nova_can tx --help

# run a command (positional form)
nova_can tx mydevice myport '{"foo": 1}'
```

Typer help and documentation
----------------------------
Typer auto-generates help text based on your app and options. The `--help` flag is the primary way to access usage information:

```bash
nova_can --help            # top-level commands and options
nova_can <command> --help  # help for a specific subcommand
```
