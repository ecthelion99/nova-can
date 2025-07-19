import yaml
import json
import os
import glob

def read_yaml_to_dict(yaml_file_path):
    with open(yaml_file_path, 'r') as file:
        return yaml.safe_load(file)


def group_config_dict(config_dict):
    """
    Transforms a dict of the form:
      {
        "name": "Chassis",
        "can_buses": [ ... ]
      }
    into a grouped dict:
      { "Chassis": { "can_buses": { ... } } }
    """
    system_name = config_dict.get("name")
    if not system_name:
        raise KeyError("Top-level 'name' key is required in each config dict")

    grouped = {system_name: {"can_buses": {}}}
    for bus in config_dict.get("can_buses", []):
        bus_name = bus.get("name")
        if not bus_name:
            raise KeyError("Each CAN bus must have a 'name' field")
        devices_by_type = {}
        for dev in bus.get("devices", []):
            dtype = dev.get("device_type")
            if not dtype:
                raise KeyError(f"Device {dev} missing 'device_type'")
            entry = {k: v for k, v in dev.items() if k != "device_type"}
            devices_by_type.setdefault(dtype, []).append(entry)
        grouped[system_name]["can_buses"][bus_name] = devices_by_type
    return grouped


def read_and_group_all_yaml(folder_path):
    """
    Reads all .yaml/.yml files in `folder_path`, groups each,
    and merges into one dict.
    """
    all_grouped = {}
    yaml_files = glob.glob(os.path.join(folder_path, "*.yaml")) + \
                 glob.glob(os.path.join(folder_path, "*.yml"))
    for yaml_path in sorted(yaml_files):
        config = read_yaml_to_dict(yaml_path)
        grouped = group_config_dict(config)
        # Merge into master dict
        for key, val in grouped.items():
            if key in all_grouped:
                raise KeyError(f"Duplicate system name '{key}' found in {yaml_path}")
            all_grouped[key] = val
    return all_grouped


def write_json(data, output_path):
    """
    Writes `data` dict to `output_path` (overwrites if exists).
    """
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=4)
    print(f"Wrote grouped JSON to '{output_path}'")


if __name__ == "__main__":
    # Determine script directory and systems folder
    script_dir = os.path.dirname(os.path.abspath(__file__))
    systems_dir = os.path.join(script_dir, 'systems')
    output_file = os.path.join(script_dir, 'systems_grouped.json')

    # Read, group, and merge all YAML configs
    all_systems = read_and_group_all_yaml(systems_dir)

    # Write combined JSON
    write_json(all_systems, output_file)
