import yaml
import json
import os
import glob
import warnings
import argparse

# Get root dir from environment; do NOT set it in code unless for temporary testing.
root_dir = os.environ.get("NOVA_SYS_ROOT_DIR", "/home/pih/FYP/nova-can/examples")


def read_yaml_to_dict(yaml_file_path):
    """Reads a YAML file and returns a dict (empty dict if file empty)."""
    with open(yaml_file_path, 'r') as f:
        return yaml.safe_load(f) or {}


def build_rover_structure(systems_dir, interfaces_dir):
    """
    Constructs the Rover JSON structure by reading system YAMLs and corresponding interface YAMLs.

    Args:
        systems_dir (str): Directory containing system YAML files.
        interfaces_dir (str): Directory containing interface YAML files.

    Returns:
        dict: Nested JSON-ready Python dict.
    """
    systems_list = []

    yaml_files = sorted(
        glob.glob(os.path.join(systems_dir, "*.yaml")) +
        glob.glob(os.path.join(systems_dir, "*.yml"))
    )

    for yaml_path in yaml_files:
        config = read_yaml_to_dict(yaml_path)
        system_name = config.get("name")
        if not system_name:
            raise KeyError(f"Top-level 'name' key missing in {yaml_path}")

        base_key = f"rover.{system_name}"
        devices_by_type = {}

        for bus in config.get("can_buses", []):
            for dev in bus.get("devices", []):
                raw_dtype = dev.get("device_type")
                if not raw_dtype:
                    raise KeyError(f"Device missing 'device_type' in {yaml_path}")
                clean_dtype = raw_dtype.split('/', 1)[-1]
                devices_by_type.setdefault(clean_dtype, []).append((dev, raw_dtype))

        type_folders = []
        for clean_dtype, dev_list in devices_by_type.items():
            type_key = f"{base_key}.{clean_dtype}"
            device_entries = []

            interface_file = os.path.join(interfaces_dir, f"{clean_dtype}.yaml")
            interface_config = read_yaml_to_dict(interface_file) if os.path.isfile(interface_file) else {}

            messages = interface_config.get('messages', {})
            receive_msgs = messages.get('transmit', []) or [] 
            receive_entries = []
            for msg in receive_msgs:
                msg_name = msg.get('name')
                if not msg_name:
                    continue
                receive_entries.append({'name': msg_name, 'key_suffix': msg_name})

            services_section = interface_config.get('services', {})
            server_list = services_section.get('server', [])  # may be None or list
            if server_list is None:
                warnings.warn(f"Interface {clean_dtype} in {interface_file} missing 'server' section")
                server_list = []
            server_list = server_list or []

            servers = []
            for srv in server_list:
                server_name = srv.get('name')
                if not server_name:
                    continue
                servers.append({'name': server_name, 'key_suffix': server_name})

            for dev, raw_dtype in dev_list:
                dev_name = dev.get("name")
                if not dev_name:
                    raise KeyError(f"Device in {yaml_path} missing 'name'")
                dev_key = f"{type_key}.{dev_name}"

                telemetry_stream = []
                for rec in receive_entries:
                    telemetry_stream_key = f"{dev_key}.{rec['key_suffix']}"
                    telemetry_stream.append({
                        'name': rec['name'].replace('_', ' ').title(),
                        'key': telemetry_stream_key.replace(' ', '_').lower(),
                        'values': [
                            {
                                'key': 'value',
                                'name': 'Value',
                                'units': 'TEST',
                                'format': 'float',
                                'hints': {'range': 1}
                            },
                            {
                                'key': 'utc',
                                'source': 'timestamp',
                                'name': 'Timestamp',
                                'units': 'utc',
                                'format': 'integer',
                                'hints': {'domain': 1}
                            }
                        ]
                    })

                telemetry_request = []
                for server in servers:
                    telemetry_request_key = f"{dev_key}.{server['key_suffix']}"
                    telemetry_request.append({
                        'name': server['name'].replace('_', ' ').title(),
                        'key': telemetry_request_key.replace(' ', '_').lower(),
                        "write": "float",
                        "read": "float",
                        'values': [
                            {
                                'key': 'value',
                                'name': 'Value',
                                'units': 'TEST',
                                'format': 'float',
                                'hints': {'range': 1}
                            },
                            {
                                'key': 'utc',
                                'source': 'timestamp',
                                'name': 'Timestamp',
                                'units': 'utc',
                                'format': 'integer',
                                'hints': {'domain': 1}
                            }
                        ]
                    })

                device_entries.append({
                    "name": dev_name.replace('_', ' ').title(),
                    "key": dev_key.replace(' ', '_').lower(),
                    "folders": [],
                    "telemetry_stream": telemetry_stream,
                    "telemetry_request": telemetry_request
                })

            type_folders.append({
                "name": clean_dtype.replace('_', ' ').title(),
                "key": type_key.replace(' ', '_').lower(),
                "folders": device_entries,
                "measurements": []
            })

        systems_list.append({
            "name": system_name.replace('_', ' ').title(),
            "key": base_key.replace(' ', '_').lower(),
            "folders": type_folders,
            "measurements": []
        })

    return {
        "name": "Rover",
        "key": "rover",
        "folders": systems_list,
        "measurements": []
    }


def write_json(data, output_path):
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=4)
    print(f"Wrote grouped JSON to '{output_path}'")

def compile_system():
    systems_dir = os.path.join(root_dir, "systems")
    interfaces_dir = os.path.join(root_dir, "interfaces")
    

    if not os.path.isdir(systems_dir):
        raise FileNotFoundError(f"Systems directory not found: {systems_dir}")
    if not os.path.isdir(interfaces_dir):
        warnings.warn(f"Interfaces directory not found: {interfaces_dir} (interface files will be skipped)")

    rover_structure = build_rover_structure(systems_dir, interfaces_dir)

    output_file = os.path.join(root_dir, 'system_composition.json')
    write_json(rover_structure, output_file)

if __name__ == "__main__":
    compile_system()

def compile_system_JSON_cli():
    parser = argparse.ArgumentParser(
        description="Compiles system YAML files into a single JSON file for openMCT.\n "
                    "The root directory containing 'systems' and 'interfaces' subdirectories needs to be provided via the environment variable NOVA_SYS_ROOT_DIR."

    )
    # parser.add_argument("-v", "--verbose", action="store_true",
    #                     help="Print DB inserts to console, True or False, default False")
    # parser.add_argument("-p", "--port", type=int, default=9000,
    #                     help="Port to run HTTP server on, default 9000")

    args = parser.parse_args()
    compile_system()
