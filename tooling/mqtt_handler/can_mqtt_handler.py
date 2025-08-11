import os
import threading
from nova_can.utils.compose_system import get_compose_result_from_env
from nova_can.communication import CanReceiver, CanCallback
import json

import paho.mqtt.client as mqtt

# MQTT configuration (can be set via environment variables)
MQTT_BROKER = os.environ.get("NOVA_CAN_MQTT_BROKER", "localhost")
MQTT_PORT = int(os.environ.get("NOVA_CAN_MQTT_PORT", 1883))
MQTT_TOPIC_PREFIX = os.environ.get("NOVA_CAN_MQTT_TOPIC_PREFIX", "rover")

# Set the environment variable
# Required for the system to be composed correctly, change to the path where your systems are located
if 'NOVA_CAN_SYSTEMS_PATH' not in os.environ:   
    os.environ['NOVA_CAN_SYSTEMS_PATH'] = '/home/pih/FYP/nova-can/examples/systems'
if 'NOVA_CAN_INTERFACES_PATH' not in os.environ:
    os.environ['NOVA_CAN_INTERFACES_PATH'] = '/home/pih/FYP/nova-can/examples/interfaces'

# no spaces allowed in .yaml files
# port_type has to be a nova_dsdl type, not nova type
# use start_vcan in tooling to start a virtual CAN interface
# use publish_current_telemtry to publish mock current telemetry data to the CAN bus
# name of canbus in systems file has to match name of canbus.


# class CanCallback(Protocol):
#     def __call__(self, system_name: str, 
#                        device_name: str,
#                        port_name: Port,
#                        data: Dict) -> None:
# 
#         ...

def get_device_type(system_info, device_name: str) -> str:
    if system_info is None:
        raise ValueError("system_info must be provided")

    device = system_info.devices.get(device_name)
    if device is None:
        raise ValueError(f"Device '{device_name}' not found in system '{system_info.name}'")

    # Optional: you can add port-based validation here in the future.
    # e.g. if hasattr(port, "name") and device.can_bus != port.name: ...

    return device.device_type

def can_to_mqtt_callback_factory(system_info):
    def callback(system_name: str, device_name: str, port: object, data: dict):
        dtype = get_device_type(system_info, device_name)
        print("Device Type:", dtype)
        topic = f"{MQTT_TOPIC_PREFIX}.{system_name}.{dtype}.{device_name}.{port.name}"
        topic = topic.lower()
        payload = str(data)
        mqtt_client.publish(topic, payload)
        print(f"Published to MQTT: {topic} -> {payload}")
    return callback

def start_can_receiver(system_info):
    receiver = CanReceiver(system_info, can_to_mqtt_callback_factory(system_info), receiver_id=0)
    receiver.run()

if __name__ == "__main__":
    # Compose system from environment
    compose_result = get_compose_result_from_env()
    if not compose_result or not compose_result.success:
        print(compose_result)
        print(compose_result.errors)
        print("Failed to compose system. Exiting.")
        exit(1)

    system_info = compose_result.system

    for device in system_info.devices.values():
        print(device.device_type)  # dot notation

    # Set up MQTT client
    mqtt_client = mqtt.Client()
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()


    # Start CAN receiver in a separate thread - may need to thread in the future
    # Uncomment the following lines if you want to run the CAN receiver in a separate thread
    # can_thread = threading.Thread(target=start_can_receiver, args=(system_info,), daemon=True)
    # can_thread.start()

    start_can_receiver(system_info)