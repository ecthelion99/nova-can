import os
import shutil
from typing import Dict, List

import yaml
from jinja2 import Environment, FileSystemLoader
from rich import print
from caseconverter import snakecase

from nova_can.models.device_models import DeviceInterface

from pathlib import Path
import typer

from pydsdl import (
    read_namespace,
    FloatType,
    CompositeType,
    ServiceType,
)
from nunavut import (
    LanguageContextBuilder,
    DSDLCodeGenerator,
    SupportGenerator,
    Language,
    build_namespace_tree,
)

app = typer.Typer(no_args_is_help=True, add_completion=True)


def copy_nova_can_header(output_folder: str):
    """Copy nova_can.h from src/c to the output folder."""
    # Get the path to nova_can.h relative to the ncc.py script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.abspath(os.path.join(script_dir, '..', '..', '..', 'c'))
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


# --- pyDSDL float detection helpers ---

def _iter_field_types(dtype):
    """Yield the given type and recursively any element/nested field types."""
    yield dtype
    element_type = getattr(dtype, 'element_type', None)
    if element_type is not None:
        yield from _iter_field_types(element_type)
    fields = getattr(dtype, 'fields', None)
    if fields is not None:
        for field in fields:
            yield from _iter_field_types(field.data_type)

def _scan_for_floats(dsdl_directory: Path, include_paths: List[str]) -> List[tuple]:
    """Return list of (qualified_field_name, dtype_str) for any float fields found."""
    types = list(read_namespace(str(dsdl_directory), include_paths))
    offenders: List[tuple] = []

    def scan_composite(comp: CompositeType, prefix: str):
        for field in comp.fields:
            for dt in _iter_field_types(field.data_type):
                if isinstance(dt, FloatType):
                    offenders.append((prefix + field.name, str(dt)))
            if isinstance(field.data_type, CompositeType):
                scan_composite(field.data_type, prefix + field.name + '.')

    for t in types:
        if isinstance(t, ServiceType):
            scan_composite(t.request_type, t.full_name + '.request.')
            scan_composite(t.response_type, t.full_name + '.response.')
        elif isinstance(t, CompositeType):
            scan_composite(t, t.full_name + '.')

    return offenders


def _generate_dsdl_headers(
    dsdl_directory: Path,
    dsdl_out_directory: Path,
) -> None:
    """Generate C headers from DSDL using Nunavut Python API."""
    # Ensure output directory exists
    dsdl_out_directory.mkdir(parents=True, exist_ok=True)

    # Resolve template paths relative to this script directory
    script_dir = Path(__file__).resolve().parent
    templates_root = (script_dir / 'templates' / 'nunavut' / 'c')
    code_templates_dir = templates_root / 'templates'
    support_templates_dir = templates_root / 'support'

    # Build the C language context first (required by build_namespace_tree)
    language_context = (
        LanguageContextBuilder()
        .set_target_language('c')
        .set_target_language_configuration_override(Language.WKCV_LANGUAGE_OPTIONS, {"omit_float_serialization_support": True})
        .create()
    )


    # Read pydsdl types from the root namespace
    types = list(read_namespace(str(dsdl_directory), [str(dsdl_directory)]))

    # Build the Nunavut namespace tree from pydsdl types
    root_namespace = build_namespace_tree(
        types=types,
        root_namespace_dir=str(dsdl_directory),
        output_dir=str(dsdl_out_directory),
        language_context=language_context,
    )

    print(f"[cyan]Generating DSDL headers...[/cyan]")

    # Run explicit generators with our custom templates
    code_gen = DSDLCodeGenerator(
        root_namespace,
        templates_dir=[code_templates_dir],
    )
    support_gen = SupportGenerator(
        root_namespace,
        support_templates_dir=[support_templates_dir],
    )

    # Generate code and support files
    list(code_gen.generate_all(allow_overwrite=True))
    list(support_gen.generate_all(allow_overwrite=True))

    print(f"[green]DSDL headers generated at {dsdl_out_directory}[/green]")


