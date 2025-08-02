import pydsdl
from pathlib import Path

# Point this at the directory that contains your 'nova' folder:
dsdl_root_dir = Path("dsdl/motor_driver")

# Correct call: singular root_namespace_directory
# If you need to resolve standard UAVCAN types, you could add them to lookup_directories:
namespaces = pydsdl.read_namespace(
    root_namespace_directory=dsdl_root_dir,
    # lookup_directories=[Path("dsdl/uavcan")]  # uncomment if you reference standard types
)

# Print out everything found
for t in namespaces:
    print(t)
