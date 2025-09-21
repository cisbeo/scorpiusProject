"""Password hashing service for secure password management."""

import secrets
from typing import Optional

import bcrypt

from src.core.config import get_settings


class PasswordService:
    """
    Service for handling password operations.

    Provides methods for:
    - Secure password hashing using bcrypt
    - Password verification
    - Password strength validation
    - Secure password generation
    """

    def __init__(self):
        """Initialize password service with settings."""
        self.settings = get_settings()
        self.bcrypt_rounds = self.settings.bcrypt_rounds

    def hash_password(self, password: str) -> str:
        """
        Hash a password using bcrypt.

        Args:
            password: Plain text password to hash

        Returns:
            Hashed password as string

        Raises:
            ValueError: If password is empty or hashing fails
        """
        if not password or not password.strip():
            raise ValueError("Password cannot be empty")

        try:
            # Generate salt and hash password
            salt = bcrypt.gensalt(rounds=self.bcrypt_rounds)
            password_bytes = password.encode('utf-8')
            hashed = bcrypt.hashpw(password_bytes, salt)
            return hashed.decode('utf-8')

        except Exception as e:
            raise ValueError(f"Failed to hash password: {str(e)}")

    def verify_password(self, password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash.

        Args:
            password: Plain text password to verify
            hashed_password: Hashed password to verify against

        Returns:
            True if password matches hash, False otherwise

        Raises:
            ValueError: If password or hash is invalid
        """
        if not password or not hashed_password:
            return False

        try:
            password_bytes = password.encode('utf-8')
            hashed_bytes = hashed_password.encode('utf-8')
            return bcrypt.checkpw(password_bytes, hashed_bytes)

        except Exception:
            # If any error occurs during verification, return False
            return False

    def validate_password_strength(
        self,
        password: str,
        min_length: int = 8,
        require_uppercase: bool = True,
        require_lowercase: bool = True,
        require_digit: bool = True,
        require_special: bool = True,
        min_unique_chars: int = 4
    ) -> tuple[bool, list[str]]:
        """
        Validate password strength according to security requirements.

        Args:
            password: Password to validate
            min_length: Minimum password length
            require_uppercase: Require at least one uppercase letter
            require_lowercase: Require at least one lowercase letter
            require_digit: Require at least one digit
            require_special: Require at least one special character
            min_unique_chars: Minimum number of unique characters

        Returns:
            Tuple of (is_valid, list_of_validation_errors)
        """
        errors = []

        if not password:
            errors.append("Password is required")
            return False, errors

        # Check minimum length
        if len(password) < min_length:
            errors.append(f"Password must be at least {min_length} characters long")

        # Check uppercase requirement
        if require_uppercase and not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")

        # Check lowercase requirement
        if require_lowercase and not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter")

        # Check digit requirement
        if require_digit and not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one digit")

        # Check special character requirement
        if require_special:
            special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
            if not any(c in special_chars for c in password):
                errors.append("Password must contain at least one special character")

        # Check unique characters
        if len(set(password)) < min_unique_chars:
            errors.append(f"Password must contain at least {min_unique_chars} unique characters")

        # Check for common weak patterns
        weak_patterns = [
            "password", "123456", "qwerty", "admin", "user",
            "12345678", "abc123", "password123"
        ]
        if password.lower() in weak_patterns:
            errors.append("Password is too common and easily guessable")

        # Check for sequential characters
        if self._has_sequential_chars(password):
            errors.append("Password should not contain sequential characters")

        # Check for repeated characters
        if self._has_repeated_chars(password):
            errors.append("Password should not have too many repeated characters")

        return len(errors) == 0, errors

    def _has_sequential_chars(self, password: str, max_sequential: int = 3) -> bool:
        """
        Check if password has sequential characters.

        Args:
            password: Password to check
            max_sequential: Maximum allowed sequential characters

        Returns:
            True if password has too many sequential characters
        """
        for i in range(len(password) - max_sequential + 1):
            # Check for ascending sequence
            if all(ord(password[j]) == ord(password[j-1]) + 1 for j in range(i+1, i+max_sequential)):
                return True
            # Check for descending sequence
            if all(ord(password[j]) == ord(password[j-1]) - 1 for j in range(i+1, i+max_sequential)):
                return True
        return False

    def _has_repeated_chars(self, password: str, max_repeats: int = 3) -> bool:
        """
        Check if password has too many repeated characters.

        Args:
            password: Password to check
            max_repeats: Maximum allowed repeated characters

        Returns:
            True if password has too many repeated characters
        """
        for i in range(len(password) - max_repeats + 1):
            if all(password[j] == password[i] for j in range(i, i + max_repeats)):
                return True
        return False

    def generate_secure_password(
        self,
        length: int = 16,
        include_uppercase: bool = True,
        include_lowercase: bool = True,
        include_digits: bool = True,
        include_special: bool = True,
        exclude_ambiguous: bool = True
    ) -> str:
        """
        Generate a cryptographically secure random password.

        Args:
            length: Password length
            include_uppercase: Include uppercase letters
            include_lowercase: Include lowercase letters
            include_digits: Include digits
            include_special: Include special characters
            exclude_ambiguous: Exclude ambiguous characters (0, O, l, 1, etc.)

        Returns:
            Generated secure password

        Raises:
            ValueError: If no character sets are selected or length is too short
        """
        if length < 4:
            raise ValueError("Password length must be at least 4 characters")

        # Define character sets
        uppercase = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        lowercase = "abcdefghijklmnopqrstuvwxyz"
        digits = "0123456789"
        special = "!@#$%^&*()_+-=[]{}|;:,.<>?"

        # Remove ambiguous characters if requested
        if exclude_ambiguous:
            uppercase = uppercase.replace("O", "").replace("I", "")
            lowercase = lowercase.replace("l", "").replace("o", "")
            digits = digits.replace("0", "").replace("1", "")

        # Build character pool
        char_pool = ""
        required_chars = []

        if include_uppercase:
            char_pool += uppercase
            required_chars.append(secrets.choice(uppercase))
        if include_lowercase:
            char_pool += lowercase
            required_chars.append(secrets.choice(lowercase))
        if include_digits:
            char_pool += digits
            required_chars.append(secrets.choice(digits))
        if include_special:
            char_pool += special
            required_chars.append(secrets.choice(special))

        if not char_pool:
            raise ValueError("At least one character set must be enabled")

        # Generate remaining characters
        remaining_length = length - len(required_chars)
        random_chars = [secrets.choice(char_pool) for _ in range(remaining_length)]

        # Combine and shuffle
        all_chars = required_chars + random_chars
        password_list = list(all_chars)

        # Shuffle the password to avoid predictable patterns
        for i in range(len(password_list)):
            j = secrets.randbelow(len(password_list))
            password_list[i], password_list[j] = password_list[j], password_list[i]

        return ''.join(password_list)

    def generate_password_hash_for_new_user(
        self,
        password: Optional[str] = None,
        validate_strength: bool = True
    ) -> tuple[str, str]:
        """
        Generate a password and its hash for a new user.

        Args:
            password: Optional password to use (if None, generates secure password)
            validate_strength: Whether to validate password strength

        Returns:
            Tuple of (plain_password, hashed_password)

        Raises:
            ValueError: If password validation fails
        """
        if password is None:
            password = self.generate_secure_password()

        if validate_strength:
            is_valid, errors = self.validate_password_strength(password)
            if not is_valid:
                raise ValueError(f"Password validation failed: {'; '.join(errors)}")

        hashed_password = self.hash_password(password)
        return password, hashed_password

    def is_password_compromised(self, password: str) -> bool:
        """
        Check if password appears in common breach databases.

        Note: This is a placeholder for future implementation.
        In production, you might want to integrate with services like
        HaveIBeenPwned API or maintain a local database of compromised passwords.

        Args:
            password: Password to check

        Returns:
            True if password is known to be compromised, False otherwise
        """
        # Basic check against most common compromised passwords
        common_breached = {
            "password", "123456", "password123", "admin", "qwerty",
            "12345678", "123456789", "letmein", "1234567890",
            "football", "iloveyou", "admin123", "welcome", "monkey"
        }

        return password.lower() in common_breached

    def get_password_strength_score(self, password: str) -> int:
        """
        Calculate a password strength score from 0-100.

        Args:
            password: Password to score

        Returns:
            Score from 0 (very weak) to 100 (very strong)
        """
        if not password:
            return 0

        score = 0

        # Length bonus (up to 25 points)
        score += min(len(password) * 2, 25)

        # Character variety bonus (up to 40 points)
        if any(c.isupper() for c in password):
            score += 10
        if any(c.islower() for c in password):
            score += 10
        if any(c.isdigit() for c in password):
            score += 10
        if any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            score += 10

        # Unique characters bonus (up to 20 points)
        unique_ratio = len(set(password)) / len(password)
        score += int(unique_ratio * 20)

        # Pattern penalties
        if self._has_sequential_chars(password):
            score -= 10
        if self._has_repeated_chars(password):
            score -= 10
        if self.is_password_compromised(password):
            score -= 20

        # Ensure score is within bounds
        return max(0, min(100, score))
