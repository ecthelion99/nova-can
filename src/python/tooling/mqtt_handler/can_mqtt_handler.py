import os
import time
import random
import argparse
import json
import threading
import signal

# Flatten nested dictionaries (only dicts are recursively flattened; lists/tuples left as values)
from typing import Any, Dict

from nova_can.utils.compose_system import get_compose_result_from_env
from nova_can.communication import CanReceiver, CanTransmitter, Priority
from paho.mqtt.enums import CallbackAPIVersion
from paho.mqtt import client as mqtt_client


# ---------- Default Configuration (can be overridden via env) ----------
DEFAULT_MQTT_BROKER = os.environ.get("NOVA_CAN_MQTT_BROKER", "localhost")
DEFAULT_MQTT_PORT = int(os.environ.get("NOVA_CAN_MQTT_PORT", 8883))
DEFAULT_MQTT_TOPIC_PREFIX = os.environ.get("NOVA_CAN_MQTT_TOPIC_PREFIX", "rover")
DEFAULT_MQTT_USERNAME = os.environ.get("NOVA_CAN_MQTT_USERNAME", "nova")
DEFAULT_MQTT_PASSWORD = os.environ.get("NOVA_CAN_MQTT_PASSWORD", "rovanova")
DEFAULT_MQTT_RECEIVE_TOPIC = os.environ.get(
    "NOVA_CAN_MQTT_RECEIVE_TOPIC", "rover.command"
)

# Ensure required environment paths exist (can be overridden externally)
os.environ.setdefault(
    "NOVA_CAN_SYSTEMS_PATH", "/home/pih/FYP/nova-can/examples/systems"
)
os.environ.setdefault(
    "NOVA_CAN_INTERFACES_PATH", "/home/pih/FYP/nova-can/examples/interfaces"
)


# ---------- Helper Functions ----------
def get_device_type(system_info, device_name: str) -> str:
    """Retrieve the device type for a given device from the composed system info."""
    if system_info is None:
        raise ValueError("system_info must be provided")

    device = system_info.devices.get(device_name)
    if device is None:
        raise ValueError(
            f"Device '{device_name}' not found in system '{system_info.name}'"
        )

    return device.device_type


def flatten_dict(
    d: Dict[Any, Any], parent_key: str = "", sep: str = "."
) -> Dict[str, Any]:
    """
    Recursively flatten a nested dictionary by joining nested keys with `sep`.
    - Only dictionaries are recursively traversed.
    - Non-dict values (including lists, tuples, etc.) are left as-is.
    - Keys are converted to strings when joined.

    Example:
        {"a": 1, "b": {"x": 2, "y": 3}} -> {"a": 1, "b.x": 2, "b.y": 3}
    """
    items: Dict[str, Any] = {}
    for key, value in d.items():
        new_key = f"{parent_key}{sep}{key}" if parent_key else str(key)
        if isinstance(value, dict):
            # recurse into nested dict
            items.update(flatten_dict(value, new_key, sep=sep))
        else:
            items[new_key] = value
    return items


def all_bools(flat_dict: Dict[str, Any]) -> bool:
    """
    Check whether all values in a flattened dictionary are booleans.
    Accepts both real bools (True/False) and string forms ("true"/"false", case-insensitive).
    """
    for key, value in flat_dict.items():
        if isinstance(value, bool):
            continue
        if isinstance(value, str) and value.lower() in ("true", "false"):
            continue
        return False
    return True


def can_to_mqtt_callback(system_info, client, topic_prefix: str, verbose: bool = True):
    """Create a callback that bridges CAN messages to MQTT."""

    def callback(system_name: str, device_name: str, port: object, data: dict):
        dtype = get_device_type(system_info, device_name)
        topic_base = f"{topic_prefix}.{system_name}.{dtype}.{device_name}.transmit.{port.name}".lower()
        flt_dct = flatten_dict(data)
        payload = 0
        if all_bools(flt_dct) or len(flt_dct) == 1:
            topic = topic_base
            payload = {"timestamp": int(time.time() * 1000)}
            payload.update(flt_dct)
            payload = json.dumps(payload)
            client.publish(topic, payload)
        else:
            ts = int(time.time() * 1000)  # single timestamp for all items
            for key, value in flt_dct.items():
                topic = f"{topic_base}.{key}".lower()
                payload = {"timestamp": ts, key: value}
                payload = json.dumps(payload)
                client.publish(topic, payload)
        if verbose:
            print(f"[CAN to MQTT] Published: {topic} -> {payload}")

    return callback


def setup_mqtt_client(
    broker: str = DEFAULT_MQTT_BROKER,
    port: int = DEFAULT_MQTT_PORT,
    username: str = DEFAULT_MQTT_USERNAME,
    password: str = DEFAULT_MQTT_PASSWORD,
) -> mqtt_client.Client:
    """Set up and connect an MQTT client."""

    def on_connect(client, userdata, flags, rc, properties=None):
        if rc == 0:
            print("[MQTT] Connected successfully")
            # Listen to MQTT topic 'DEFAULT_MQTT_RECEIVE_TOPIC' and bridge to CAN transmitter
            client.subscribe(DEFAULT_MQTT_RECEIVE_TOPIC)
        else:
            print(f"[MQTT] Failed to connect (code {rc})")

    client = mqtt_client.Client(
        client_id=f"nova-can-{random.randint(0, 1000)}",
        transport="websockets",
        callback_api_version=CallbackAPIVersion.VERSION2,
    )
    client.username_pw_set(username, password)
    client.on_connect = on_connect
    client.connect(broker, port)
    return client

