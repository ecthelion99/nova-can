from enum import IntEnum
from pydantic import BaseModel, Field, field_validator, model_validator, AfterValidator, ValidationError
from typing import List, Optional, Union, Annotated, TypeVar, Set
from itertools import filterfalse

class ProtocolPortIds(IntEnum):
    MIN = 0
    MAX = 32

class CustomPortIds(IntEnum):
    MIN = ProtocolPortIds.MAX + 1
    MAX = 511

def validate_name_str(v: str) -> str:
    """Validate that a name doesn't contain spaces."""
    if ' ' in v:
        raise ValueError('Name cannot contain spaces')
    return v

def validate_port_type_str(v: str) -> str:
    """Validate that a port type doesn't contain spaces."""
    if ' ' in v:
        raise ValueError('Port type cannot contain spaces')
    return v

# Annotated types for validated strings
NameStr = Annotated[str, AfterValidator(validate_name_str)]
PortTypeStr = Annotated[str, AfterValidator(validate_port_type_str)]

class Port(BaseModel):
    name: NameStr = Field(..., description="Port name without spaces")
    port_type: PortTypeStr = Field(..., description="Port type without spaces")
    port_id: Optional[int] = Field(None, ge=CustomPortIds.MIN, le=CustomPortIds.MAX)

def validate_port_ids(v: List[Port]):
    port_ids = []
    for item in v:
        if item.port_id is not None:
            port_ids.append(item.port_id)
    if len(port_ids) != len(set(port_ids)):
        raise ValueError('manually specified port_ids must be unique')
    return v

def get_port_ids(v: List[Port]) -> Set[int]:
    port_ids = []
    for item in v:
        if item.port_id is not None:
            port_ids.append(item.port_id)
    return port_ids

def assign_port_ids(v: List[Port]):
    existing_port_ids = get_port_ids(v)
    port_iterator = filterfalse(lambda x: x in existing_port_ids, range(CustomPortIds.MIN, CustomPortIds.MAX + 1))
    out_ports = []
    for item in v:
        out_ports.append(Port(name=item.name, 
                              port_type=item.port_type, 
                              port_id=next(port_iterator) if item.port_id is None else item.port_id))
    return out_ports

ValidatedPortList = Annotated[List[Port], 
                              AfterValidator(validate_port_ids), 
                              AfterValidator(assign_port_ids)]

class Messages(BaseModel):
    receive: Optional[ValidatedPortList] = Field(None)
    transmit: Optional[ValidatedPortList] = Field(None)

class Services(BaseModel):
    client: Optional[ValidatedPortList] = Field(None)
    server: Optional[ValidatedPortList] = Field(None)

class DeviceInterface(BaseModel):
    name: NameStr = Field(..., description="Interface name without spaces")
    version: str
    messages: Optional[Messages] = Field(None)
    services: Optional[Services] = Field(None)
