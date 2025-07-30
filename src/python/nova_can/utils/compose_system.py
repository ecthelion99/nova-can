"""
System composition utilities for Nova-CAN.

This module provides functions to verify and compose Nova-CAN systems from
YAML configuration files and DSDL Python bindings.
"""

import os
import glob
import yaml
from typing import List, Dict, Set, Optional, Tuple, Any
from dataclasses import dataclass, field
from pathlib import Path
import importlib
import importlib.util

from nova_can.models.system_models import SystemDefinition
from nova_can.models.device_models import DeviceInterface


@dataclass
class ComposeError:
    """Represents a composition error with details."""
    error_type: str
    message: str
    file_path: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


@dataclass
class InterfaceInfo:
    """Information about a device interface."""
    name: str
    version: str
    file_path: str
    interface_name: str = ""  # The filename without extension
    messages: Dict[str, Any] = field(default_factory=dict)
    services: Dict[str, Any] = field(default_factory=dict)
    dsdl_modules: Set[str] = field(default_factory=set)


@dataclass
class DeviceInfo:
    """Information about a device in a system."""
    name: str
    node_id: int
    device_type: str
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


@dataclass
class ComposeResult:
    """Result of system composition."""
    systems: List[SystemInfo] = field(default_factory=list)
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


def _dsdl_module_to_import_path(port_type: str) -> str:
    """Convert a DSDL port type to a Python import path."""
    # Convert "nova.motor_driver.msg.Command.1.0" to "nova.motor_driver.msg.Command_1_0"
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
    4. Returns a comprehensive result with all systems, interfaces, and any errors
    
    Args:
        system_search_dirs: List of directories to search for system YAML files
        interface_search_dirs: List of directories to search for interface YAML files
        
    Returns:
        ComposeResult containing systems, interfaces, errors, and missing modules
    """
    result = ComposeResult()
    
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
    
    # Step 2: Process each system file
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
        
        # Create SystemInfo
        system_info = SystemInfo(
            name=system_def.name,
            file_path=system_file
        )
        
        # Process CAN buses and devices
        for bus_def in system_def.can_buses:
            bus_info = CanBusInfo(
                name=bus_def.name,
                rate=bus_def.rate
            )
            
            for device_def in bus_def.devices:
                device_info = DeviceInfo(
                    name=device_def.name,
                    node_id=device_def.node_id,
                    device_type=device_def.device_type
                )
                bus_info.devices.append(device_info)
                
                # Add to fast lookup dictionary
                system_info.devices[device_info.name] = device_info
            
            system_info.can_buses.append(bus_info)
        
        result.systems.append(system_info)
    
    # Step 3: Find and validate all interface YAML files
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
    
    # Step 4: Collect interface files (processing moved to Step 5)
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
    
    # Step 5: Link interfaces to CAN buses and verify DSDL modules
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
        
        all_interfaces[interface_name] = interface_info
    
    # Now attach interfaces to devices
    for system_info in result.systems:
        for bus_info in system_info.can_buses:
            for device_info in bus_info.devices:
                # Find the interface for this device
                device_type = device_info.device_type
                if '/' in device_type:
                    device_type = device_type.split('/')[-1]
                
                interface_info = all_interfaces.get(device_type)
                if interface_info:
                    device_info.interface = interface_info
                    
                    # Add interface to fast lookup dictionary
                    system_info.interfaces[device_type] = interface_info
                    

                    
                    # Check DSDL module availability
                    for port_type in interface_info.dsdl_modules:
                        module_path = _dsdl_module_to_import_path(port_type)
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
                            "system": system_info.name,
                            "bus": bus_info.name
                        }
                    ))
    
    return result


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
        if device.interface.messages.get('receive'):
            messages['receive'] = [msg.get('name', '') for msg in device.interface.messages['receive']]
        if device.interface.messages.get('transmit'):
            messages['transmit'] = [msg.get('name', '') for msg in device.interface.messages['transmit']]
    
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
        if device.interface.services.get('server'):
            services['server'] = [srv.get('name', '') for srv in device.interface.services['server']]
        if device.interface.services.get('client'):
            services['client'] = [srv.get('name', '') for srv in device.interface.services['client']]
    
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
        module_path = _dsdl_module_to_import_path(port_type)
        # Extract class name from module path
        class_name = module_path.split('.')[-1]
        imports.append(f"from {module_path} import {class_name}")
    
    return sorted(imports)


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
    print(f"  Systems found: {len(result.systems)}")
    total_devices = sum(len(bus.devices) for s in result.systems for bus in s.can_buses)
    print(f"  Total devices: {total_devices}")
    print(f"  DSDL modules required: {len(result.all_dsdl_modules)}")
    print(f"  Errors: {len(result.errors)}")
    
    if result.systems:
        print(f"\n🏗️  SYSTEMS:")
        for system in result.systems:
            print(f"  📁 {system.name} ({system.file_path})")
            for bus in system.can_buses:
                print(f"    🔌 {bus.name} ({bus.rate} bps)")
                for device in bus.devices:
                    status = "✅" if device.interface else "❌"
                    interface_name = device.interface.name if device.interface else "N/A"
                    print(f"      {status} {device.name} (Node {device.node_id}) - {device.device_type} -> {interface_name}")
    
    if result.all_dsdl_modules:
        print(f"\n📦 DSDL MODULES:")
        for module in sorted(result.all_dsdl_modules):
            module_path = _dsdl_module_to_import_path(module)
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
    
    if result.success and result.systems:
        print(f"\n🔍 LOOKUP CAPABILITIES:")
        for system in result.systems:
            print(f"  📁 System: {system.name}")
            
            # Show devices with their details
            if system.devices:
                print(f"    📱 Devices ({len(system.devices)}):")
                for device_name, device in system.devices.items():
                    interface_name = device.interface.name if device.interface else "N/A"
                    print(f"      • {device_name} (Node {device.node_id}, Type: {device.device_type})")
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
            if system.interfaces:
                print(f"    🔌 Interfaces ({len(system.interfaces)}):")
                for interface_name, interface in system.interfaces.items():
                    print(f"      • {interface_name} (v{interface.version})")
            else:
                print(f"    🔌 Interfaces: None")
            
            print()  # Add spacing between systems
    
    print("=" * 80)

def compose_report():
    """ Move to nova_can CLI """

    ### Get system and interface search paths from environment variables
    system_search_path = os.environ.get("NOVA_CAN_SYSTEM_PATHS")
    if not system_search_path:
        print("Error: NOVA_CAN_SYSTEM_PATHS must be set")
        return
    system_search_dirs = system_search_path.split(os.pathsep)
    if system_search_dirs == [""]:
        print("Error: NOVA_CAN_SYSTEM_PATHS is empty")
        return

    ### Get interface search paths from environment variables
    interface_search_path = os.environ.get("NOVA_CAN_INTERFACE_PATHS")
    if not interface_search_path:
        print("Error: NOVA_CAN_INTERFACE_PATHS must be set")
        return
    interface_search_dirs = interface_search_path.split(os.pathsep)
    if interface_search_dirs == [""]:
        print("Error: NOVA_CAN_INTERFACE_PATHS is empty")
        return

    ### Compose system
    result = compose_system(system_search_dirs, interface_search_dirs)

    ### Print report
    print_compose_report(result)