import argparse
import os
from typing import List, TypedDict, Union

import pydsdl
from jinja2 import Environment, FileSystemLoader

class Define(TypedDict):
    name: str
    value: Union[str, int, float]

class Field(TypedDict):
    name: str
    type: str

DEFAULT_TEMPLATES_LOCATION = os.path.join(os.path.dirname(__file__), "jinja_templates")
env = Environment(loader=FileSystemLoader(DEFAULT_TEMPLATES_LOCATION))
template = env.get_template("c_dsdl.h.j2")

def process_dsdl_constant(constant: pydsdl.Constant) -> Define:
    return {'name': constant.name, 'value': constant.value}

def process_dsdl_field(field: pydsdl.Field) -> Field:
    return {'name': field.name, 'type': field.data_type}

def generate_type_code(t: pydsdl.CompositeType) -> str:
    defines = map(process_dsdl_constant, t.constants)
    fields = map(process_dsdl_field, t.fields)
    name = t.full_name.replace(t.NAME_COMPONENT_SEPARATOR, '_')
    return template.render(struct_name = name,
                           struct_fields = fields,
                           defines = defines
                           )

def generate_namespace_code(input_folder: str, output_folder: str):
    types = pydsdl.read_namespace(root_namespace_directory=input_folder)
    for t in types:
        rendered_type = generate_type_code(t)
        full_output_dir = os.path.join(output_folder, *t.namespace_components)
        file_name = t.short_name + ".h"
        os.makedirs(full_output_dir, exist_ok=True)
        with open(os.path.join(full_output_dir, file_name), "w") as f:
            f.write(rendered_type)


def main():
    parser = argparse.ArgumentParser(description="CLI transpiler for DSDL to C")
    
    parser.add_argument("input_folder", type=str, help="The input folder of the top level namespace")
    parser.add_argument("output_folder", type=str, help="The output folder of the compiled code")

    args = parser.parse_args()

    generate_namespace_code(args.input_folder, args.output_folder)
  

if __name__ == "__main__":
    main()