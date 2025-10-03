from dataclasses import dataclass
import importlib
from typing import Optional, Tuple, Self, Protocol, List
from enum import Enum
import time
import threading
from queue import SimpleQueue, Empty
import logging


import can
from typer.models import NoneType
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

def create_system_buses(system_info: SystemInfo) -> dict[str, can.BusABC]:
    return {
        bus.name: can.Bus(
                channel=bus.name,
                interface='socketcan', ## we could add support for other interfaces if we added this to the configuration
                bitrate=bus.rate
            )
            for bus in system_info.can_buses
        }


class CanTransmitter:
    def __init__(self, system_info: SystemInfo, transmitter_id: int = 0):
        self.system_info = system_info
        self.transmitter_id = transmitter_id
        self.modules = import_dsdl_modules(system_info)
        self.can_buses = create_system_buses(system_info)
    
    def send_message(self, device_name: str, port_name: str, dsdl_data_dict: dict, priority: Priority = Priority.Nominal, from_device: bool = False) -> SendResult:
        """
        Send a message to a device on a port.
        """
        device = self.system_info.devices[device_name]
        # Flip which message set we pull the port from based on perspective
        if from_device:
            port = device.interface.messages.transmit[port_name]
        else:
            port = device.interface.messages.receive[port_name]

        can_id = CanID(
            priority=priority.value,
            service=False,
            service_request=False,  
            port_id=port.port_id,
            destination_id=(0 if from_device else device.node_id),
            source_id=self.transmitter_id)
        
        
        ## TODO: Add support for multi-frame transfers
        frame_header = FrameHeader(
            start_of_transfer=True,
            end_of_transfer=True,
            transfer_id=0) ## TODO: properly deal with transfer id
        

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
    
    def stop(self):
        for _, can_bus in self.can_buses.items():
            can_bus.shutdown()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()


class CanCallback(Protocol):
    def __call__(self, system_name: str, 
                       device_name: str,
                       port_name: Port,
                       data: dict) -> None:
        ...

class CanReceiver:
    """
    Receives messages from the CAN bus and calls the callback with the parsed message.
    TODO: Add support for multi-frame transfers
    TODO: Add filters
    """
    def __init__(self, system_info: SystemInfo, callback: CanCallback, receiver_id: int = 0, recv_timeout: float = 0.1, queue_timeout: float = 0.5):
        self.system_info = system_info
        self.receiver_id = receiver_id
        self._modules = import_dsdl_modules(system_info)
        self._callback = callback
        self._recv_timeout = recv_timeout
        self._queue_timeout = queue_timeout

        self._can_buses: dict[str, can.BusABC] = None
        self._msg_queue: SimpleQueue  = None
        self._stop_event = threading.Event()
        self._bus_workers: List[threading.Thread] = []
        self._consumer_thread = None


    def _consumer_loop(self):
        while not self._stop_event.is_set():
            logging.debug(f"Queue Size: {self._msg_queue.qsize()}")
            try:
                parsed_msg = self._msg_queue.get(timeout=self._queue_timeout)
                self._callback(*parsed_msg)
            except Empty:
                continue
    
    def _worker_loop(self, bus_name: str, can_bus: can.BusABC):
        while not self._stop_event.is_set():
            msg = can_bus.recv(timeout=self._recv_timeout)
            if msg is not None:
                parsed_msg = self.parse_message(msg, bus_name)
                if parsed_msg[3] is None:
                    logging.warning(f"Invalid payload received on {parsed_msg[0]}.{parsed_msg[1]}.{parsed_msg[2].name}")
                    continue
                self._msg_queue.put(parsed_msg)

    def parse_message(self, msg: can.Message, bus_name: str) -> Optional[Tuple[str, str, str, Port, dict]]:
        if not msg.is_extended_id: #ignore sid frames (unsupported)self.parse_messag
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
        
        payload_buff = bytearray(msg.data[1:])
        serialized_fragment_view = memoryview(payload_buff)

        dsdl_class = getattr(self._modules[port.port_type], 
                             dsdl_module_to_import_path(port.port_type).split('.')[-1])
        
        deserialized_dsdl = deserialize(dsdl_class, [serialized_fragment_view])
        dsdl_data_dict = to_builtin(deserialized_dsdl)
        
        return rx_device.source_system, rx_device.name, port, dsdl_data_dict
    def start(self):
        self._msg_queue = SimpleQueue()
        self._can_buses = create_system_buses(self.system_info)
        self._consumer_thread = threading.Thread(target=self._consumer_loop, name="consumer-thread")
        for bus_name, bus in self._can_buses.items():
            self._bus_workers.append(threading.Thread(target=self._worker_loop,
                                                      name=f"{bus_name}-worker",
                                                      args=(bus_name, bus)))
        self._stop_event.clear()
        self._consumer_thread.start()
        for worker in self._bus_workers:
            worker.start()
    
    def stop(self):
        self._stop_event.set()
        for worker in self._bus_workers:
            worker.join()
        self._consumer_thread.join()
        self._consumer_thread = None
        self._bus_workers = []
        self._msg_queue = None
        for _, can_bus in self._can_buses.items():
            can_bus.shutdown()
        

    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()