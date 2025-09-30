from nova_can.communication import CanTransmitter, Priority
from typing import Dict
from nova_can.utils.compose_system import get_compose_result_from_env
import typer
import time
import json
from typing_extensions import Annotated

app = typer.Typer()
compose_result = get_compose_result_from_env()
if compose_result and compose_result.success:
    system_info = compose_result.system
else:
    raise RuntimeError(f"Failed to compose system: {compose_result.errors}")


def complete_device_names(incomplete: str) -> list[str]:
    """
    Autocompletion function for device names.

    Args:
        incomplete (str): The current incomplete input from the user.
    """
    device_names = list(system_info.devices.keys())
    if not incomplete:
        return device_names
    inc = incomplete.lower()
    return [name for name in device_names if name.lower().startswith(inc)]


def complete_port_names(ctx: typer.Context, incomplete: str) -> list[str]:
    """
    Autocompletion function for port names based on the selected device.

    Args:
        ctx (typer.Context): The Typer context to access other parameters.
        incomplete (str): The current incomplete input from the user.
    """
    dev_name = ctx.params.get("device_name") or None
    if dev_name is None:
        return []
    else:
        ports = list(system_info.devices[dev_name].interface.messages.receive.keys())
    if not incomplete:
        return ports
    inc = incomplete.lower()
    return [p for p in ports if p.lower().startswith(inc)]


def dsdl_example(dsdl_type: str) -> Dict:
    """
    Generate example DSDL data for a given DSDL type.

    Args:
        dsdl_type (str): The DSDL type in the format 'namespace.type.version' as specified in interface.yaml.
    """
    pass  # TODO


def complete_dsdl_data_json(ctx: typer.Context, incomplete: str) -> list[str]:
    """
    Autocompletion function for DSDL data JSON based on the selected device and port.

    Args:
        ctx (typer.Context): The Typer context to access other parameters.
        incomplete (str): The current incomplete input from the user.
    """
    dev_name = ctx.params.get("device_name") or None
    port_name = ctx.params.get("port_name") or None
    if dev_name is None or port_name is None:
        return []
    else:
        port = system_info.devices[dev_name].interface.messages.receive[port_name]
        dsdl_type = port.port_type
        example_data = dsdl_example(dsdl_type)
        return [json.dumps(example_data, indent=2)]


@app.command(help="Transmit a CAN message to a device")
def tx(
    device_name: Annotated[
        str,
        typer.Argument(
            help="The name of the device to send the message to as specified in system.yaml",
            autocompletion=complete_device_names,
        ),
    ],
    port_name: Annotated[
        str,
        typer.Argument(
            help="The name of the port to send the message to as specified in interface.yaml",
            autocompletion=complete_port_names,
        ),
    ],
    dsdl_data_json: Annotated[
        str,
        typer.Argument(
            help="The DSDL data to send as a JSON string",
            autocompletion=complete_dsdl_data_json,
        ),
    ],
    priority: Annotated[
        Priority, typer.Option(help="The CAN bus priority of the sent message")
    ] = Priority.Nominal,
    max_attempts: Annotated[
        int, typer.Option(help="Retry attempts for a failed CAN bus transmission")
    ] = 1,
    interval: Annotated[
        float,
        typer.Option(
            help="Time to wait between CAN bus retransmissions attempts (seconds)"
        ),
    ] = 0.5,
):

    # All three arguments are required positionally
    try:
        dsdl_data_dict = json.loads(dsdl_data_json)
    except json.JSONDecodeError as e:
        raise typer.BadParameter(f"Invalid JSON data: {e}")

    transmitter = CanTransmitter(system_info)
    for _ in range(max_attempts):
        result = transmitter.send_message(
            device_name, port_name, dsdl_data_dict, priority
        )
        if result.success:
            print(f"Successfully transmitted {port_name} to {device_name}")
            break
        else:
            print(f"Failed to transmit: {result.message}. Retrying...")
        time.sleep(interval)

    # TODO: Close the CAN bus


@app.command(help="Receive CAN messages from a device")
def rx(
    device_name: Annotated[
        str,
        typer.Option(
            help="The name of the device to send the message to as specified in system.yaml",
            autocompletion=complete_device_names,
        ),
    ],
):
    pass  # TODO: Placeholder for future implementation


if __name__ == "__main__":
    app()
