"""
System composition utilities for Nova-CAN.

This module provides functions to verify and compose Nova-CAN systems from
YAML configuration files and DSDL Python bindings.
"""

import os
import glob
import yaml
from typing import List, Dict, Set, Optional, Tuple, Any
from types import ModuleType
from dataclasses import dataclass, field
from pathlib import Path
import importlib
import importlib.util

from nova_can.models.system_models import SystemDefinition
from nova_can.models.device_models import DeviceInterface, Port


@dataclass
class ComposeError:
    """Represents a composition error with details."""
    error_type: str
    message: str
    file_path: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


@dataclass
class MessagesInfo:
    """Information about a message in a device interface."""
    #TODO: Use a multi-index lookup for ports
    receive: Dict[str, Port] = field(default_factory=dict)
    transmit: Dict[str, Port] = field(default_factory=dict)

@dataclass
class ServicesInfo:
    """Information about a service in a device interface."""
    #TODO: Use a multi-index lookup for the ports
    server: Dict[str, Port] = field(default_factory=dict)
    client: Dict[str, Port] = field(default_factory=dict)

@dataclass
class InterfaceInfo:
    """Information about a device interface."""
    name: str
    version: str
    file_path: str
    interface_name: str = ""  # The filename without extension
    messages: MessagesInfo = field(default_factory=MessagesInfo)
    services: ServicesInfo = field(default_factory=ServicesInfo)
    dsdl_modules: Set[str] = field(default_factory=set)
    
    #TODO: Move this into the messages and services and implement a multi-index lookup
    def get_port_by_id(self, port_id: int) -> Optional[Dict[str, Port]]:
        """Get a port by its id."""
        ports = {}
        for port in self.messages.receive.values():
            if port.port_id == port_id:
                ports['receive'] = port
        for port in self.messages.transmit.values():
            if port.port_id == port_id:
                ports['transmit'] = port
        for port in self.services.server.values():
            if port.port_id == port_id:
                ports['server'] = port
        for port in self.services.client.values():
            if port.port_id == port_id:
                ports['client'] = port
        return ports


@dataclass
class DeviceInfo:
    """Information about a device in a system."""
    name: str
    node_id: int
    source_system: str
    device_type: str
    can_bus: str
    interface: Optional[InterfaceInfo] = None


@dataclass
class CanBusInfo:
    """Information about a CAN bus in a system."""
    name: str
    rate: int
    devices: List[DeviceInfo] = field(default_factory=list)


@dataclass
class SystemInfo:
    """Information about a complete system."""
    name: str
    file_path: str
    can_buses: List[CanBusInfo] = field(default_factory=list)
    # Fast lookup dictionaries
    devices: Dict[str, DeviceInfo] = field(default_factory=dict)
    interfaces: Dict[str, InterfaceInfo] = field(default_factory=dict)

    def get_dsdl_modules(self) -> Set[str]:
        """Get all DSDL modules used in the system."""
        dsdl_modules = set()
        for interface in self.interfaces.values():
            dsdl_modules.update(interface.dsdl_modules)
        return dsdl_modules
    
    #TODO: swtich this to a multi-index lookup
    def get_devices_by_id(self, device_id: int) -> Optional[DeviceInfo]:
        """Get a device by its node_id."""
        devices = []
        for device in self.devices.values():
            if device.node_id == device_id:
                devices.append(device)
        return devices

<<<<<<< HEAD
    all_dsdl_modules: Set[str] = field(default_factory=set)

=======
>>>>>>> 58447e4 (add initial communication module)

@dataclass
class ComposeResult:
    """Result of system composition."""
    system: Optional[SystemInfo] = None
    errors: List[ComposeError] = field(default_factory=list)
    all_dsdl_modules: Set[str] = field(default_factory=set)
    
    @property
    def success(self) -> bool:
        """Returns True if composition was successful (no errors)."""
        return len(self.errors) == 0
    
    def get_missing_dsdl_modules(self) -> Set[str]:
        """Returns set of DSDL modules that are missing."""
        return self.all_dsdl_modules


