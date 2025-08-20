from dataclasses import dataclass
import importlib
from typing import Callable, Dict, Optional, Tuple, Self, Protocol
from enum import Enum
import time


import can
from nunavut_support import serialize, deserialize, update_from_builtin, to_builtin

from .utils import SystemInfo, import_dsdl_modules, dsdl_module_to_import_path
from .models import Port

class Priority(Enum):
    Critical = 0
    Immediate = 1
    Fast = 2
    High = 3
    Nominal = 4
    Low = 5
    Slow = 6
    Optional = 7


@dataclass
class CanID:
    priority: int
    service: bool
    service_request: bool
    port_id: int
    destination_id: int
    source_id: int

    def to_serialized(self) -> int:
        return (self.priority << 26) |\
                (self.service << 25) | \
                (self.service_request << 24) | \
                (self.port_id << 14) | \
                (self.destination_id << 7) | \
                self.source_id
    
    @classmethod
    def from_serialized(cls, serialized: int) -> Self:
        return cls(
            priority=(serialized >> 26) & 0x07,
            service=(serialized >> 25) & 0x01,
            service_request=(serialized >> 24) & 0x01,
            port_id=(serialized >> 14) & 0x1FF,
            destination_id=(serialized >> 7) & 0x3F,
            source_id=serialized & 0x3F
        )

@dataclass
class FrameHeader:
    start_of_transfer: bool
    end_of_transfer: bool
    transfer_id: int

    def to_serialized(self) -> bytes:
        return ((self.start_of_transfer << 7) | (self.end_of_transfer << 6) | (self.transfer_id)).to_bytes(1, 'big')

    @classmethod
    def from_serialized(cls, serialized: int) -> Self:
        return cls(
            start_of_transfer=(serialized >> 7) & 0x01,
            end_of_transfer=(serialized >> 6) & 0x01,
            transfer_id=(serialized) & 0x7F
        )

@dataclass
class SendResult:
    success: bool
    message: str

def create_system_buses(system_info: SystemInfo) -> Dict[str, can.Bus]:
    return {
        bus.name: can.Bus(
                channel=bus.name,
                interface='socketcan', ## we could add support for other interfaces if we added this to the configuration
                bitrate=bus.rate
            )
            for bus in system_info.can_buses
        }


class CanTransmitter:
    def __init__(self, system_info: SystemInfo, sender_id: int = 0):
        self.system_info = system_info
        self.sender_id = sender_id
        self.modules = import_dsdl_modules(system_info)
        self.can_buses = create_system_buses(system_info)
    
    def send_message(self, device_name: str, port_name: str, dsdl_data_dict: Dict, priority: Priority = Priority.Nominal) -> SendResult:
        """
        Send a message to a device on a port.
        """
        device = self.system_info.devices[device_name]
        port = device.interface.messages.receive[port_name]

        can_id = CanID(
            priority=priority.value,
            service=False,
            service_request=False,  
            port_id=port.port_id,
            destination_id=device.node_id,
            source_id=self.sender_id)
        
        
        ## TODO: Add support for multi-frame transfers
        frame_header = FrameHeader(
            start_of_transfer=True,
            end_of_transfer=True,
            transfer_id=0) ## TODO: properly deal with transfer id
        <<<<<<< HEAD
        dsdl_class = getattr(self.modules[port.port_type], 
                             dsdl_module_to_import_path(port.port_type).split('.')[-1])
        
        dsdl_instance = dsdl_class()
        update_from_builtin(dsdl_instance, dsdl_data_dict)
        fragments = serialize(dsdl_instance)

        ## TODO: add support for multi-frame transfers
        ## TODO: Zero-copy implementation for improved performance
        data_bytes = frame_header.to_serialized() + b"".join(fragment.tobytes() for fragment in fragments)

        message = can.Message(arbitration_id=can_id.to_serialized(), is_extended_id=True,
                              data=data_bytes)
        
        self.can_buses[device.can_bus].send(message)
        
        return SendResult(success=True, message=f"Message sent to {device_name} on {port_name}")
        

class CanCallback(Protocol):
    def __call__(self, system_name: str, 
                       device_name: str,
                       port_name: Port,
                       data: Dict) -> None:
        ...

class CanReceiver:
    """
    Receives messages from the CAN bus and calls the callback with the parsed message.
    TODO: Add support for multi-frame transfers
    TODO: Need to handle the case where we want to receive a message that we sent (eg, a receive message from a device)
    """
    def __init__(self, system_info: SystemInfo, callback: CanCallback, receiver_id: int = 0):
        self.system_info = system_info
        self.receiver_id = receiver_id
        self.modules = import_dsdl_modules(system_info)
        self.can_buses = create_system_buses(system_info)
        self.callback = callback


    def parse_message(self, msg: can.Message, bus_name: str) -> Optional[Tuple[str, str, str, Port, Dict]]:
        if not msg.is_extended_id: #ignore sid frames (unsupported)
            return None
        can_id = CanID.from_serialized(msg.arbitration_id)
        if can_id.destination_id != self.receiver_id and can_id.destination_id != 0: #TODO: Filter by destination id
            return None
        
        if can_id.service: #TODO: Handle service messages
            return None
        
        rx_device = None

        for device in self.system_info.get_devices_by_id(can_id.source_id):
            if device.can_bus == bus_name:
                rx_device = device

        if rx_device is None:
            return None

        if device.interface is None:
            return None
        port = device.interface.get_port_by_id(can_id.port_id).get('transmit')
        if port is None:
            return None

        header = FrameHeader.from_serialized(msg.data[0])
        if header.start_of_transfer and not header.end_of_transfer: #TODO: Handle multi-frame transfers
            return None
        if not header.start_of_transfer and header.end_of_transfer: #TODO: Handle multi-frame transfers
            return None
        
        deserialized_dsdl = deserialize(dsdl_class, [serialized_fragment_view])
        dsdl_data_dict = to_builtin(deserialized_dsdl)
        
        serialized_fragment_view = memoryview(msg.data[1:])

        dsdl_class = getattr(self.modules[port.port_type], 
                             dsdl_module_to_import_path(port.port_type).split('.')[-1])
        
        deserialized_dsdl = deserialize(dsdl_class, [serialized_fragment_view])
        dsdl_data_dict = to_builtin(deserialized_dsdl)
        
        return rx_device.source_system, rx_device.name, port, dsdl_data_dict

    def run(self):
        while True:
            for bus_name, bus in self.can_buses.items():
                msg = bus.recv()
                if msg is not None:
                    result = self.parse_message(msg, bus_name)
                    if result is not None:
                        self.callback(*result)
            time.sleep(0.001) ##TODO: switch to selectors for better perfomance/latency
            
            







