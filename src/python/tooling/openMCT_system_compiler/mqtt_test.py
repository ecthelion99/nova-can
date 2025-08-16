import json
import random
import time
import math
import os

from paho.mqtt import client as mqtt_client
from paho.mqtt.enums import CallbackAPIVersion, MQTTErrorCode

# MQTT broker configuration
BROKER = 'localhost'
PORT = 8081  # 8080 for WebSockets or 1883 if using TCP
USERNAME = 'nova'
PASSWORD = 'rovanova'

# Path to the generated rover structure JSON in the script's directory
# Script must reside in same directory as the JSON file.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROVER_JSON_PATH = os.path.join(SCRIPT_DIR, 'systems_grouped.json')

# Publishing interval (in seconds)
PUBLISH_INTERVAL = 0.5  # adjust as needed


def load_measurement_keys(json_path):
    """
    Loads the rover JSON structure and extracts all measurement keys.
    Returns:
        List[str]: A list of topic strings corresponding to each measurement key.
    """
    with open(json_path, 'r') as f:
        data = json.load(f)

    keys = []
    # Drill down: rover -> systems -> types -> devices -> measurements
    for system in data.get('folders', []):  # each system
        for dtype in system.get('folders', []):  # each device type
            for device in dtype.get('folders', []):  # each device
                for meas in device.get('measurements', []):  # each measurement
                    keys.append(meas['key'])
    return keys


def connect_mqtt(client_id=None):
    """
    Creates and returns a connected MQTT client using MQTT v5 over WebSockets.
    """
    if client_id is None:
        client_id = f'publish-{random.randint(0, 1000)}'

    def on_connect(client, userdata, flags, rc, properties=None):
        if rc == 0:
            print("Connected to MQTT Broker!")
        else:
            print(f"Failed to connect, return code {rc}")

    client = mqtt_client.Client(
        client_id=client_id,
        transport='websockets',
        callback_api_version=CallbackAPIVersion.VERSION2
    )
    client.username_pw_set(USERNAME, PASSWORD)
    client.on_connect = on_connect
    client.connect(BROKER, PORT)
    return client


def noisy_sin(x):
    """Generate a noisy sine wave value."""
    return 20 * math.sin(2 * math.pi / 30 * x) + 5 * random.random()


def publish_loop(client, topics):
    """
    Publishes noisy sine wave data to each topic at the configured interval.
    Each payload is a JSON object: {"timestamp": <utc_ms>, "value": <val>}.
    """
    msg_count = 0
    while True:
        utc_ms = time.time() * 1000  # UTC timestamp in milliseconds
        print("-----------------PUBLISHING-----------------")
        for topic in topics:
            value = noisy_sin(msg_count)
            payload = json.dumps({"timestamp": utc_ms, "value": value})
            rc, _ = client.publish(topic, payload)
            if rc == MQTTErrorCode.MQTT_ERR_SUCCESS:
                print(f"Published {payload} to {topic}")
            else:
                print(f"Publish failed for {topic}: {rc}")
        msg_count += 1
        time.sleep(PUBLISH_INTERVAL)


def main():
    # Load all measurement topic keys from the script's directory
    topics = load_measurement_keys(ROVER_JSON_PATH)
    if not topics:
        print(f"No measurement topics found. Check your JSON structure at {ROVER_JSON_PATH}.")
        return

    # Connect and start publishing
    client = connect_mqtt()
    client.loop_start()
    try:
        publish_loop(client, topics)
    except KeyboardInterrupt:
        print("Stopping publisher.")
    finally:
        client.loop_stop()


if __name__ == '__main__':
    main()