def _load_yaml_file(file_path: str) -> Tuple[Optional[Dict[str, Any]], Optional[ComposeError]]:
    """Load a YAML file and return the data or an error."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f), None
    except yaml.YAMLError as e:
        return None, ComposeError(
            error_type="YAML_PARSE_ERROR",
            message=f"Failed to parse YAML file: {str(e)}",
            file_path=file_path
        )
    except FileNotFoundError:
        return None, ComposeError(
            error_type="FILE_NOT_FOUND",
            message="File not found",
            file_path=file_path
        )
    except Exception as e:
        return None, ComposeError(
            error_type="FILE_READ_ERROR",
            message=f"Failed to read file: {str(e)}",
            file_path=file_path
        )


def _validate_system_yaml(data: Dict[str, Any], file_path: str) -> Tuple[Optional[SystemDefinition], Optional[ComposeError]]:
    """Validate system YAML data and return SystemDefinition or error."""
    try:
        system_def = SystemDefinition(**data)
        return system_def, None
    except Exception as e:
        return None, ComposeError(
            error_type="SYSTEM_VALIDATION_ERROR",
            message=f"System YAML validation failed: {str(e)}",
            file_path=file_path,
            details={"data": data}
        )


def _validate_interface_yaml(data: Dict[str, Any], file_path: str) -> Tuple[Optional[DeviceInterface], Optional[ComposeError]]:
    """Validate interface YAML data and return DeviceInterface or error."""
    try:
        interface_def = DeviceInterface(**data)
        return interface_def, None
    except Exception as e:
        return None, ComposeError(
            error_type="INTERFACE_VALIDATION_ERROR",
            message=f"Interface YAML validation failed: {str(e)}",
            file_path=file_path,
            details={"data": data}
        )


def _extract_dsdl_modules_from_interface(interface: DeviceInterface) -> Set[str]:
    """Extract all DSDL module names from an interface definition."""
    modules = set()
    
    # Extract from messages
    if interface.messages:
        if interface.messages.receive:
            for msg in interface.messages.receive:
                modules.add(msg.port_type)
        if interface.messages.transmit:
            for msg in interface.messages.transmit:
                modules.add(msg.port_type)
    
    # Extract from services
    if interface.services:
        if interface.services.server:
            for srv in interface.services.server:
                modules.add(srv.port_type)
        if interface.services.client:
            for srv in interface.services.client:
                modules.add(srv.port_type)
    
    return modules

<<<<<<< HEAD
=======

>>>>>>> 58447e4 (add initial communication module)
def dsdl_module_to_import_path(port_type: str) -> str:
    """Convert a DSDL port type to a Python import path."""
    parts = port_type.split('.')
    parts[-3] = '_'.join(parts[-3:])
    return '.'.join(parts[:-2])


def _check_dsdl_module_availability(module_path: str) -> Tuple[bool, Optional[ComposeError]]:
    """Check if a DSDL module exists without importing it."""
    try:
        # Check if the module can be found in the Python path
        spec = importlib.util.find_spec(module_path)
        if spec is not None:
            return True, None
        else:
            return False, ComposeError(
                error_type="DSDL_MODULE_NOT_FOUND",
                message=f"DSDL module not found in PYTHONPATH: {module_path}",
                details={"module_path": module_path}
            )
    except Exception as e:
        return False, ComposeError(
            error_type="DSDL_MODULE_CHECK_ERROR",
            message=f"Error checking DSDL module {module_path}: {str(e)}",
            details={"module_path": module_path, "error": str(e)}
        )


def compose_system(
    system_search_dirs: List[str],
    interface_search_dirs: List[str]
) -> ComposeResult:
    """
    Compose a complete Nova-CAN system by verifying all components.
    
    This function:
    1. Finds and validates all system YAML files in the search directories
    2. Finds and validates all device interface YAML files referenced by systems
    3. Verifies that all required DSDL Python bindings are available (assumes PYTHONPATH is set)
    4. Returns a comprehensive result with a unified system containing all devices, interfaces, and any errors
    
    Args:
        system_search_dirs: List of directories to search for system YAML files
        interface_search_dirs: List of directories to search for interface YAML files
        
    Returns:
        ComposeResult containing a unified system, interfaces, errors, and missing modules
    """
    result = ComposeResult()
    
    # Create a unified system to hold all devices
    unified_system = SystemInfo(
        name="Unified System",
        file_path="composed"
    )
    
    # Step 1: Find and validate all system YAML files
    system_files = []
    for search_dir in system_search_dirs:
        if os.path.exists(search_dir):
            yaml_patterns = [
                os.path.join(search_dir, "*.yaml"),
                os.path.join(search_dir, "*.yml")
            ]
            for pattern in yaml_patterns:
                system_files.extend(glob.glob(pattern))
        else:
            result.errors.append(ComposeError(
                error_type="SEARCH_DIR_NOT_FOUND",
                message=f"System search directory not found: {search_dir}",
                details={"search_dir": search_dir}
            ))
    
    # Step 2: Process each system file and merge into unified system
    for system_file in system_files:
        # Load and validate system YAML
        data, error = _load_yaml_file(system_file)
        if error:
            result.errors.append(error)
            continue
        
        system_def, error = _validate_system_yaml(data, system_file)
        if error:
            result.errors.append(error)
            continue
        
        # Process CAN buses and devices
        for bus_def in system_def.can_buses:
            # Check if this bus already exists in unified system
            existing_bus = None
            for bus in unified_system.can_buses:
                if bus.name == bus_def.name:
                    existing_bus = bus
                    break
            
            if existing_bus is None:
                # Create new bus
                bus_info = CanBusInfo(
                    name=bus_def.name,
                    rate=bus_def.rate
                )
                unified_system.can_buses.append(bus_info)
            else:
                bus_info = existing_bus
            
            for device_def in bus_def.devices:
                # Check for device name conflicts (for now, just warn and skip)
                if device_def.name in unified_system.devices:
                    result.errors.append(ComposeError(
                        error_type="DEVICE_NAME_CONFLICT",
                        message=f"Device name '{device_def.name}' already exists in unified system",
                        details={
                            "device_name": device_def.name,
                            "system": system_def.name,
                            "bus": bus_def.name
                        }
                    ))
                    continue
                
                device_info = DeviceInfo(
                    name=device_def.name,
                    node_id=device_def.node_id,
                    source_system=system_def.name,
                    device_type=device_def.device_type,
                    can_bus=bus_info.name
                )
                bus_info.devices.append(device_info)
                # Add to fast lookup dictionary
                unified_system.devices[device_info.name] = device_info
    
   
    # Step 3: Collect interface files (processing moved to Step 5)
    interface_files = []
    for search_dir in interface_search_dirs:
        if os.path.exists(search_dir):
            yaml_patterns = [
                os.path.join(search_dir, "*.yaml"),
                os.path.join(search_dir, "*.yml")
            ]
            for pattern in yaml_patterns:
                interface_files.extend(glob.glob(pattern))
        else:
            result.errors.append(ComposeError(
                error_type="SEARCH_DIR_NOT_FOUND",
                message=f"Interface search directory not found: {search_dir}",
                details={"search_dir": search_dir}
            ))
    
    # Step 4: Link interfaces to CAN buses and verify DSDL modules
    # First, collect all interfaces by their interface_name
    all_interfaces = {}
    for interface_file in interface_files:
        data, error = _load_yaml_file(interface_file)
        if error:
            continue
        
        interface_def, error = _validate_interface_yaml(data, interface_file)
        if error:
            continue
        
        interface_name = os.path.splitext(os.path.basename(interface_file))[0]
        interface_info = InterfaceInfo(
            name=interface_def.name,
            version=interface_def.version,
            file_path=interface_file,
            interface_name=interface_name
        )
        
        # Extract DSDL modules
        dsdl_modules = _extract_dsdl_modules_from_interface(interface_def)
        interface_info.dsdl_modules = dsdl_modules
        result.all_dsdl_modules.update(dsdl_modules)

        # Add messages and services to interface info
        if interface_def.messages:
            if interface_def.messages.receive:
                interface_info.messages.receive = {msg.name: msg for msg in interface_def.messages.receive}
            if interface_def.messages.transmit:
                interface_info.messages.transmit = {msg.name: msg for msg in interface_def.messages.transmit}
        if interface_def.services:
            if interface_def.services.server:
                interface_info.services.server = {srv.name: srv for srv in interface_def.services.server}
            if interface_def.services.client:
                interface_info.services.client = {srv.name: srv for srv in interface_def.services.client}
        
        all_interfaces[interface_name] = interface_info
    
    # Now attach interfaces to devices
    for bus_info in unified_system.can_buses:
        for device_info in bus_info.devices:
            # Find the interface for this device
            device_type = device_info.device_type
            if '/' in device_type:
                device_type = device_type.split('/')[-1]
            
            interface_info = all_interfaces.get(device_type)
            if interface_info:
                device_info.interface = interface_info
                
                # Add interface to fast lookup dictionary
                unified_system.interfaces[device_type] = interface_info
                
                # Check DSDL module availability
                for port_type in interface_info.dsdl_modules:
                    module_path = dsdl_module_to_import_path(port_type)
                    available, error = _check_dsdl_module_availability(module_path)
                    if not available:
                        result.errors.append(error)
            else:
                result.errors.append(ComposeError(
                    error_type="INTERFACE_NOT_FOUND",
                    message=f"Interface not found for device type: {device_type}",
                    details={
                        "device_name": device_info.name,
                        "device_type": device_info.device_type,
                        "bus": bus_info.name
                    }
                ))
    
    # Set the unified system as the result
    result.system = unified_system
    
    return result

def import_dsdl_modules(system_info: SystemInfo) -> Dict[str, ModuleType]:
    """
    Import all DSDL modules for the composed system.
    """
    modules = {}
    for module in system_info.get_dsdl_modules():
        modules[module] = importlib.import_module(dsdl_module_to_import_path(module))
    return modules


def get_device(system_info: SystemInfo, device_name: str) -> Optional[DeviceInfo]:
    """
    Get a device by name using fast lookup.
    
    Args:
        system_info: The system information
        device_name: Name of the device
        
    Returns:
        DeviceInfo if found, None otherwise
    """
    return system_info.devices.get(device_name)


def get_interface_for_device(system_info: SystemInfo, bus_name: str, device_name: str) -> Optional[InterfaceInfo]:
    """
    Get the interface for a specific device on a specific bus.
    
    Args:
        system_info: The system information
        bus_name: Name of the CAN bus
        device_name: Name of the device
        
    Returns:
        InterfaceInfo if found, None otherwise
    """
    for bus in system_info.can_buses:
        if bus.name == bus_name:
            for device in bus.devices:
                if device.name == device_name:
                    return device.interface
    return None


def get_device_messages(device: DeviceInfo) -> Dict[str, List[str]]:
    """
    Get all messages that a device can handle.
    
    Args:
        device: The device information
        
    Returns:
        Dictionary with 'receive' and 'transmit' lists of message names
    """
    if not device.interface:
        return {}
    
    messages = {'receive': [], 'transmit': []}
    
    if device.interface.messages:
        if device.interface.messages.receive:
            messages['receive'] = [port for port in device.interface.messages.receive]
        if device.interface.messages.transmit:
            messages['transmit'] = [port for port in device.interface.messages.transmit]
    
    return messages


def get_device_services(device: DeviceInfo) -> Dict[str, List[str]]:
    """
    Get all services that a device can handle.
    
    Args:
        device: The device information
        
    Returns:
        Dictionary with 'server' and 'client' lists of service names
    """
    if not device.interface:
        return {}
    
    services = {'server': [], 'client': []}
    
    if device.interface.services:
        if device.interface.services.server:
            services['server'] = [port for port in device.interface.services.server]
        if device.interface.services.client:
            services['client'] = [port for port in device.interface.services.client]
    
    return services


def get_required_imports(result: ComposeResult) -> List[str]:
    """
    Get a list of all required Python imports for the composed system.
    
    Args:
        result: The ComposeResult from compose_system
        
    Returns:
        List of import statements as strings
    """
    imports = []
    
    for port_type in result.all_dsdl_modules:
        module_path = dsdl_module_to_import_path(port_type)
        # Extract class name from module path
        imports.append(module_path)
    
    return sorted(imports)
6

def print_compose_report(result: ComposeResult) -> None:
    """
    Print a comprehensive report of the composition result.
    
    Args:
        result: The ComposeResult from compose_system
    """
    print("=" * 80)
    print("NOVA-CAN SYSTEM COMPOSITION REPORT")
    print("=" * 80)
    
    if result.success:
        print("✅ COMPOSITION SUCCESSFUL")
    else:
        print("❌ COMPOSITION FAILED")
    
    print(f"\n📊 SUMMARY:")
    total_devices = len(result.system.devices) if result.system else 0
    print(f"  Total devices: {total_devices}")
    print(f"  DSDL modules required: {len(result.all_dsdl_modules)}")
    print(f"  Errors: {len(result.errors)}")
    
    if result.system:
        print(f"\n🏗️  UNIFIED SYSTEM:")
        print(f"  📁 {result.system.name}")
        for bus in result.system.can_buses:
            print(f"    🔌 {bus.name} ({bus.rate} bps)")
            for device in bus.devices:
                status = "✅" if device.interface else "❌"
                interface_name = device.interface.name if device.interface else "N/A"
                print(f"      {status} {device.name} (Node {device.node_id}) - {device.device_type} -> {interface_name}")
    
    if result.all_dsdl_modules:
        print(f"\n📦 DSDL MODULES:")
        for module in sorted(result.all_dsdl_modules):
            module_path = dsdl_module_to_import_path(module)
            print(f"  📄 {module_path}")
    
    if result.errors:
        print(f"\n❌ ERRORS:")
        for error in result.errors:
            print(f"  🚨 {error.error_type}: {error.message}")
            if error.file_path:
                print(f"     File: {error.file_path}")
            if error.details:
                for key, value in error.details.items():
                    print(f"     {key}: {value}")
            print()
    
    if result.success and result.all_dsdl_modules:
        print(f"\n📋 REQUIRED IMPORTS:")
        imports = get_required_imports(result)
        for imp in imports:
            print(f"  {imp}")
    
    if result.success and result.system:
        print(f"\n🔍 LOOKUP CAPABILITIES:")
        print(f"  📁 System: {result.system.name}")
        
        # Show devices with their details
        if result.system.devices:
            print(f"    📱 Devices ({len(result.system.devices)}):")
            for device_name, device in result.system.devices.items():
                interface_name = device.interface.name if device.interface else "N/A"
                print(f"      • {device_name} (Node {device.node_id}, Type: {device.device_type}, Bus: {device.can_bus})")
                print(f"        └─ Interface: {interface_name}")
                
                # Show messages and services for this device
                if device.interface:
                    messages = get_device_messages(device)
                    services = get_device_services(device)
                    
                    if messages.get('receive') or messages.get('transmit'):
                        print(f"        └─ Messages:")
                        if messages.get('receive'):
                            print(f"           📥 Receive: {', '.join(messages['receive'])}")
                        if messages.get('transmit'):
                            print(f"           📤 Transmit: {', '.join(messages['transmit'])}")
                    
                    if services.get('server') or services.get('client'):
                        print(f"        └─ Services:")
                        if services.get('server'):
                            print(f"           🖥️  Server: {', '.join(services['server'])}")
                        if services.get('client'):
                            print(f"           💻 Client: {', '.join(services['client'])}")
        else:
            print(f"    📱 Devices: None")
        
        # Show interfaces summary
        if result.system.interfaces:
            print(f"    🔌 Interfaces ({len(result.system.interfaces)}):")
            for interface_name, interface in result.system.interfaces.items():
                print(f"      • {interface_name} (v{interface.version})")
        else:
            print(f"    🔌 Interfaces: None")
    
    print("=" * 80)

    
def get_compose_result_from_env() -> ComposeResult:
    """ Move to nova_can CLI """

    ### Get system and interface search paths from environment variables
    system_search_path = os.environ.get("NOVA_CAN_SYSTEMS_PATH")
    if not system_search_path:
        print("Error: NOVA_CAN_SYSTEMS_PATH must be set")
        return
    system_search_dirs = system_search_path.split(os.pathsep)
    if system_search_dirs == [""]:
        print("Error: NOVA_CAN_SYSTEMS_PATH is empty")
        return

    ### Get interface search paths from environment variables
    interface_search_path = os.environ.get("NOVA_CAN_INTERFACES_PATH")
    if not interface_search_path:
        print("Error: NOVA_CAN_INTERFACES_PATH must be set")
        return
    interface_search_dirs = interface_search_path.split(os.pathsep)
    if interface_search_dirs == [""]:
        print("Error: NOVA_CAN_INTERFACES_PATH is empty")
        return

    ### Compose system
    return compose_system(system_search_dirs, interface_search_dirs)

def compose_report():
    """ Move to nova_can CLI """

    ### Get system and interface search paths from environment variables
    system_search_path = os.environ.get("NOVA_CAN_SYSTEMS_PATH")
    if not system_search_path:
        print("Error: NOVA_CAN_SYSTEMS_PATH must be set")
        return
    system_search_dirs = system_search_path.split(os.pathsep)
    if system_search_dirs == [""]:
        print("Error: NOVA_CAN_SYSTEMS_PATH is empty")
        return

    ### Get interface search paths from environment variables
    interface_search_path = os.environ.get("NOVA_CAN_INTERFACES_PATH")
    if not interface_search_path:
        print("Error: NOVA_CAN_INTERFACES_PATH must be set")
        return
    interface_search_dirs = interface_search_path.split(os.pathsep)
    if interface_search_dirs == [""]:
        print("Error: NOVA_CAN_INTERFACES_PATH is empty")
        return

    ### Compose system
    result = compose_system(system_search_dirs, interface_search_dirs)

    ### Print report
    print_compose_report(result)

