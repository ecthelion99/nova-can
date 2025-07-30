#!/usr/bin/env python3
"""
Test runner for Nova-CAN Python tests.

This script runs all Python unit tests and provides a summary.
"""

import unittest
import sys
import os

# Add the src/python directory to the Python path
src_python_path = os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'python')
sys.path.insert(0, src_python_path)

# Also add the current directory to help with imports
sys.path.insert(0, os.path.dirname(__file__))

print(f"Python path includes: {src_python_path}")
print(f"Current working directory: {os.getcwd()}")


def run_tests():
    """Run all Python tests."""
    # Discover and run all tests in the current directory
    loader = unittest.TestLoader()
    start_dir = os.path.dirname(__file__)
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped) if hasattr(result, 'skipped') else 0}")
    
    if result.failures:
        print("\nFAILURES:")
        for test, traceback in result.failures:
            print(f"  {test}: {traceback}")
    
    if result.errors:
        print("\nERRORS:")
        for test, traceback in result.errors:
            print(f"  {test}: {traceback}")
    
    # Return appropriate exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests()) 