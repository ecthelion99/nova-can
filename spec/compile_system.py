import yaml  # PyYAML parser
import json  # JSON serialization
import os    # File path utilities
import glob  # File pattern matching


def read_yaml_to_dict(yaml_file_path):
    """
    Reads a YAML file from the given path and returns as a Python dict.
    """
    with open(yaml_file_path, 'r') as file:
        return yaml.safe_load(file)  # Use safe_load to avoid execution of arbitrary tags


def build_rover_structure(folder_path):
    """
    Constructs the Rover JSON structure by reading system YAMLs and corresponding interface YAMLs.

    Args:
        folder_path (str): Directory containing system YAML files.

    Returns:
        dict: Nested JSON-ready Python dict.
    """
    # Determine script and interfaces directory paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    interfaces_dir = os.path.join(script_dir, 'interfaces')

    systems_list = []  # Container for each system's JSON representation
    # Gather all .yaml and .yml files in the systems folder
    yaml_files = sorted(
        glob.glob(os.path.join(folder_path, "*.yaml")) +
        glob.glob(os.path.join(folder_path, "*.yml"))
    )

    # Process each system config file
    for yaml_path in yaml_files:
        config = read_yaml_to_dict(yaml_path)
        system_name = config.get("name")
        if not system_name:
            raise KeyError(f"Top-level 'name' key missing in {yaml_path}")

        # Base key for this system (lowercased)
        base_key = f"rover.{(system_name)}"
        devices_by_type = {}  # Group devices by their type

        # Iterate all CAN bus entries and their devices
        # Once this loop has run, devices_by_type will be a dictionary containing all device types.
        # Each device type will then having an array containing each device of that type.
        for bus in config.get("can_buses", []):
            for dev in bus.get("devices", []):
                # gets the value of the device type for each device
                raw_dtype = dev.get("device_type") 
                if not raw_dtype:
                    raise KeyError(f"Device missing 'device_type' in {yaml_path}")
                # Strip leading folder prefix (e.g., "nova_interfaces/")
                clean_dtype = (raw_dtype.split('/', 1)[-1])
                devices_by_type.setdefault(clean_dtype, []).append((dev, raw_dtype))

        type_folders = []  # JSON entries for each device type
        for clean_dtype, dev_list in devices_by_type.items():
            type_key = f"{base_key}.{clean_dtype}"  # Unique key per type
            device_entries = []  # JSON entries for each device

            # Load the corresponding interface YAML (contains message definitions)
            interface_file = os.path.join(interfaces_dir, f"{clean_dtype}.yaml")
            interface_config = {}
            if os.path.isfile(interface_file):
                interface_config = read_yaml_to_dict(interface_file)

            # Extract receive message definitions
            messages = interface_config.get('messages', {})
            receive_msgs = messages.get('receive', [])
            receive_entries = []  # Temporary store for message prototypes
            for msg in receive_msgs:
                msg_name = msg.get('name')
                if not msg_name:
                    continue
                # Store name and lowercase suffix for key construction
                receive_entries.append({
                    'name': msg_name,
                    'key_suffix': msg_name
                })

            # Build JSON for each device under this type
            for dev, raw_dtype in dev_list:
                dev_name = dev.get("name")
                if not dev_name:
                    raise KeyError(f"Device in {yaml_path} missing 'name'")
                dev_key = f"{type_key}.{dev_name}"

                # Construct measurements for each receive message
                measurements = []
                for rec in receive_entries:
                    measurement_key = f"{dev_key}.{rec['key_suffix']}"
                    # Each measurement gets a 'values' array with placeholders
                    measurements.append({
                        'name': rec['name'].replace('_',' ').title(),
                        'key': measurement_key.replace(' ','_').lower(),
                        'values': [
                            {
                                'key': 'value',
                                'name': 'Value',
                                'units': 'TEST',  # Placeholder units
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

                # Final device entry
                device_entries.append({
                    "name": dev_name.replace('_',' ').title(),
                    "key": dev_key.replace(' ','_').lower(),
                    "folders": [],
                    "measurements": measurements
                })

            # Append the device type entry
            type_folders.append({
                "name": clean_dtype.replace('_',' ').title(),
                "key": type_key.replace(' ','_').lower(),
                "folders": device_entries,
                "measurements": []  # Empty placeholder
            })

        # Append the system entry
        systems_list.append({
            "name": system_name.replace('_',' ').title(),
            "key": base_key.replace(' ','_').lower(),
            "folders": type_folders,
            "measurements": []  # Empty placeholder
        })

    # Top-level Rover object
    return {
        "name": "Rover",
        "key": "rover",
        "folders": systems_list,
        "measurements": []  # Empty placeholder
    }


def write_json(data, output_path):
    """
    Writes the given data dict to a JSON file with indentation.
    """
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=4)
    print(f"Wrote grouped JSON to '{output_path}'")


if __name__ == "__main__":
    # Determine directories relative to script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    systems_dir = os.path.join(script_dir, 'systems')
    output_file = os.path.join(script_dir, 'systems_grouped.json')

    # Build and write the structure
    rover_structure = build_rover_structure(systems_dir)
    write_json(rover_structure, output_file)
