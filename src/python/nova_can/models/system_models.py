from pydantic import BaseModel, Field, field_validator, AfterValidator
from typing import List, Annotated
from enum import IntEnum

def validate_name_str(v: str) -> str:
    """Validate that a name doesn't contain spaces."""
    if ' ' in v:
        raise ValueError('Name cannot contain spaces')
    return v

def validate_device_type_str(v: str) -> str:
    """Validate that a device type doesn't contain spaces."""
    if ' ' in v:
        raise ValueError('Device type cannot contain spaces')
    return v

# Annotated types for validated strings
NameStr = Annotated[str, AfterValidator(validate_name_str)]
DeviceTypeStr = Annotated[str, AfterValidator(validate_device_type_str)]

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
    name: NameStr = Field(..., description="Device name without spaces")
    node_id: int = Field(ge=NodeId.MIN, le=NodeId.MAX)
    device_type: DeviceTypeStr = Field(..., description="Device type without spaces")

class CanBus(BaseModel):
    name: NameStr = Field(..., description="CAN bus name without spaces")
    rate: CanBusRate
    devices: List[CanBusDevice]

class SystemDefinition(BaseModel):
    name: NameStr = Field(..., description="System name without spaces")
    can_buses: List[CanBus]