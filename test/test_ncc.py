import unittest

from tooling.ncc.ncc import dsdl_header_path

class TestNCC(unittest.TestCase):
    def test_dsdl_header_path(self):
        """Test DSDL header path generation"""
        test_cases = [
            ("nova.motor_driver.msg.Command.1.0", "nova/motor_driver/msg/Command_1_0.h"),
            ("nova.motor_driver.srv.SetPIDConstant.1.0", "nova/motor_driver/srv/SetPIDConstant_1_0.h"),
            ("simple.type.1.0", "simple/type_1_0.h"),
        ]
        
        for input_type, expected_path in test_cases:
            result = dsdl_header_path(input_type)
            self.assertEqual(result, expected_path)

if __name__ == "__main__":
    unittest.main() 