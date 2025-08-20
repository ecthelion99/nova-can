import os
import time
import random
from typing import Optional
import argparse

from nova_can.utils.compose_system import get_compose_result_from_env
from nova_can.communication import CanReceiver
from paho.mqtt.enums import CallbackAPIVersion
from paho.mqtt import client as mqtt_client


# ---------- Default Configuration (can be overridden via env) ----------
DEFAULT_MQTT_BROKER = os.environ.get("NOVA_CAN_MQTT_BROKER", "localhost")
DEFAULT_MQTT_PORT = int(os.environ.get("NOVA_CAN_MQTT_PORT", 8883))
DEFAULT_MQTT_TOPIC_PREFIX = os.environ.get("NOVA_CAN_MQTT_TOPIC_PREFIX", "rover")
DEFAULT_MQTT_USERNAME = os.environ.get("NOVA_CAN_MQTT_USERNAME", "nova")
DEFAULT_MQTT_PASSWORD = os.environ.get("NOVA_CAN_MQTT_PASSWORD", "rovanova")

# Ensure required environment paths exist (can be overridden externally)
os.environ.setdefault("NOVA_CAN_SYSTEMS_PATH", "/home/pih/FYP/nova-can/examples/systems")
os.environ.setdefault("NOVA_CAN_INTERFACES_PATH", "/home/pih/FYP/nova-can/examples/interfaces")


# ---------- Helper Functions ----------
def get_device_type(system_info, device_name: str) -> str:
    """Retrieve the device type for a given device from the composed system info."""
    if system_info is None:
        raise ValueError("system_info must be provided")

    device = system_info.devices.get(device_name)
    if device is None:
        raise ValueError(f"Device '{device_name}' not found in system '{system_info.name}'")

    return device.device_type


def can_to_mqtt_callback(system_info, client, topic_prefix: str, verbose: bool = True):
    """Create a callback that bridges CAN messages to MQTT."""
    def callback(system_name: str, device_name: str, port: object, data: dict):
        dtype = get_device_type(system_info, device_name)
        topic = f"{topic_prefix}.{system_name}.{dtype}.{device_name}.{port.name}".lower()
        payload = f'{{"timestamp": {int(time.time() * 1000)}, "value": {data["value"]}}}'
        client.publish(topic, payload)
        if verbose:
            print(f"[CAN→MQTT] Published: {topic} -> {payload}")
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
        else:
            print(f"[MQTT] Failed to connect (code {rc})")

    client = mqtt_client.Client(
        client_id=f'nova-can-{random.randint(0, 1000)}',
        transport="websockets",
        callback_api_version=CallbackAPIVersion.VERSION2,
    )
    client.username_pw_set(username, password)
    client.on_connect = on_connect
    client.connect(broker, port)
    client.loop_start()
    return client


def start_can_receiver(system_info, mqtt_client, topic_prefix: str = DEFAULT_MQTT_TOPIC_PREFIX, verbose: bool = True):
    """Start listening to CAN messages and forwarding them to MQTT."""
    receiver = CanReceiver(system_info, can_to_mqtt_callback(system_info, mqtt_client, topic_prefix, verbose))
    receiver.run()


# ---------- Public API ----------
def start_gateway(
    broker: str = DEFAULT_MQTT_BROKER,
    port: int = DEFAULT_MQTT_PORT,
    username: str = DEFAULT_MQTT_USERNAME,
    password: str = DEFAULT_MQTT_PASSWORD,
    topic_prefix: str = DEFAULT_MQTT_TOPIC_PREFIX,
    verbose: bool = True,
):
    """
    Start the CAN→MQTT gateway.
    :param broker: MQTT broker hostname
    :param port: MQTT broker port
    :param username: MQTT username
    :param password: MQTT password
    :param topic_prefix: Prefix for MQTT topics
    :param system_info: Optional pre-composed system info, otherwise composed from env
    """
    
    compose_result = get_compose_result_from_env()
    if not compose_result or not compose_result.success:
        raise RuntimeError(f"Failed to compose system: {compose_result.errors}")
    system_info = compose_result.system

    mqtt_client_instance = setup_mqtt_client(broker, port, username, password)
    start_can_receiver(system_info, mqtt_client_instance, topic_prefix, verbose)


# ---------- Command-Line Interface ----------
def start_gateway_cli():
    parser = argparse.ArgumentParser(
        description="Starts a CAN to MQTT gateway that listens for CAN messages and publishes them via an MQTT broker.\n The file path to the system info (.yaml files) needs to be provided via environment variables.\n NOVA_CAN_INTERFACES_PATH and NOVA_CAN_SYSTEMS_PATH"
    )
    parser.add_argument("-b", "--broker", type=str, default=DEFAULT_MQTT_BROKER, help="MQTT broker hostname")
    parser.add_argument("-p", "--port", type=int, default=DEFAULT_MQTT_PORT, help="MQTT broker port")
    parser.add_argument("-u", "--username", type=str, default=DEFAULT_MQTT_USERNAME, help="MQTT username")
    parser.add_argument("-P", "--password", type=str, default=DEFAULT_MQTT_PASSWORD, help="MQTT password")
    parser.add_argument("-t", "--topic-prefix", type=str, default=DEFAULT_MQTT_TOPIC_PREFIX, help="MQTT topic prefix")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print MQTT messages to console, True or False, default False")

    args = parser.parse_args()

    # Compose system_info from env if needed
    start_gateway(
        broker=args.broker,
        port=args.port,
        username=args.username,
        password=args.password,
        topic_prefix=args.topic_prefix,
        verbose=args.verbose
    )

# ---------- Default Usage ----------
if __name__ == "__main__":
    start_gateway(verbose=True)
