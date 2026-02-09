# -*- coding: utf-8 -*-
"""
File Upload Security
Validates uploaded files for security threats
"""

import hashlib
import magic
from typing import Tuple, Dict
import re

# Allowed MIME types
ALLOWED_MIME_TYPES = {
    'image/png': ['.png'],
    'image/jpeg': ['.jpg', '.jpeg'],
    'application/pdf': ['.pdf'],
    'text/plain': ['.txt'],
    'text/markdown': ['.md'],
}

# Maximum file sizes (bytes)
MAX_FILE_SIZES = {
    'image/png': 10 * 1024 * 1024,  # 10MB
    'image/jpeg': 10 * 1024 * 1024,  # 10MB
    'application/pdf': 20 * 1024 * 1024,  # 20MB
    'text/plain': 5 * 1024 * 1024,  # 5MB
    'text/markdown': 5 * 1024 * 1024,  # 5MB
}

# Known malicious file signatures (magic bytes)
MALICIOUS_SIGNATURES = [
    b'MZ',  # PE executable
    b'\x7fELF',  # ELF executable
    b'!<arch>',  # Unix archive
    b'\xca\xfe\xba\xbe',  # Mach-O executable
]

# Suspicious patterns in filenames
SUSPICIOUS_FILENAME_PATTERNS = [
    r'\.\.|/',  # Directory traversal
    r'\.exe$|\.dll$|\.bat$|\.cmd$|\.sh$|\.ps1$',  # Executables
    r'\.scr$|\.vbs$|\.jar$|\.app$',  # More executables
    r'[<>:"|?*]',  # Invalid filename characters
]


def validate_file(file_content: bytes, filename: str, declared_type: str) -> Tuple[bool, str]:
    """
    Comprehensive file validation
    
    Args:
        file_content: Raw file bytes
        filename: Original filename
        declared_type: File extension declared by uploader
        
    Returns:
        Tuple of (is_safe, reason)
    """
    # 1. Validate filename
    is_safe, reason = validate_filename(filename)
    if not is_safe:
        return False, reason
    
    # 2. Check file size
    is_safe, reason = check_file_size(file_content, declared_type)
    if not is_safe:
        return False, reason
    
    # 3. Verify MIME type matches extension
    is_safe, reason = verify_mime_type(file_content, filename, declared_type)
    if not is_safe:
        return False, reason
    
    # 4. Scan for malicious signatures
    is_safe, reason = scan_malicious_signatures(file_content)
    if not is_safe:
        return False, reason
    
    # 5. PDF-specific checks
    if declared_type == 'pdf':
        is_safe, reason = validate_pdf(file_content)
        if not is_safe:
            return False, reason
    
    # 6. Image-specific checks
    if declared_type in ['png', 'jpg', 'jpeg']:
        is_safe, reason = validate_image(file_content, declared_type)
        if not is_safe:
            return False, reason
    
    return True, "File validation passed"


def validate_filename(filename: str) -> Tuple[bool, str]:
    """Validate filename for security issues"""
    if not filename:
        return False, "Empty filename"
    
    # Check for suspicious patterns
    for pattern in SUSPICIOUS_FILENAME_PATTERNS:
        if re.search(pattern, filename, re.IGNORECASE):
            return False, f"Suspicious filename pattern detected: {filename}"
    
    # Check length
    if len(filename) > 255:
        return False, "Filename too long"
    
    # Ensure ASCII-printable characters only
    if not all(32 <= ord(c) < 127 for c in filename):
        return False, "Filename contains non-ASCII characters"
    
    return True, ""


def check_file_size(file_content: bytes, file_type: str) -> Tuple[bool, str]:
    """Check if file size is within limits"""
    size = len(file_content)
    
    if size == 0:
        return False, "Empty file"
    
    # Get MIME type from extension
    mime_type = None
    for mime, exts in ALLOWED_MIME_TYPES.items():
        if f'.{file_type}' in exts:
            mime_type = mime
            break
    
    if mime_type and mime_type in MAX_FILE_SIZES:
        max_size = MAX_FILE_SIZES[mime_type]
        if size > max_size:
            return False, f"File too large: {size} bytes (max {max_size})"
    
    return True, ""


