import importlib.util
import sys
from typing import Dict, Any
from nunavut_support import get_model, to_builtin, is_service_type
from pprint import pprint

def get_field_info(field) -> Dict[str, Any]:
    """Helper function to extract field information."""
    field_info = {
        'name': field.name,
        'type': str(field.data_type),
    }
    
    # Add value range if available
    if hasattr(field.data_type, 'value_range'):
        field_info['value_range'] = {
            'min': field.data_type.value_range.min,
            'max': field.data_type.value_range.max
        }
    
    # Add field attributes if any
    if hasattr(field, 'attributes') and field.attributes:
        field_info['attributes'] = {
            attr.name: attr.value for attr in field.attributes
        }
    
    return field_info

def get_dsdl_metadata(python_binding_path: str) -> Dict[str, Any]:
    """
    Extract metadata from a DSDL file using its Python binding path.
    Supports both message and service types.
    
    Args:
        python_binding_path: Absolute path to the Python binding file
        (e.g., '/home/pih/FYP/nova-can/dsdl_python_bindings/nova_dsdl/motor_driver/msg/Command_1_0.py')
    
    Returns:
        Dictionary containing all metadata about the DSDL type
    """
    try:
        # Get the module name from the file path
        module_name = python_binding_path.split('/dsdl_python_bindings/')[-1]
        module_name = module_name.replace('/', '.').replace('.py', '')

        # Load the module from the file path
        spec = importlib.util.spec_from_file_location(module_name, python_binding_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load module specification from {python_binding_path}")
            
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        
        # Get the main class (Command_1_0 in your case)
        class_name = python_binding_path.split('/')[-1].replace('.py', '')
        main_class = getattr(module, class_name)
        
        # Create an instance with default values
        instance = main_class()
        
        metadata = {
            'name': python_binding_path,  # We'll update this for service types
            'version': None,  # We'll update this from request/response
            'fixed_port_id': None,
            'deprecated': None,
            'is_service': is_service_type(main_class)
        }

        if is_service_type(main_class):
            # For service types, we need to handle Request and Response separately
            req_class = main_class.Request
            resp_class = main_class.Response
            
            # Create instances
            req_instance = req_class()
            resp_instance = resp_class()
            
            # Get models for both
            req_model = get_model(req_instance)
            resp_model = get_model(resp_instance)
            
            # Update metadata with service type info
            metadata.update({
                'name': req_model.full_name.rsplit('.', 1)[0],  # Remove .Request
                'version': f"{req_model.version.major}.{req_model.version.minor}",
                'fixed_port_id': req_model.fixed_port_id,
                'deprecated': req_model.deprecated,
                'service': {
                    'request': {
                        'fields': [],
                        'constants': [],
                        'bit_length': req_model.bit_length_set.max,
                        'byte_length': req_model.bit_length_set.max // 8,
                        'default_values': to_builtin(req_instance)
                    },
                    'response': {
                        'fields': [],
                        'constants': [],
                        'bit_length': resp_model.bit_length_set.max,
                        'byte_length': resp_model.bit_length_set.max // 8,
                        'default_values': to_builtin(resp_instance)
                    }
                }
            })
            
            # Process Request fields
            for field in req_model.fields:
                metadata['service']['request']['fields'].append(get_field_info(field))
            
            # Process Response fields
            for field in resp_model.fields:
                metadata['service']['response']['fields'].append(get_field_info(field))
            
            # Process constants if any
            if hasattr(req_model, 'constants'):
                for constant in req_model.constants:
                    const_info = {
                        'name': constant.name,
                        'type': str(constant.data_type),
                        'value': constant.value
                    }
                    metadata['service']['request']['constants'].append(const_info)
            
            if hasattr(resp_model, 'constants'):
                for constant in resp_model.constants:
                    const_info = {
                        'name': constant.name,
                        'type': str(constant.data_type),
                        'value': constant.value
                    }
                    metadata['service']['response']['constants'].append(const_info)
            
        else:
            # Handle message types (original behavior)
            model = get_model(instance)
            metadata.update({
                'name': model.full_name,
                'version': f"{model.version.major}.{model.version.minor}",
                'fixed_port_id': model.fixed_port_id,
                'deprecated': model.deprecated,
                'bit_length': model.bit_length_set.max,
                'byte_length': model.bit_length_set.max // 8,
                'fields': [],
                'constants': [],
                'default_values': to_builtin(instance)
            })
            
            for field in model.fields:
                metadata['fields'].append(get_field_info(field))
            
            if hasattr(model, 'constants'):
                for constant in model.constants:
                    const_info = {
                        'name': constant.name,
                        'type': str(constant.data_type),
                        'value': constant.value
                    }
                    metadata['constants'].append(const_info)
        
        return metadata
        
    except ImportError as e:
        raise ImportError(f"Could not import DSDL binding from {python_binding_path}: {str(e)}")
    except Exception as e:
        raise Exception(f"Error processing DSDL metadata: {str(e)}")

def transform_dsdl_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform DSDL metadata into a simplified format focusing on fields and constants.
    
    Args:
        metadata: Dictionary containing DSDL metadata from get_dsdl_metadata()
        
    Returns:
        Dictionary containing transformed data with fields and constants in the specified format
    """
    def process_fields_and_constants(fields: list, constants: list) -> list:
        """Helper function to process fields and constants into the required format."""
        result = []
        
        # Process fields
        for field in fields:
            field_info = {
                "key": field["name"],
                "name": field["name"],
                "format": field["type"],
                "value": None  # Fields don't have values, they're variables
            }
            result.append(field_info)
        
        # Process constants
        for constant in constants:
            const_info = {
                "key": constant["name"],
                "name": constant["name"],
                "format": constant["type"],
                "value": constant["value"]
            }
            result.append(const_info)
        
        return result

    result = {
        "name": metadata["name"],
        "version": metadata["version"]
    }

    if metadata["is_service"]:
        # Handle service types
        result["type"] = "service"
        result["data"] = {
            "request": process_fields_and_constants(
                metadata["service"]["request"]["fields"],
                metadata["service"]["request"]["constants"]
            ),
            "response": process_fields_and_constants(
                metadata["service"]["response"]["fields"],
                metadata["service"]["response"]["constants"]
            )
        }
    else:
        # Handle message types
        result["type"] = "message"
        result["data"] = process_fields_and_constants(
            metadata["fields"],
            metadata["constants"]
        )

    return result

# Example usage
if __name__ == "__main__":
    try:
        # Test with a service type
        srv_path = "/home/pih/FYP/nova-can/dsdl_python_bindings/nova_dsdl/motor_driver/srv/GetPIDConstant_1_0.py"
        print("\nProcessing Service DSDL type:")
        srv_data = get_dsdl_metadata(srv_path)
        transformed_srv = transform_dsdl_metadata(srv_data)
        pprint(transformed_srv, width=80, sort_dicts=False)
        
        # Test with a message type
        msg_path = "/home/pih/FYP/nova-can/dsdl_python_bindings/nova_dsdl/motor_driver/msg/Command_1_0.py"
        print("\nProcessing Message DSDL type:")
        msg_data = get_dsdl_metadata(msg_path)
        transformed_msg = transform_dsdl_metadata(msg_data)
        pprint(transformed_msg, width=80, sort_dicts=False)
        
    except Exception as e:
        print(f"Error: {str(e)}")
