import sys
import os

# Set up path to import the module
sys.path.append(os.path.join(os.getcwd(), 'python_version'))

from core.logic_manager import LogicManager

def test_validation():
    print("Testing LogicManager.validate_safe_write...")

    # Test Case 1: Safe (File < Chip)
    safe, msg = LogicManager.validate_safe_write(1024, 512)
    assert safe == True
    assert msg == ""
    print("PASS: Safe case (File < Chip)")

    # Test Case 2: Safe (File == Chip)
    safe, msg = LogicManager.validate_safe_write(1024, 1024)
    assert safe == True
    assert msg == ""
    print("PASS: Safe case (File == Chip)")

    # Test Case 3: Unsafe (File > Chip)
    safe, msg = LogicManager.validate_safe_write(1024, 2048)
    assert safe == False
    assert "strictly blocked" in msg
    print("PASS: Unsafe case (File > Chip)")

    # Test Case 4: Normalization (Strings)
    safe, msg = LogicManager.validate_safe_write("1024", "512")
    assert safe == True
    print("PASS: Normalization (String inputs)")

    # Test Case 5: Invalid Input
    safe, msg = LogicManager.validate_safe_write(None, 1024)
    assert safe == False
    assert "Invalid size" in msg
    print("PASS: Invalid Input Handled")
    
    print("\nALL LOGIC TESTS PASSED.")

if __name__ == "__main__":
    test_validation()
