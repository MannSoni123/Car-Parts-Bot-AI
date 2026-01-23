
from app.services.extract_vin_service import extract_vin_from_text, get_vin_validation_error

def test_case(input_text, description, expected_error_substr=None):
    print(f"--- {description} ---")
    print(f"Input: '{input_text}'")
    
    extracted = extract_vin_from_text(input_text)
    error = get_vin_validation_error(input_text)
    
    print(f"Extracted: {extracted}")
    print(f"Validation Error: {error}")
    
    if expected_error_substr:
        if error and expected_error_substr.lower() in error.lower():
            print("✅ PASS: Correct error returned")
        else:
            print(f"❌ FAIL: Expected error containing '{expected_error_substr}', got '{error}'")
    else:
        if extracted and not error:
             print("✅ PASS: Valid VIN extracted, no error")
        elif not extracted and not error:
             print("✅ PASS: No VIN, no error (ignored text)")
        else:
             print(f"❌ FAIL: Unexpected result. Extracted: {extracted}, Error: {error}")
    print("\n")

if __name__ == "__main__":
    # Case 1: The user reported issue (19 chars)
    test_case("WVAVPN7C524AA778342", "User reported broken VIN (19 chars)", "19 characters")

    # Case 2: Illegal characters
    test_case("1HGCM82633A00435I", "VIN with 'I'", "letters I, O, or Q")
    test_case("1HGCM82633A00435Q", "VIN with 'Q'", "letters I, O, or Q")

    # Case 3: Valid VIN
    test_case("1HGCM82633A004352", "Valid 17-char VIN", None)
    
    # Case 4: Random text (should be ignored)
    test_case("Hello world how are you", "Random text", None)
    
    # Case 5: Short candidate
    test_case("ABC1234567890", "13 char alphanumeric", "13 characters")
