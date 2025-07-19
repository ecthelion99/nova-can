import yaml
import json
import os
import glob


def read_yaml_to_dict(yaml_file_path):
    with open(yaml_file_path, 'r') as file:
        return yaml.safe_load(file)


def build_rover_structure(folder_path):
    """
    Reads all .yaml/.yml files in `folder_path`, and builds a nested JSON structure:

    {
      "name": "Rover",
      "key": "rover",
      "folders": [
        {
          "name": <system name>,
          "key": "rover.<system>",
          "folders": [
            {
              "name": <device_type>,
              "key": "rover.<system>.<device_type>",
              "folders": [
                {
                  "name": <device name>,
                  "key": "rover.<system>.<device_type>.<device_name>",
                  "folders": [],
                  "measurements": []
                },
                ...
              ],
              "measurements": []
            },
            ...
          ],
          "measurements": []
        },
        ...
      ],
      "measurements": []
    }
    """
    systems_list = []
    yaml_files = sorted(
        glob.glob(os.path.join(folder_path, "*.yaml")) +
        glob.glob(os.path.join(folder_path, "*.yml"))
    )

    for yaml_path in yaml_files:
        config = read_yaml_to_dict(yaml_path)
        system_name = config.get("name")
        if not system_name:
            raise KeyError(f"Top-level 'name' key missing in {yaml_path}")

        base_key = f"rover.{system_name.lower()}"
        # collect devices by clean type across all CAN buses
        devices_by_type = {}
        for bus in config.get("can_buses", []):
            for dev in bus.get("devices", []):
                raw_dtype = dev.get("device_type")
                if not raw_dtype:
                    raise KeyError(f"Device missing 'device_type' in {yaml_path}")
                # strip leading folder prefix (e.g., "nova_interfaces/")
                clean_dtype = raw_dtype.split('/', 1)[-1]
                devices_by_type.setdefault(clean_dtype.lower(), []).append(dev)

        # build per-type entries
        type_folders = []
        for clean_dtype, devices in devices_by_type.items():
            type_key = f"{base_key}.{clean_dtype}"
            # build device entries under folders
            device_entries = []
            for dev in devices:
                dev_name = dev.get("name")
                if not dev_name:
                    raise KeyError(f"Device in {yaml_path} missing 'name'")
                dev_key = f"{type_key}.{dev_name.lower()}"
                device_entries.append({
                    "name": dev_name,
                    "key": dev_key,
                    "folders": [],
                    "measurements": []
                })

            type_folders.append({
                "name": clean_dtype,
                "key": type_key,
                "folders": device_entries,
                "measurements": []
            })

        systems_list.append({
            "name": system_name,
            "key": base_key,
            "folders": type_folders,
            "measurements": []
        })

    # top-level Rover
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


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    systems_dir = os.path.join(script_dir, 'systems')
    output_file = os.path.join(script_dir, 'systems_grouped.json')

    rover_structure = build_rover_structure(systems_dir)
    write_json(rover_structure, output_file)
