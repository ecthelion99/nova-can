from tooling.dsdl_reader.dsdl_reader import get_transformed_dsdl
from tooling.dsdl_reader.dsdl_reader import get_dsdl_metadata
from pprint import pprint



# Example usage
if __name__ == "__main__":
    try:
        # Test with a service type
        srv_path = "/home/pih/FYP/nova-can/dsdl_python_bindings/nova_dsdl/motor_driver/srv/GetPIDConstant_1_0.py"
        print("\nProcessing Service DSDL type:")
        transformed_srv = get_transformed_dsdl(srv_path)
        pprint(transformed_srv, width=80, sort_dicts=False)
        
        # Test with a message type
        msg_path = "/home/pih/FYP/nova-can/dsdl_python_bindings/nova_dsdl/motor_driver/msg/Command_1_0.py"
        transformed_msg = get_dsdl_metadata(msg_path)
        pprint(transformed_msg, width=80, sort_dicts=False)
        
    except Exception as e:
        print(f"Error: {str(e)}")
