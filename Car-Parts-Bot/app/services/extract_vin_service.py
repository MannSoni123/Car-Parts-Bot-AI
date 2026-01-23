import re
from typing import Optional

VIN_REGEX = re.compile(
    r"\b[A-HJ-NPR-Z0-9]{17}\b",
    re.IGNORECASE
)

def extract_vin_from_text(text: str) -> Optional[str]:
    """
    Extract a valid 17-character VIN from text.
    Returns VIN if found, else None.
    """
    if not text:
        return None

    match = VIN_REGEX.search(text.upper())
    return match.group(0) if match else None

def get_vin_validation_error(text: str) -> Optional[str]:
    """
    Check if text contains a potential VIN that is invalid
    (e.g. wrong length, invalid chars).
    Returns a user-friendly error message if an issue is found.
    """
    if not text:
        return None
        
    text_upper = text.upper()
    
    # 1. Check for illegal characters I, O, Q in what looks like a VIN
    # Look for a 17-char alphanumeric string that might contain I/O/Q
    broad_pattern = re.compile(r'\b[A-Z0-9]{17}\b')
    potential_match = broad_pattern.search(text_upper)
    
    if potential_match:
        candidate = potential_match.group(0)
        invalid_chars = [c for c in candidate if c in "IOQ"]
        if invalid_chars:
            chars_str = ", ".join(sorted(list(set(invalid_chars))))
            return f"Chassis numbers cannot contain letters I, O, or Q (found: {chars_str}). Did you mean 1, 0, or 0?"

    # 2. Check for length issues
    # Look for long alphanumeric sequences that look like VINs but are wrong length
    # We look for 13-20 chars alphanumeric, but NOT 17 chars (which would be handled above or be valid)
    length_pattern = re.compile(r'\b[A-Z0-9]{13,20}\b')
    matches = length_pattern.findall(text_upper)
    
    for candidate in matches:
        # Ignore if it's actually 17 chars (handled by extraction logic validation)
        if len(candidate) == 17:
             continue
             
        # Heuristic: mostly letters/numbers mixed? (simple check: has at least 1 digit and 1 letter)
        has_letter = any(c.isalpha() for c in candidate)
        has_digit = any(c.isdigit() for c in candidate)
        
        if has_letter and has_digit:
             return f"Chassis number seems to be {len(candidate)} characters long. A valid VIN must be exactly 17 characters."

    return None
