#!/usr/bin/env python3
from pathlib import Path
import sys
import pydsdl

dsdl_file = Path("/home/pih/FYP/nova-can/examples/dsdl/nova_dsdl/motor_driver/srv/SetPIDConstant.1.0.dsdl").resolve()
root_namespace = Path("/home/pih/FYP/nova-can/examples/dsdl/nova_dsdl").resolve()

# sanity checks before calling pydsdl
if not dsdl_file.exists():
    print(f"DSDL file not found: {dsdl_file}", file=sys.stderr)
    sys.exit(1)
if not root_namespace.exists():
    print(f"Root namespace dir not found: {root_namespace}", file=sys.stderr)
    sys.exit(1)


parsed, dependent = pydsdl.read_files(
    dsdl_files=[dsdl_file],
    root_namespace_directories_or_names=[root_namespace],
    lookup_directories=None,
    print_output_handler=None,
    allow_unregulated_fixed_port_id=False,
)
print(f"Type of parsed: {type(parsed)}")
# Output: Type of parsed: <class 'list'>
print("AAAAAAAAAA")
print(parsed)
print("AAAAAAAAAA")
print(dependent)
print("AAAAAAAAAA")

service_type = parsed[0]  # First (and only) parsed type
request_type = service_type.fields[0].data_type  # Request structure
response_type = service_type.fields[1].data_type  # Response structure

# Get constants from request
constants = request_type.constants
for const in constants:
    print(f"{const.name} = {const.value}")  # P=0, I=1, D=2



    
