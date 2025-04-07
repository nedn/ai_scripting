#!/usr/bin/env python3

import unittest
import sys
import os

def _extract_test_cases(test):
    for t in test:
        if isinstance(t, unittest.TestSuite):
            yield from _extract_test_cases(t)
        else:
            yield t

def run_tests(test_name=None):
    # Get the directory containing this script
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # Discover all test files in the current directory and subdirectories
    loader = unittest.TestLoader()
    start_dir = current_dir

    if test_name:
        # If a test name is provided, only run tests that match the name
        suite = unittest.TestSuite()
        for test in loader.discover(start_dir, pattern='*_unittest.py', top_level_dir=current_dir):
            for test_case in _extract_test_cases(test):
                if test_name.lower() in str(test_case).lower():
                    suite.addTest(test_case)
    else:
        # Run all tests if test name is provided
        suite = loader.discover(start_dir, pattern='*_unittest.py', top_level_dir=current_dir)

    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Return 0 if tests passed, 1 if any failed
    return 0 if result.wasSuccessful() else 1

if __name__ == '__main__':
    test_name = sys.argv[1] if len(sys.argv) > 1 else None
    sys.exit(run_tests(test_name))


