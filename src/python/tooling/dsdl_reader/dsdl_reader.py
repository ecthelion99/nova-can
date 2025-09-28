import importlib.util
import sys
from typing import Dict, Any
from nunavut_support import get_model, to_builtin, is_service_type
from pprint import pprint
from typing import Set, Tuple, List

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
        # Attempt to import the generated binding as a normal package/module first.
        # This avoids a circular-import problem that can occur when the package
        # __init__ performs convenience "from .X import X" imports while the
        # module itself imports the package (common in auto-generated bindings).
        module_name = python_binding_path.split('/dsdl_python_bindings/')[-1]
        module_name = module_name.replace('/', '.').replace('.py', '')

        module = None
        try:
            # Ensure the bindings directory is on sys.path so normal package imports work
            bindings_root = python_binding_path.split('/dsdl_python_bindings/')[0] + '/dsdl_python_bindings'
            if bindings_root not in sys.path:
                sys.path.insert(0, bindings_root)

            module = importlib.import_module(module_name)
        except Exception:
            # Fall back to loading directly from file if package import fails
            spec = importlib.util.spec_from_file_location(module_name, python_binding_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Could not load module specification from {python_binding_path}")

            module = importlib.util.module_from_spec(spec)
            # Register the module under the expected name to support other imports
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

        def _flatten_fields_and_constants(instance, model, prefix: str = "", seen: Set[str] = None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
            """
            Recursively flatten fields and constants from a model/instance pair.
            Returns (fields, constants) where each field is a dict like get_field_info()
            but with the 'name' replaced by the dotted prefix (e.g. 'yahoo.v1').
            """
            if seen is None:
                seen = set()

            fields_out: List[Dict[str, Any]] = []
            consts_out: List[Dict[str, Any]] = []

            # Avoid infinite recursion on recursive types by tracking model full names
            model_name = getattr(model, 'full_name', None)
            if model_name:
                if model_name in seen:
                    return fields_out, consts_out
                seen.add(model_name)

            # Collect constants defined on this model (prefix name)
            if hasattr(model, 'constants') and model.constants:
                for constant in model.constants:
                    const_entry = {
                        'name': f"{prefix + '.' if prefix else ''}{constant.name}",
                        'type': str(constant.data_type),
                        'value': constant.value
                    }
                    consts_out.append(const_entry)

            for field in model.fields:
                field_name = field.name
                full_name = f"{prefix + '.' if prefix else ''}{field_name}"

                # Try to get the attribute value from the instance (uses default values)
                try:
                    attr_val = getattr(instance, field_name)
                except Exception:
                    attr_val = None

                # If the attribute itself is a generated DSDL instance, recurse
                try:
                    nested_model = get_model(attr_val)
                except Exception:
                    nested_model = None

                if nested_model is not None:
                    # Recurse into nested structure
                    nested_fields, nested_consts = _flatten_fields_and_constants(attr_val, nested_model, full_name, seen)
                    fields_out.extend(nested_fields)
                    consts_out.extend(nested_consts)
                else:
                    # Not a nested structure we can introspect; treat as primitive/array
                    finfo = get_field_info(field)
                    # Replace name with the dotted full name
                    finfo['name'] = full_name
                    fields_out.append(finfo)

            return fields_out, consts_out

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
            req_fields, req_consts = _flatten_fields_and_constants(req_instance, req_model)
            metadata['service']['request']['fields'].extend(req_fields)
            # include nested constants discovered
            metadata['service']['request']['constants'].extend(req_consts)
            
            # Process Response fields
            resp_fields, resp_consts = _flatten_fields_and_constants(resp_instance, resp_model)
            metadata['service']['response']['fields'].extend(resp_fields)
            metadata['service']['response']['constants'].extend(resp_consts)
            
            # Process constants if any
            # Top-level constants already handled by _flatten_fields_and_constants
            
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
            
            # Flatten fields and constants for the message type
            flat_fields, flat_consts = _flatten_fields_and_constants(instance, model)
            metadata['fields'].extend(flat_fields)
            metadata['constants'].extend(flat_consts)
        
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

def get_transformed_dsdl(file_path: str) -> Dict[str, Any]:
    """
    Wrapper function that retrieves DSDL metadata and transforms it into a simplified format.
    
    Args:
        file_path: Absolute path to the Python binding file
        (e.g., '/home/pih/FYP/nova-can/dsdl_python_bindings/nova_dsdl/motor_driver/msg/Command_1_0.py')
        
    Returns:
        Dictionary containing transformed DSDL data with the following structure:
        For message types:
        {
            'name': str,
            'version': str,
            'type': 'message',
            'data': [
                {
                    'key': str,
                    'name': str,
                    'format': str,
                    'value': Any or None
                },
                ...
            ]
        }
        
        For service types:
        {
            'name': str,
            'version': str,
            'type': 'service',
            'data': {
                'request': [...],  # List of fields/constants as above
                'response': [...]  # List of fields/constants as above
            }
        }
    """
    try:
        # Get the raw metadata
        metadata = get_dsdl_metadata(file_path)
        
        # Transform it into the simplified format
        transformed_data = transform_dsdl_metadata(metadata)
        
        return transformed_data
        
    except Exception as e:
        raise Exception(f"Error processing DSDL file {file_path}: {str(e)}")


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
