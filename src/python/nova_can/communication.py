from dataclasses import dataclass
import importlib
from typing import Callable, Dict, Optional, Tuple
from enum import Enum


import can
from nunavut_support import serialize, deserialize, update_from_builtin, to_builtin

from .utils import SystemInfo, import_dsdl_modules
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
class CANID:
    priority: int
    service: bool
    service_request: bool
    port_id: int
    destination_id: int
    source_id: int

    def to_serialized(self) -> int:
        return (self.priority << 26) |
                (self.service << 25) | 
                (self.service_request << 24) | 
                (self.port_id << 14) | 
                (self.destination_id << 7) | 
                self.source_id
    
    @classmethod
    def from_serialized(cls, serialized: int) -> CANID:
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

    def to_serialized(self) -> int:
        return (self.start_of_transfer << 7) | (self.end_of_transfer << 6) | (self.transfer_id)

    @classmethod
    def from_serialized(cls, serialized: int) -> FrameHeader:
        return cls(
            start_of_transfer=(serialized >> 7) & 0x01,
            end_of_transfer=(serialized >> 30) & 0x01,
            transfer_id=(serialized >> 24) & 0x7F
        )

@dataclass
class SendResult:
    success: bool
    message: str



def create_system_buses(system_info: SystemInfo) -> Dict[str, can.Bus]:
    buses = {
        bus_name: {
            bus_name: can.Bus(
                channel=bus.name,
                interface='socketcan', ## we could add support for other interfaces if we added this to the configuration
                bitrate=bus.rate
            )
            for bus in system_info.can_buses
        }
    }

class CanSender:
    def __init__(self, system_info: SystemInfo, sender_id: int = 0):
        self.system_info = system_info
        self.modules = import_dsdl_modules(system_info)
        self.can_buses = create_system_buses(system_info)
    
    def send_message(self, device_name: str, port_name: str, message: Dict, priority: Priority = Priority.Nominal) -> SendResult:
        """
        Send a message to a device on a port.
        """
        device = self.system_info.devices[device_name]
        
        can_id = CANID(
            priority=priority.value,
            service=False,
            service_request=False,
            port_id=0,
            destination_id=0,
            source_id=self.sender_id)
        
        ## TODO: Add support for multi-frame transfers
        frame_header = FrameHeader(
            start_of_transfer=True,
            end_of_transfer=False,
            transfer_id=0) ## TODO: properly deal with transfer id
        
        

class CanReceiver:
    def __init__(self, system_info: SystemInfo, receiver_id: int = 0, callback: Callable[[str, str, str, Port, Dict]]):
        self.system_info = system_info
        self.receiver_id = receiver_id
        self.modules = import_dsdl_modules(system_info)
        self.can_buses = create_system_buses(system_info)
        self.callback = callback


    def parse_message(self, msg: can.Message, bus_name: str) -> Optional[Tuple[str, str, str, Port, Dict]]:
        if msg.has_extended_id: #ignore sid frames (unsupported)
            return None
        can_id = CANID.from_serialized(msg.arbitration_id)
        if can_id.destination_id != self.receiver_id or can_id.destination_id == 0: #TODO: Filter by destination id
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
        port = device.interface.get_port_by_id(can_id.port_id).get('receive')
        if port is None:
            return None

        dsdl_class = getattr(self.modules[port.port_type], self.modules[port.port_type].split('.')[-1])
        
        

    def run(self):
        for bus_name, bus in self.can_buses.items():
            msg = bus.recv()
            if msg is not None:
                







