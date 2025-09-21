"""File validation service for document uploads."""

import hashlib
import os
from pathlib import Path
from typing import Optional

import magic

from src.core.config import get_settings


class ValidationError(Exception):
    """Custom exception for file validation errors."""
    pass


class DocumentValidationService:
    """
    Service for validating uploaded documents.

    Provides validation for:
    - File size limits
    - File type/MIME type validation
    - Security checks
    - Content validation
    - Malware scanning (basic)
    """

    def __init__(self):
        """Initialize validation service with settings."""
        self.settings = get_settings()
        self.max_upload_size = self.settings.max_upload_size
        self.allowed_extensions = self.settings.allowed_extensions
        self.temp_path = Path(self.settings.temp_path)

        # Ensure temp directory exists
        self.temp_path.mkdir(parents=True, exist_ok=True)

    def validate_file_upload(
        self,
        file_content: bytes,
        filename: str,
        content_type: Optional[str] = None
    ) -> tuple[bool, list[str], dict]:
        """
        Comprehensive file validation.

        Args:
            file_content: File content as bytes
            filename: Original filename
            content_type: Optional MIME content type from upload

        Returns:
            Tuple of (is_valid, errors, metadata)
            - is_valid: True if file passes all validations
            - errors: List of validation error messages
            - metadata: Dictionary with file information

        Raises:
            ValidationError: If critical validation error occurs
        """
        errors = []
        metadata = {
            "original_filename": filename,
            "file_size": len(file_content),
            "content_type_header": content_type,
        }

        try:
            # Basic validations
            size_valid, size_errors = self._validate_file_size(file_content)
            if not size_valid:
                errors.extend(size_errors)

            extension_valid, ext_errors = self._validate_file_extension(filename)
            if not extension_valid:
                errors.extend(ext_errors)

            # MIME type validation
            mime_valid, mime_errors, detected_mime = self._validate_mime_type(
                file_content, filename, content_type
            )
            if not mime_valid:
                errors.extend(mime_errors)
            metadata["detected_mime_type"] = detected_mime

            # Content validation
            content_valid, content_errors = self._validate_file_content(file_content)
            if not content_valid:
                errors.extend(content_errors)

            # Security checks
            security_valid, security_errors = self._validate_file_security(
                file_content, filename
            )
            if not security_valid:
                errors.extend(security_errors)

            # Generate file hash
            file_hash = self._calculate_file_hash(file_content)
            metadata["file_hash"] = file_hash
            metadata["hash_algorithm"] = "sha256"

            # Additional metadata
            metadata["validation_passed"] = len(errors) == 0
            metadata["error_count"] = len(errors)

            return len(errors) == 0, errors, metadata

        except Exception as e:
            raise ValidationError(f"File validation failed: {str(e)}")

    def _validate_file_size(self, file_content: bytes) -> tuple[bool, list[str]]:
        """
        Validate file size against limits.

        Args:
            file_content: File content as bytes

        Returns:
            Tuple of (is_valid, errors)
        """
        errors = []
        file_size = len(file_content)

        if file_size == 0:
            errors.append("File is empty")
        elif file_size > self.max_upload_size:
            max_mb = self.max_upload_size / (1024 * 1024)
            current_mb = file_size / (1024 * 1024)
            errors.append(
                f"File size ({current_mb:.1f}MB) exceeds maximum allowed size ({max_mb:.1f}MB)"
            )

        return len(errors) == 0, errors

    def _validate_file_extension(self, filename: str) -> tuple[bool, list[str]]:
        """
        Validate file extension against allowed extensions.

        Args:
            filename: Original filename

        Returns:
            Tuple of (is_valid, errors)
        """
        errors = []

        if not filename:
            errors.append("Filename is required")
            return False, errors

        # Extract file extension
        file_extension = Path(filename).suffix.lower()

        if not file_extension:
            errors.append("File must have an extension")
        elif file_extension not in self.allowed_extensions:
            allowed_list = ", ".join(self.allowed_extensions)
            errors.append(
                f"File extension '{file_extension}' is not allowed. "
                f"Allowed extensions: {allowed_list}"
            )

        # Check for potentially dangerous filename patterns
        dangerous_patterns = [
            "../", "..\\",  # Directory traversal
            "<%", "%>",     # Script tags
            "<?", "?>",     # PHP tags
        ]

        for pattern in dangerous_patterns:
            if pattern in filename:
                errors.append(f"Filename contains dangerous pattern: {pattern}")

        return len(errors) == 0, errors

    def _validate_mime_type(
        self,
        file_content: bytes,
        filename: str,
        declared_content_type: Optional[str] = None
    ) -> tuple[bool, list[str], Optional[str]]:
        """
        Validate MIME type using content detection.

        Args:
            file_content: File content as bytes
            filename: Original filename
            declared_content_type: MIME type declared in upload

        Returns:
            Tuple of (is_valid, errors, detected_mime_type)
        """
        errors = []
        detected_mime = None

        try:
            # Detect MIME type from content
            detected_mime = magic.from_buffer(file_content, mime=True)

            # Define allowed MIME types for each extension
            allowed_mimes = {
                ".pdf": ["application/pdf"],
                ".doc": ["application/msword"],
                ".docx": [
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                ],
                ".txt": ["text/plain"],
                ".rtf": ["application/rtf", "text/rtf"],
            }

            file_extension = Path(filename).suffix.lower()

            if file_extension in allowed_mimes:
                expected_mimes = allowed_mimes[file_extension]
                if detected_mime not in expected_mimes:
                    errors.append(
                        f"File content type '{detected_mime}' does not match "
                        f"extension '{file_extension}'. Expected: {', '.join(expected_mimes)}"
                    )

            # Check if declared content type matches detected
            if declared_content_type and declared_content_type != detected_mime:
                # Allow some common variations
                variations = {
                    "application/x-pdf": "application/pdf",
                    "text/pdf": "application/pdf",
                }
                normalized_declared = variations.get(declared_content_type, declared_content_type)

                if normalized_declared != detected_mime:
                    errors.append(
                        f"Declared content type '{declared_content_type}' does not match "
                        f"detected content type '{detected_mime}'"
                    )

        except Exception as e:
            errors.append(f"Could not detect file type: {str(e)}")

        return len(errors) == 0, errors, detected_mime

    def _validate_file_content(self, file_content: bytes) -> tuple[bool, list[str]]:
        """
        Validate file content for basic integrity.

        Args:
            file_content: File content as bytes

        Returns:
            Tuple of (is_valid, errors)
        """
        errors = []

        # Check for PDF-specific validation
        if file_content.startswith(b'%PDF-'):
            pdf_valid, pdf_errors = self._validate_pdf_content(file_content)
            if not pdf_valid:
                errors.extend(pdf_errors)

        # Check for minimum content requirements
        if len(file_content) < 100:  # Very small files are suspicious
            errors.append("File content appears to be too small to be valid")

        # Check for binary content in text files
        if b'\x00' in file_content[:1024]:  # Null bytes in first 1KB
            # This is expected for binary files like PDF, but not for text
            pass  # For now, we'll allow binary content

        return len(errors) == 0, errors

    def _validate_pdf_content(self, file_content: bytes) -> tuple[bool, list[str]]:
        """
        Validate PDF-specific content.

        Args:
            file_content: PDF file content as bytes

        Returns:
            Tuple of (is_valid, errors)
        """
        errors = []

        # Check PDF header
        if not file_content.startswith(b'%PDF-'):
            errors.append("Invalid PDF header")
            return False, errors

        # Check for PDF trailer
        if b'%%EOF' not in file_content:
            errors.append("PDF file appears to be incomplete (missing EOF marker)")

        # Check for basic PDF structure
        if b'endobj' not in file_content:
            errors.append("PDF file appears to be corrupted (missing object structures)")

        # Look for potentially malicious content
        suspicious_content = [
            b'/JavaScript',
            b'/JS',
            b'/Launch',
            b'/EmbeddedFile',
            b'/URI',
        ]

        for suspicious in suspicious_content:
            if suspicious in file_content:
                errors.append(f"PDF contains potentially dangerous content: {suspicious.decode('utf-8', errors='ignore')}")

        return len(errors) == 0, errors

    def _validate_file_security(
        self,
        file_content: bytes,
        filename: str
    ) -> tuple[bool, list[str]]:
        """
        Perform basic security validation.

        Args:
            file_content: File content as bytes
            filename: Original filename

        Returns:
            Tuple of (is_valid, errors)
        """
        errors = []

        # Check for executable file patterns
        executable_signatures = [
            b'MZ',      # Windows PE
            b'\x7fELF', # Linux ELF
            b'\xca\xfe\xba\xbe',  # Java class file
            b'PK\x03\x04',  # ZIP (could contain executables)
        ]

        for signature in executable_signatures:
            if file_content.startswith(signature):
                if signature == b'PK\x03\x04':
                    # ZIP files could be legitimate documents (docx, etc.)
                    if not filename.lower().endswith(('.docx', '.xlsx', '.pptx')):
                        errors.append("ZIP archives are not allowed unless they are Office documents")
                else:
                    errors.append("Executable files are not allowed")

        # Check for script content in text files
        script_patterns = [
            b'<script',
            b'javascript:',
            b'vbscript:',
            b'<?php',
            b'<%',
            b'eval(',
            b'exec(',
        ]

        for pattern in script_patterns:
            if pattern.lower() in file_content.lower()[:5000]:  # Check first 5KB
                errors.append("File contains potentially dangerous script content")
                break

        # Check for file bombs (highly compressed content)
        compression_ratio = self._estimate_compression_ratio(file_content)
        if compression_ratio > 1000:  # Very high compression ratio
            errors.append("File appears to be a compression bomb")

        return len(errors) == 0, errors

    def _estimate_compression_ratio(self, file_content: bytes) -> float:
        """
        Estimate compression ratio to detect potential zip bombs.

        Args:
            file_content: File content as bytes

        Returns:
            Estimated compression ratio
        """
        try:
            import zlib
            compressed = zlib.compress(file_content, level=9)
            return len(file_content) / len(compressed)
        except Exception:
            return 1.0  # No compression detected

    def _calculate_file_hash(self, file_content: bytes, algorithm: str = "sha256") -> str:
        """
        Calculate hash of file content.

        Args:
            file_content: File content as bytes
            algorithm: Hash algorithm to use

        Returns:
            Hexadecimal hash string

        Raises:
            ValidationError: If hash calculation fails
        """
        try:
            if algorithm == "sha256":
                hasher = hashlib.sha256()
            elif algorithm == "md5":
                hasher = hashlib.md5()
            elif algorithm == "sha1":
                hasher = hashlib.sha1()
            else:
                raise ValidationError(f"Unsupported hash algorithm: {algorithm}")

            hasher.update(file_content)
            return hasher.hexdigest()

        except Exception as e:
            raise ValidationError(f"Hash calculation failed: {str(e)}")

    def check_duplicate_by_hash(self, file_hash: str) -> bool:
        """
        Check if file with same hash already exists.

        Args:
            file_hash: File hash to check

        Returns:
            True if duplicate exists, False otherwise

        Note:
            This is a placeholder. In production, you would check against
            your database of existing file hashes.
        """
        # Placeholder implementation
        # In real implementation, check against database
        return False

    def sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename for safe storage.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename safe for filesystem storage
        """
        import re

        # Remove any path separators
        filename = os.path.basename(filename)

        # Replace dangerous characters
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)

        # Remove leading/trailing spaces and dots
        filename = filename.strip(' .')

        # Ensure filename is not empty
        if not filename:
            filename = "unnamed_file"

        # Limit filename length
        max_length = 255
        if len(filename) > max_length:
            name, ext = os.path.splitext(filename)
            filename = name[:max_length - len(ext)] + ext

        return filename

    def get_safe_filename(self, original_filename: str, file_hash: str) -> str:
        """
        Generate a safe filename for storage.

        Args:
            original_filename: Original uploaded filename
            file_hash: File content hash

        Returns:
            Safe filename for storage
        """
        # Sanitize original filename
        safe_name = self.sanitize_filename(original_filename)

        # Extract extension
        _, ext = os.path.splitext(safe_name)

        # Create new filename with hash prefix
        timestamp = int(os.urandom(4).hex(), 16)  # Random component
        safe_filename = f"{file_hash[:16]}_{timestamp}{ext}"

        return safe_filename
