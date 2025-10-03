from typing import Callable, Dict, Optional
import signal
import threading

import typer
import time
import json
from typing_extensions import Annotated
from rich import print
from rich.pretty import Pretty

from nova_can.communication import CanReceiver, CanTransmitter, Priority
from nova_can.models.device_models import Port
from nova_can.utils.compose_system import get_compose_result_from_env

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

def complete_tx_port_names(ctx: typer.Context, incomplete: str):
        """
        Autocompletion function for port names based on the selected device.

        Args:
            ctx (typer.Context): The Typer context to access other parameters.
            incomplete (str): The current incomplete input from the user.
        """
        dev_name = ctx.params.get("device_name") or None
        from_device = ctx.params.get("from_device") or False
        if dev_name is None:
            return []
        else:
            if from_device:
                ports = list(system_info.devices[dev_name].interface.messages.transmit.keys())
            else:
                ports = list(system_info.devices[dev_name].interface.messages.receive.keys())
            
        if not incomplete:
            return ports
        inc = incomplete.lower()
        return [p for p in ports if p.lower().startswith(inc)]

def complete_rx_port_names(ctx: typer.Context, incomplete: str):
        """
        Autocompletion function for port names based on the selected device.

        Args:
            ctx (typer.Context): The Typer context to access other parameters.
            incomplete (str): The current incomplete input from the user.
        """
        dev_name = ctx.params.get("device_name") or None
        from_device = ctx.params.get("from_device") or False
        if dev_name is None:
            return []
        else:
            if from_device:
                ports = list(system_info.devices[dev_name].interface.messages.receive.keys())
            else:
                ports = list(system_info.devices[dev_name].interface.messages.transmit.keys())
            
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
    from_device = ctx.params.get("from_device") or False
    if dev_name is None or port_name is None:
        return []
    else:
        if from_device:
            port = system_info.devices[dev_name].interface.messages.transmit[port_name]
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
            autocompletion=complete_tx_port_names,
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
    retry_interval: Annotated[
        float,
        typer.Option("--retry-interval", help="Time to wait between retry attempts (seconds)")
    ] = 0.5,
    repeat: Annotated[
        Optional[int],
        typer.Option("--repeat", help="Number of times to send; omit to send once")
    ] = None,
    interval: Annotated[
        Optional[float],
        typer.Option("--interval", help="Period between sends (s); with no --repeat, send perpetually")
    ] = None,
    from_device: Annotated[
        bool,
        typer.Option("--from", help="Interpret device as sender (device perspective)")
    ] = False,
):

    # All three arguments are required positionally
    try:
        dsdl_data_dict = json.loads(dsdl_data_json)
    except json.JSONDecodeError as e:
        raise typer.BadParameter(f"Invalid JSON data: {e}")
    
    if device_name not in system_info.devices:
        raise typer.BadParameter(f"Invalid device name {device_name}")

    if from_device:
        ports = system_info.devices[device_name].interface.messages.transmit
        if port_name not in ports:
            raise typer.BadParameter(f"Invalid port name {port_name} for device {device_name} (expected a transmit port)")
    else:
        ports = system_info.devices[device_name].interface.messages.receive
        if port_name not in ports:
            raise typer.BadParameter(f"Invalid port name {port_name} for device {device_name} (expected a receive port)")
    
    if from_device:
        transmitter_id = system_info.devices[device_name].node_id
    else:
        transmitter_id = 0
        
    with CanTransmitter(system_info, transmitter_id=transmitter_id) as transmitter:
        def attempt_send() -> bool:
            for _ in range(max_attempts):
                result = transmitter.send_message(device_name, port_name, dsdl_data_dict, priority, from_device=from_device)
                if result.success:
                    direction = "from" if from_device else "to"
                    print(f"Successfully transmitted {port_name} {direction} {device_name}")
                    return True
                else:
                    print(f"Failed to transmit: {result.message}. Retrying...")
                time.sleep(retry_interval)
            return False

        if interval is not None and repeat is None:
            while True:
                attempt_send()
                time.sleep(interval)
        else:
            send_count = repeat if repeat is not None else 1
            gap = interval if interval is not None else (1.0 if repeat is not None else None)
            for i in range(send_count):
                attempt_send()
                if gap is not None and i < send_count - 1:
                    time.sleep(gap)





@app.command(help="Receive CAN messages from a device")
def rx(
    device_name: Annotated[
        str,
        typer.Argument(
            help="The name of the device to send the message to as specified in system.yaml",
            autocompletion=complete_device_names,
        ),
    ] = None,
    port_name: Annotated[
        str,
        typer.Argument(
            help="The name of the port to send the message to as specified in interface.yaml",
            autocompletion=complete_rx_port_names,
        ),
    ] = None,
    from_device: Annotated[
        bool,
        typer.Option("--from", help="Interpret device as receiver (device perspective)")
    ] = False,
):
    if device_name is not None:
        device_names = list(system_info.devices.keys())
        if device_name not in device_names:
            raise typer.BadParameter(f"Invalid device name {device_name}")
    
    if port_name is not None:
        if from_device:
            ports = list(system_info.devices[device_name].interface.messages.receive.keys())
        else:
            ports = list(system_info.devices[device_name].interface.messages.transmit.keys())
        if port_name not in ports:
            raise typer.BadParameter(f"Invalid port name {port_name}")


    def rx_callback(system_name: str, device: str, port: Port, data: dict):
        if device_name is not None and device != device_name:
            return
        if port_name is not None and port_name != port.name:
            return
        print(f'{system_name}.{device}.{port.name}: ', Pretty(data), sep='')
           
    exit_event = threading.Event()
    def handle_exit(signum, frame):
        exit_event.set()

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    receiver_id = 0
    if from_device:
        if device_name not in system_info.devices:
            raise typer.BadParameter(f"Invalid device name {device_name}")
        receiver_id = system_info.devices[device_name].node_id
    with CanReceiver(system_info, callback=rx_callback, receiver_id=receiver_id) as can_rx:
        exit_event.wait()


if __name__ == "__main__":
    app()