@app.callback(invoke_without_command=True)
def main(
    device_interface: Path = typer.Option(
        ..., '--device-interface', '-d', exists=True, file_okay=True, dir_okay=False, readable=True,
        help='Path to the device interface YAML file',
    ),
    output_folder: Path = typer.Option(
        ..., '--output-folder', '-o', exists=False, file_okay=False, dir_okay=True,
        help='Path to the output folder',
    ),
    generate_dsdl_headers: bool = typer.Option(
        False, '--generate-dsdl-headers', help='Generate DSDL C headers using Nunavut before rendering.',
    ),
    header_only: bool = typer.Option(
        False, '--header-only', help='Generate a header-only device file.',
    ),
    dsdl_directory: Path = typer.Option(
        Path('dsdl/nova_dsdl'), '--dsdl-directory', exists=False, file_okay=False, dir_okay=True,
        help='Path to the DSDL root directory (default: ./dsdl/nova_dsdl).',
    ),
    dsdl_out_directory: Path = typer.Option(
        Path('dsdl_headers'), '--dsdl-out-directory', exists=False, file_okay=False, dir_okay=True,
        help='Output directory for generated DSDL headers (default: ./dsdl_headers).',
    ),
):
    """Nova CAN Compiler (ncc)"""

    # Optionally generate DSDL headers via Nunavut
    if generate_dsdl_headers:
        if not dsdl_directory.exists():
            print(f"[red]DSDL directory not found: {dsdl_directory}[/red]")
            raise typer.Exit(code=2)
        _generate_dsdl_headers(dsdl_directory.resolve(), dsdl_out_directory.resolve())

    # Enforce no floating-point usage in DSDL types (suggest fixed-point instead)
    if dsdl_directory.exists():
        offenders = _scan_for_floats(dsdl_directory.resolve(), [str(dsdl_directory.resolve())])
        if offenders:
            print("[red]Floating-point fields detected in DSDL (use fixed-point scaled integers instead):[/red]")
            for name, dtype in offenders:
                print(f" - {name}: {dtype}")
            raise typer.Exit(code=3)
    else:
        print(f"[yellow]Warning: DSDL directory not found ({dsdl_directory}). Float-type check skipped.[/yellow]")

    # Load device interface YAML
    with open(device_interface, 'r') as f:
        raw_device_interface = yaml.safe_load(f)

    device_interface_model = DeviceInterface(**raw_device_interface)

    # Ensure output directory exists
    os.makedirs(output_folder, exist_ok=True)

    # Copy nova_can.h to output directory
    copy_nova_can_header(str(output_folder))

    # Set up Jinja2 environment
    template_dir = os.path.join(os.path.dirname(__file__), 'templates')
    env = Environment(loader=FileSystemLoader(template_dir))

    # Load templates
    header_template = env.get_template('nova_can_device.h.j2')
    c_template = env.get_template('nova_can_device.c.j2')

    # Render header
    header_output = header_template.render(
        device=device_interface_model,
        snakecase=snakecase,
        dsdl_header_path=dsdl_header_path,
        header_only=header_only,
    )
    header_path = Path(output_folder) / f"{snakecase(device_interface_model.name)}.h"
    with open(header_path, 'w') as f:
        f.write(header_output)
    print(f"[green]Generated device header at {header_path}[/green]")

    # Render .c only if not header-only
    if not header_only:
        c_output = c_template.render(
            device=device_interface_model,
            snakecase=snakecase,
            dsdl_header_path=dsdl_header_path,
        )
        c_path = Path(output_folder) / f"{snakecase(device_interface_model.name)}.c"
        with open(c_path, 'w') as f:
            f.write(c_output)
        print(f"[green]Generated device source at {c_path}[/green]")


if __name__ == "__main__":
    app()