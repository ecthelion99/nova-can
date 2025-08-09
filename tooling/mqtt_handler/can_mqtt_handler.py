import os
import threading
from nova_can.utils.compose_system import get_compose_result_from_env
from nova_can.communication import CanReceiver, CanCallback

import paho.mqtt.client as mqtt

# MQTT configuration (can be set via environment variables)
MQTT_BROKER = os.environ.get("NOVA_CAN_MQTT_BROKER", "localhost")
MQTT_PORT = int(os.environ.get("NOVA_CAN_MQTT_PORT", 1883))
MQTT_TOPIC_PREFIX = os.environ.get("NOVA_CAN_MQTT_TOPIC_PREFIX", "nova_can")

# Set the environment variable
# Required for the system to be composed correctly, change to the path where your systems are located
if 'NOVA_CAN_SYSTEMS_PATH' not in os.environ:   
    os.environ['NOVA_CAN_SYSTEMS_PATH'] = '/home/pih/FYP/nova-can/spec/systems'


def can_to_mqtt_callback(system_name: str, device_name: str, port: object, data: dict):
    """
    Callback function for CanReceiver.
    Publishes received CAN messages to MQTT.
    """
    topic = f"{MQTT_TOPIC_PREFIX}/{system_name}/{device_name}/{port.name}"
    payload = str(data)
    mqtt_client.publish(topic, payload)
    print(f"Published to MQTT: {topic} -> {payload}")

def start_can_receiver(system_info):
    receiver = CanReceiver(system_info, can_to_mqtt_callback)
    receiver.run()

if __name__ == "__main__":
    # Compose system from environment
    compose_result = get_compose_result_from_env()
    if not compose_result or not compose_result.success:
        print("Failed to compose system. Exiting.")
        exit(1)

    system_info = compose_result.system

    # Set up MQTT client
    mqtt_client = mqtt.Client()
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()

    # Start CAN receiver in a separate thread
    can_thread = threading.Thread(target=start_can_receiver, args=(system_info,), daemon=True)
    can_thread.start()

    print("CAN to MQTT handler running. Press Ctrl+C to exit.")
    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("Exiting...")