def verify_mime_type(file_content: bytes, filename: str, declared_type: str) -> Tuple[bool, str]:
    """
    Verify actual MIME type matches declared extension
    Prevents extension spoofing (e.g., malware.exe renamed to malware.pdf)
    """
    try:
        # Use python-magic to detect actual file type
        actual_mime = magic.from_buffer(file_content[:2048], mime=True)
    except Exception as e:
        # Fallback: basic signature check
        actual_mime = detect_mime_basic(file_content)
    
    # Check if actual MIME type is allowed
    if actual_mime not in ALLOWED_MIME_TYPES:
        return False, f"File type not allowed: {actual_mime}"
    
    # Verify extension matches MIME type
    expected_exts = ALLOWED_MIME_TYPES[actual_mime]
    if f'.{declared_type}' not in expected_exts:
        return False, f"Extension mismatch: .{declared_type} file is actually {actual_mime}"
    
    return True, ""


def detect_mime_basic(file_content: bytes) -> str:
    """Basic MIME type detection from file signatures"""
    if file_content.startswith(b'\x89PNG'):
        return 'image/png'
    elif file_content.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    elif file_content.startswith(b'%PDF'):
        return 'application/pdf'
    elif all(32 <= b < 127 or b in [9, 10, 13] for b in file_content[:1024]):
        return 'text/plain'
    else:
        return 'application/octet-stream'


def scan_malicious_signatures(file_content: bytes) -> Tuple[bool, str]:
    """Scan for known malicious file signatures"""
    # Only check file header (first 8 bytes) to avoid false positives
    header = file_content[:8]
    
    for signature in MALICIOUS_SIGNATURES:
        if header.startswith(signature):
            return False, f"Malicious file signature detected: {signature.hex()}"
    
    return True, ""


def validate_pdf(file_content: bytes) -> Tuple[bool, str]:
    """PDF-specific validation"""
    # Check PDF header
    if not file_content.startswith(b'%PDF'):
        return False, "Invalid PDF header"
    
    # Check for JavaScript (common in malicious PDFs)
    if b'/JavaScript' in file_content or b'/JS' in file_content:
        return False, "PDF contains JavaScript (not allowed)"
    
    # Check for auto-execute actions
    if b'/AA' in file_content or b'/OpenAction' in file_content:
        return False, "PDF contains auto-execute actions (not allowed)"
    
    # Check for embedded files
    if b'/EmbeddedFile' in file_content:
        return False, "PDF contains embedded files (not allowed)"
    
    # Check for forms (can be used for exploits)
    if b'/AcroForm' in file_content:
        # Allow forms but log it
        print("[WARNING] PDF contains forms")
    
    return True, ""


def validate_image(file_content: bytes, image_type: str) -> Tuple[bool, str]:
    """Image-specific validation"""
    try:
        from PIL import Image
        import io
        
        # Try to open image
        img = Image.open(io.BytesIO(file_content))
        
        # Verify format matches
        if img.format.lower() != image_type.lower() and not (
            img.format.lower() == 'jpeg' and image_type.lower() in ['jpg', 'jpeg']
        ):
            return False, f"Image format mismatch: {img.format} vs {image_type}"
        
        # Check for reasonable dimensions (prevent decompression bombs)
        width, height = img.size
        if width * height > 178956970:  # ~13000x13000 pixels (same as PIL's default)
            return False, f"Image too large: {width}x{height} pixels"
        
        # Verify image (catches some corrupted/malicious images)
        img.verify()
        
    except Exception as e:
        return False, f"Invalid or corrupted image: {str(e)}"
    
    return True, ""


def calculate_file_hash(file_content: bytes) -> str:
    """Calculate SHA256 hash of file for logging/tracking"""
    return hashlib.sha256(file_content).hexdigest()


def get_file_info(file_content: bytes, filename: str) -> Dict[str, any]:
    """Get comprehensive file information"""
    try:
        mime_type = magic.from_buffer(file_content[:2048], mime=True)
    except:
        mime_type = detect_mime_basic(file_content)
    
    return {
        'filename': filename,
        'size': len(file_content),
        'mime_type': mime_type,
        'sha256': calculate_file_hash(file_content),
    }


# Example usage
if __name__ == "__main__":
    # Test with sample files
    print("File Security Validation Tests")
    print("=" * 50)
    
    # Test filename validation
    test_filenames = [
        ("normal.pdf", True),
        ("../../../etc/passwd", False),
        ("malware.exe", False),
        ("document.pdf.exe", False),
        ("valid-file_name.png", True),
    ]
    
    print("\nFilename Validation:")
    for filename, expected in test_filenames:
        is_safe, reason = validate_filename(filename)
        status = "✅" if is_safe == expected else "❌"
        print(f"{status} {filename}: {reason if not is_safe else 'OK'}")
