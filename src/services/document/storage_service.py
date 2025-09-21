"""Document storage service for secure file management."""

import os
import shutil
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

from src.core.config import get_settings


class StorageError(Exception):
    """Custom exception for storage operations."""
    pass


class DocumentStorageService:
    """
    Service for secure document storage and retrieval.

    Provides methods for:
    - Secure file storage with encryption paths
    - File retrieval and verification
    - Storage cleanup and management
    - Path generation and validation
    """

    def __init__(self):
        """Initialize storage service with settings."""
        self.settings = get_settings()
        self.upload_path = Path(self.settings.upload_path)
        self.temp_path = Path(self.settings.temp_path)

        # Ensure directories exist
        self.upload_path.mkdir(parents=True, exist_ok=True)
        self.temp_path.mkdir(parents=True, exist_ok=True)

        # Set proper permissions (readable/writable by owner only)
        self._set_secure_permissions()

    def store_document(
        self,
        file_content: bytes,
        original_filename: str,
        file_hash: str,
        user_id: UUID,
        tenant_id: Optional[UUID] = None
    ) -> tuple[str, str]:
        """
        Store document securely on filesystem.

        Args:
            file_content: Binary content of the document
            original_filename: Original filename from upload
            file_hash: SHA-256 hash of the file content
            user_id: UUID of the user uploading the file
            tenant_id: Optional tenant ID for multi-tenancy

        Returns:
            Tuple of (storage_path, relative_path)
            - storage_path: Absolute path where file is stored
            - relative_path: Relative path for database storage

        Raises:
            StorageError: If storage operation fails
        """
        try:
            # Generate secure storage path
            relative_path = self._generate_storage_path(
                original_filename, file_hash, user_id, tenant_id
            )
            storage_path = self.upload_path / relative_path

            # Ensure parent directory exists
            storage_path.parent.mkdir(parents=True, exist_ok=True)

            # Check if file already exists (duplicate check)
            if storage_path.exists():
                # Verify it's the same content
                existing_content = storage_path.read_bytes()
                if len(existing_content) == len(file_content):
                    # File already exists with same size, assume it's the same
                    return str(storage_path), str(relative_path)
                else:
                    # Size mismatch, generate new path with timestamp
                    relative_path = self._generate_storage_path(
                        original_filename, file_hash, user_id, tenant_id,
                        suffix=str(uuid4())[:8]
                    )
                    storage_path = self.upload_path / relative_path
                    storage_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file atomically (write to temp file, then move)
            temp_path = self.temp_path / f"upload_{uuid4()}.tmp"
            try:
                # Write to temporary file
                temp_path.write_bytes(file_content)

                # Set secure permissions on temp file
                temp_path.chmod(0o600)

                # Move to final location
                shutil.move(str(temp_path), str(storage_path))

                # Set secure permissions on final file
                storage_path.chmod(0o600)

                return str(storage_path), str(relative_path)

            finally:
                # Clean up temp file if it still exists
                if temp_path.exists():
                    temp_path.unlink()

        except Exception as e:
            raise StorageError(f"Failed to store document: {str(e)}")

    def retrieve_document(self, relative_path: str) -> bytes:
        """
        Retrieve document content from storage.

        Args:
            relative_path: Relative path to the stored document

        Returns:
            Binary content of the document

        Raises:
            StorageError: If retrieval fails or file not found
        """
        try:
            # Validate path for security
            if not self._is_safe_path(relative_path):
                raise StorageError("Invalid file path")

            storage_path = self.upload_path / relative_path

            if not storage_path.exists():
                raise StorageError("Document not found")

            if not storage_path.is_file():
                raise StorageError("Path is not a file")

            # Check if file is within allowed storage area
            if not self._is_within_storage_area(storage_path):
                raise StorageError("File is outside allowed storage area")

            return storage_path.read_bytes()

        except StorageError:
            # Re-raise storage errors as-is
            raise
        except Exception as e:
            raise StorageError(f"Failed to retrieve document: {str(e)}")

    def document_exists(self, relative_path: str) -> bool:
        """
        Check if document exists in storage.

        Args:
            relative_path: Relative path to check

        Returns:
            True if document exists, False otherwise
        """
        try:
            if not self._is_safe_path(relative_path):
                return False

            storage_path = self.upload_path / relative_path
            return storage_path.exists() and storage_path.is_file()

        except Exception:
            return False

    def get_document_size(self, relative_path: str) -> Optional[int]:
        """
        Get size of stored document.

        Args:
            relative_path: Relative path to the document

        Returns:
            File size in bytes, or None if file doesn't exist
        """
        try:
            if not self._is_safe_path(relative_path):
                return None

            storage_path = self.upload_path / relative_path
            if storage_path.exists() and storage_path.is_file():
                return storage_path.stat().st_size
            return None

        except Exception:
            return None

    def delete_document(self, relative_path: str) -> bool:
        """
        Delete document from storage.

        Args:
            relative_path: Relative path to the document

        Returns:
            True if document was deleted, False if not found

        Raises:
            StorageError: If deletion fails
        """
        try:
            if not self._is_safe_path(relative_path):
                raise StorageError("Invalid file path")

            storage_path = self.upload_path / relative_path

            if not storage_path.exists():
                return False

            if not storage_path.is_file():
                raise StorageError("Path is not a file")

            # Check if file is within allowed storage area
            if not self._is_within_storage_area(storage_path):
                raise StorageError("File is outside allowed storage area")

            # Securely delete file
            storage_path.unlink()

            # Try to remove empty parent directories
            self._cleanup_empty_directories(storage_path.parent)

            return True

        except StorageError:
            # Re-raise storage errors as-is
            raise
        except Exception as e:
            raise StorageError(f"Failed to delete document: {str(e)}")

    def move_document(
        self,
        old_relative_path: str,
        new_relative_path: str
    ) -> bool:
        """
        Move document to new location.

        Args:
            old_relative_path: Current relative path
            new_relative_path: New relative path

        Returns:
            True if document was moved successfully

        Raises:
            StorageError: If move operation fails
        """
        try:
            if not self._is_safe_path(old_relative_path) or not self._is_safe_path(new_relative_path):
                raise StorageError("Invalid file path")

            old_storage_path = self.upload_path / old_relative_path
            new_storage_path = self.upload_path / new_relative_path

            if not old_storage_path.exists():
                return False

            # Ensure new parent directory exists
            new_storage_path.parent.mkdir(parents=True, exist_ok=True)

            # Move file
            shutil.move(str(old_storage_path), str(new_storage_path))

            # Set secure permissions
            new_storage_path.chmod(0o600)

            # Cleanup old directory if empty
            self._cleanup_empty_directories(old_storage_path.parent)

            return True

        except Exception as e:
            raise StorageError(f"Failed to move document: {str(e)}")

    def get_storage_info(self) -> dict:
        """
        Get storage system information.

        Returns:
            Dictionary with storage information
        """
        try:
            upload_stat = self.upload_path.stat()
            temp_stat = self.temp_path.stat()

            return {
                "upload_path": str(self.upload_path),
                "temp_path": str(self.temp_path),
                "upload_path_exists": self.upload_path.exists(),
                "temp_path_exists": self.temp_path.exists(),
                "upload_path_writable": os.access(self.upload_path, os.W_OK),
                "temp_path_writable": os.access(self.temp_path, os.W_OK),
                "upload_permissions": oct(upload_stat.st_mode)[-3:],
                "temp_permissions": oct(temp_stat.st_mode)[-3:],
            }
        except Exception as e:
            return {"error": str(e)}

    def cleanup_temp_files(self, max_age_hours: int = 24) -> int:
        """
        Clean up old temporary files.

        Args:
            max_age_hours: Maximum age for temp files in hours

        Returns:
            Number of files cleaned up
        """
        import time

        cleaned_count = 0
        max_age_seconds = max_age_hours * 3600
        current_time = time.time()

        try:
            for temp_file in self.temp_path.glob("*"):
                if temp_file.is_file():
                    file_age = current_time - temp_file.stat().st_mtime
                    if file_age > max_age_seconds:
                        try:
                            temp_file.unlink()
                            cleaned_count += 1
                        except Exception:
                            # Continue cleaning other files if one fails
                            pass

        except Exception:
            # If cleanup fails, return what we managed to clean
            pass

        return cleaned_count

    def _generate_storage_path(
        self,
        original_filename: str,
        file_hash: str,
        user_id: UUID,
        tenant_id: Optional[UUID] = None,
        suffix: Optional[str] = None
    ) -> str:
        """
        Generate secure storage path for file.

        Args:
            original_filename: Original filename
            file_hash: File content hash
            user_id: User UUID
            tenant_id: Optional tenant UUID
            suffix: Optional suffix for uniqueness

        Returns:
            Relative storage path
        """
        from pathlib import Path

        # Extract file extension
        ext = Path(original_filename).suffix.lower()

        # Create directory structure: tenant/user/year/month
        from datetime import datetime
        now = datetime.utcnow()
        year = now.strftime("%Y")
        month = now.strftime("%m")

        # Build path components
        path_parts = []

        if tenant_id:
            path_parts.append(f"tenant_{str(tenant_id)[:8]}")
        else:
            path_parts.append("default")

        path_parts.extend([
            f"user_{str(user_id)[:8]}",
            year,
            month
        ])

        # Create filename: hash_prefix + suffix + extension
        filename_parts = [file_hash[:16]]
        if suffix:
            filename_parts.append(suffix)
        filename = "_".join(filename_parts) + ext

        # Combine path
        return str(Path(*path_parts) / filename)

    def _is_safe_path(self, path: str) -> bool:
        """
        Check if path is safe (no directory traversal).

        Args:
            path: Path to validate

        Returns:
            True if path is safe
        """
        # Check for directory traversal patterns
        dangerous_patterns = ['..', '~', '//', '\\\\', '<', '>', '|', '*', '?']
        for pattern in dangerous_patterns:
            if pattern in path:
                return False

        # Check if path is relative and doesn't start with /
        if os.path.isabs(path):
            return False

        return True

    def _is_within_storage_area(self, storage_path: Path) -> bool:
        """
        Check if path is within allowed storage area.

        Args:
            storage_path: Absolute storage path

        Returns:
            True if path is within storage area
        """
        try:
            # Resolve paths to handle symlinks
            resolved_storage = storage_path.resolve()
            resolved_upload = self.upload_path.resolve()

            # Check if storage path is under upload path
            return str(resolved_storage).startswith(str(resolved_upload))

        except Exception:
            return False

    def _set_secure_permissions(self) -> None:
        """Set secure permissions on storage directories."""
        try:
            # Set directory permissions (read/write/execute for owner only)
            self.upload_path.chmod(0o700)
            self.temp_path.chmod(0o700)
        except Exception:
            # If permission setting fails, continue (might be running in restricted environment)
            pass

    def _cleanup_empty_directories(self, directory: Path) -> None:
        """
        Remove empty parent directories up to upload root.

        Args:
            directory: Directory to start cleanup from
        """
        try:
            # Don't remove the root upload directory
            if directory == self.upload_path:
                return

            # Only remove if directory is empty
            if directory.exists() and directory.is_dir():
                try:
                    # Try to remove directory (will fail if not empty)
                    directory.rmdir()
                    # Recursively try parent
                    self._cleanup_empty_directories(directory.parent)
                except OSError:
                    # Directory not empty or other error, stop cleanup
                    pass

        except Exception:
            # If cleanup fails, it's not critical
            pass
