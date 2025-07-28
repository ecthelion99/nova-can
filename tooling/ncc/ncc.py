import argparse
import os
import shutil
from typing import Dict, List

import yaml
from jinja2 import Environment, FileSystemLoader
from rich import print
from caseconverter import snakecase

from nova_can.models.device_models import DeviceInterface

def copy_nova_can_header(output_folder: str):
    """Copy nova_can.h from src/c to the output folder."""
    # Get the path to nova_can.h relative to the ncc.py script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.abspath(os.path.join(script_dir, '..', '..', 'src', 'c'))
    nova_can_h = os.path.join(src_dir, 'nova_can.h')
    
    # Copy the file
    if os.path.exists(nova_can_h):
        shutil.copy2(nova_can_h, output_folder)
    else:
        print(f"[yellow]Warning: nova_can.h not found at {nova_can_h}[/yellow]")

def dsdl_header_path(port_type: str) -> str:
    """Return the path to the DSDL header for a given port type."""
    full_type_components = port_type.split('.')
    full_type_components[-3] = '_'.join(full_type_components[-3:])
    header_path = os.path.join(*full_type_components[:-2])
    return header_path + '.h'

def main():
    parser = argparse.ArgumentParser(description='Nova CAN Compiler (ncc)')
    parser.add_argument('-d', '--device-interface',
                       dest='device_interface',
                       required=True,
                       type=str,
                       help='Path to the device interface YAML file')
    parser.add_argument('-o', '--output-folder',
                       dest='output_folder',
                       required=True,
                       type=str,
                       help='Path to the output folder')

    # Parse arguments
    args = parser.parse_args()

    device_interface_path = args.device_interface
    output_folder = args.output_folder

    with open(device_interface_path, 'r') as f:
        raw_device_interface = yaml.safe_load(f)
    
    device_interface = DeviceInterface(**raw_device_interface)

    # Ensure output directory exists
    os.makedirs(output_folder, exist_ok=True)
    
    # Copy nova_can.h to output directory
    copy_nova_can_header(output_folder)
    
    # Set up Jinja2 environment
    template_dir = os.path.join(os.path.dirname(__file__), 'templates')
    env = Environment(loader=FileSystemLoader(template_dir))

    # Load a template (example)
    template = env.get_template('nova_can_device.h.j2')

    # Render the template with some context (example)
    output = template.render(device=device_interface,
                             snakecase=snakecase,
                             dsdl_header_path=dsdl_header_path)

    # Save the rendered output to a file (example)
    with open(os.path.join(output_folder, f'{snakecase(device_interface.name)}.h'), 'w') as f:
        f.write(output)

if __name__ == "__main__":
    main()