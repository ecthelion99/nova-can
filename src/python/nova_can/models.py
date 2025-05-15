from pydantic import BaseModel, Field, field_validator, model_validator, AfterValidator, ValidationError
from typing import List, Optional, Union, Annotated



class Message(BaseModel):
    name: str
    msg_type: str
    subject_id: Optional[int] = Field(None, ge=33, le=511)

class Service(BaseModel):
    name: str
    request_type: str
    response_type: str
    subject_id: Optional[int] = Field(None, ge=33, le=511)

def validate_subject_ids(v: Union[List[Message], List[Service]]):
    subject_ids = []
    for item in v:
        if item.subject_id is not None:
            subject_ids.append(item.subject_id)
    if len(subject_ids) != len(set(subject_ids)):
        raise ValueError('manually specified subject_ids must be unique')
    return v

class Messages(BaseModel):
    receive: Optional[Annotated[List[Message], AfterValidator(validate_subject_ids)]] = Field(None)
    transmit: Optional[Annotated[List[Message], AfterValidator(validate_subject_ids)]] = Field(None)

class Services(BaseModel):
    client: Optional[Annotated[List[Service], AfterValidator(validate_subject_ids)]] = Field(None)
    server: Optional[Annotated[List[Service], AfterValidator(validate_subject_ids)]] = Field(None)

class DeviceInterface(BaseModel):
    device: str
    version: str
    messages: Optional[Messages] = Field(None)
    services: Optional[Services] = Field(None)

class CanBusDevice(BaseModel):
    name: str
    node_id: int = Field(ge=1, le=127)
    device_type: str

class CanBus(BaseModel):
    name: str
    rate: int
    devices: List[CanBusDevice]

    @field_validator('rate', mode='before')
    def validate_rate(cls, v: int):
        if v not in [125000, 250000, 500000, 1000000, 2000000, 3000000, 5000000]:
            raise ValueError('rate must be one of the typical CAN/CAN FD rates')
        return v

class SystemDefinition(BaseModel):
    name: str
    can_buses: List[CanBus]

if __name__ == '__main__':
    import yaml
    with open('spec/interfaces/motor_driver.yaml', 'r') as f:
        data = yaml.safe_load(f)
    try:
        device_interface = DeviceInterface(**data)
    except ValidationError as e:
        print(e.errors())
    print(device_interface)
