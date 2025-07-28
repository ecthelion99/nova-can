from pydantic import BaseModel, Field
from typing import List
from enum import IntEnum

from nova_can.device_models import DeviceInterface

class NodeId(IntEnum):
    MIN = 1
    MAX = 127

class CanBusRate(IntEnum):
    RATE_125K = 125000
    RATE_250K = 250000
    RATE_500K = 500000
    RATE_1M = 1000000
    RATE_2M = 2000000
    RATE_3M = 3000000
    RATE_5M = 5000000

class CanBusDevice(BaseModel):
    name: str
    node_id: int = Field(ge=NodeId.MIN, le=NodeId.MAX)
    device_type: str

class CanBus(BaseModel):
    name: str
    rate: CanBusRate
    devices: List[CanBusDevice]

class SystemDefinition(BaseModel):
    name: str
    can_buses: List[CanBus]