#!/usr/bin/python3

import pydsdl
import argparse
import os
from jinja2 import Environment, FileSystemLoader


DEFAULT_TEMPLATES_LOCATION = os.path.join(os.path.dirname(__file__), "jinja_templates")
env = Environment(loader=FileSystemLoader(DEFAULT_TEMPLATES_LOCATION))
template = env.get_template("d_dsdl.h.j2")

def dsdl_contant_processor(constant: pydsdl.Constant):
    pass

def generate_type_code(t: pydsdl.CompositeType) -> str:
    pass

def generate_namespace_code(input_folder: str, output_folder: str):
    types = pydsdl.read_namespace(root_namespace_directory=input_folder)
    for t in types:
        rendered_type = generate_type_code(t, output_folder)
        write_to_file(rendered_type)

def main():
    parser = argparse.ArgumentParser(description="CLI transpiler for DSDL to C")
    
    parser.add_argument("input_folder", type=str, help="The input folder of the top level namespace")
    parser.add_argument("output_folder", type=str, help="The output folder of the compiled code")

    args = parser.parse_args()

    generate_namespace_code(args.input_folder, args.output_folder)

    

if __name__ == "__main__":
    main()