# ---------- MQTT-to-CAN Bridge ----------
def mqtt_to_can_callback(can_transmitter, verbose: bool = True):
    """
    Create a callback that bridges MQTT messages to CAN transmitter.
    The callback expects messages in the format:
    {
        "command": "rover.system.device_type.device_name.port",
        ...dsdl_fields
    }
    where dsdl_fields are the fields required by the DSDL definition for that port.
    """

    def on_message(client, userdata, msg):
        try:
            #
            if verbose:
                print(
                    "[MQTT to CAN] mqtt to can received message:",
                    msg.topic,
                    msg.payload.decode(),
                )
            # Parse the incoming MQTT message
            payload = json.loads(msg.payload)

            # Extract command components
            if "command" not in payload:
                if verbose:
                    print("[MQTT to CAN] Error: No command field in message")
                return

            # Parse command path
            command_parts = payload["command"].split(".")
            if (
                len(command_parts) != 6
            ):  # rover.system.device_type.device_name.receive.port_name
                if verbose:
                    print(
                        f"[MQTT to CAN] Error: Invalid command format: {payload['command']}"
                    )
                return

            # Extract device and port info
            _, _, _, device_name, receive, port_name = command_parts

            # Verify that this is a receive command
            if receive.lower() != "receive":
                if verbose:
                    print(
                        f"[MQTT to CAN] Error: Invalid command format, expected 'receive' but got '{receive}'"
                    )
                return

            # Create DSDL data dictionary by removing command field and extracting only the payload sub-dictionary
            dsdl_data = payload.get("payload", {})

            # Send message to CAN bus
            print(
                f"[MQTT to CAN] Transmitting to {device_name} on {port_name} with data {dsdl_data}"
            )
            result = can_transmitter.send_message(
                device_name=device_name,
                port_name=port_name,
                dsdl_data_dict=dsdl_data,
                priority=Priority.Nominal,  # Using default priority
            )

            if result.success:
                if verbose:
                    print(
                        f"[MQTT to CAN] mqtt to can Successfully transmitted {port_name} to {device_name}"
                    )
            else:
                if verbose:
                    print(f"[MQTT to CAN] Failed to transmit: {result.message}")

        except json.JSONDecodeError as e:
            if verbose:
                print(f"[MQTT to CAN] Error decoding JSON message: {e}")
        except Exception as e:
            if verbose:
                print(f"[MQTT to CAN] Error processing message: {e}")

    return on_message

# ---------- Command-Line Interface ----------
def start_gateway_cli():
    parser = argparse.ArgumentParser(
        description="Starts a CAN to MQTT gateway that listens for CAN messages and publishes them via an MQTT broker.\n The file path to the system info (.yaml files) needs to be provided via environment variables.\n NOVA_CAN_INTERFACES_PATH and NOVA_CAN_SYSTEMS_PATH"
    )
    parser.add_argument(
        "-b",
        "--broker",
        type=str,
        default=DEFAULT_MQTT_BROKER,
        help="MQTT broker hostname",
    )
    parser.add_argument(
        "-p", "--port", type=int, default=DEFAULT_MQTT_PORT, help="MQTT broker port"
    )
    parser.add_argument(
        "-u",
        "--username",
        type=str,
        default=DEFAULT_MQTT_USERNAME,
        help="MQTT username",
    )
    parser.add_argument(
        "-P",
        "--password",
        type=str,
        default=DEFAULT_MQTT_PASSWORD,
        help="MQTT password",
    )
    parser.add_argument(
        "-t",
        "--topic-prefix",
        type=str,
        default=DEFAULT_MQTT_TOPIC_PREFIX,
        help="MQTT topic prefix",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print MQTT messages to console, True or False, default False",
    )

    args = parser.parse_args()

    print("Verbosity:", args.verbose)

    compose_result = get_compose_result_from_env()
    if not compose_result or not compose_result.success:
        raise RuntimeError(f"Failed to compose system: {compose_result.errors}")
    system_info = compose_result.system

    

    exit_event = threading.Event()
    def handle_exit(signum, frame):
        exit_event.set()

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    # MQTT to CAN callback setup
    with CanTransmitter(system_info) as can_transmitter:
        mqtt_client_instance = setup_mqtt_client(args.broker, args.port, args.username, args.password)
        mqtt_client_instance.on_message = mqtt_to_can_callback(can_transmitter, args.verbose)
        mqtt_client_instance.loop_start()
        try:
            receiver_callback = can_to_mqtt_callback(system_info, mqtt_client_instance, args.topic_prefix, args.verbose)
            with CanReceiver(system_info, callback=receiver_callback) as can_rx:
                exit_event.wait()
        finally:
            mqtt_client_instance.disconnect()
            mqtt_client_instance.loop_stop(force=True)


# ---------- Default Usage ----------
if __name__ == "__main__":
    start_gateway_cli()
