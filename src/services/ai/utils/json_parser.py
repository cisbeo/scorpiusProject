"""Robust JSON parser for handling Mistral AI responses."""

import json
import re
import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class RobustJSONParser:
    """Parser for handling potentially malformed JSON from LLM responses."""

    @staticmethod
    def clean_json_string(text: str) -> str:
        """
        Clean common JSON formatting issues from LLM responses.

        Args:
            text: Raw text that might contain JSON

        Returns:
            Cleaned JSON string
        """
        # Remove markdown code blocks
        if "```json" in text:
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*$', '', text)
        elif "```" in text:
            text = re.sub(r'```\s*', '', text)

        # Remove any leading/trailing whitespace
        text = text.strip()

        # Fix common JSON issues
        # Remove trailing commas
        text = re.sub(r',\s*}', '}', text)
        text = re.sub(r',\s*]', ']', text)

        # Fix boolean values
        text = re.sub(r'\btrue\b', 'true', text, flags=re.IGNORECASE)
        text = re.sub(r'\bfalse\b', 'false', text, flags=re.IGNORECASE)
        text = re.sub(r'\bnull\b', 'null', text, flags=re.IGNORECASE)

        return text

    @staticmethod
    def extract_json_object(text: str) -> Optional[str]:
        """
        Extract the first valid JSON object from text.

        Args:
            text: Text containing JSON

        Returns:
            Extracted JSON string or None
        """
        # Find JSON object boundaries
        start_idx = text.find('{')
        if start_idx == -1:
            return None

        # Track bracket depth to find matching closing bracket
        depth = 0
        in_string = False
        escape_next = False

        for i in range(start_idx, len(text)):
            char = text[i]

            if escape_next:
                escape_next = False
                continue

            if char == '\\':
                escape_next = True
                continue

            if char == '"' and not escape_next:
                in_string = not in_string
                continue

            if not in_string:
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        return text[start_idx:i+1]

        # If we didn't find a complete object, try to close it
        if depth > 0:
            # Add missing closing brackets
            missing_brackets = '}' * depth
            return text[start_idx:] + missing_brackets

        return None

    @staticmethod
    def fix_truncated_string(json_str: str) -> str:
        """
        Fix truncated string values in JSON.

        Args:
            json_str: JSON string that might have truncated values

        Returns:
            Fixed JSON string
        """
        # Find the last string that might be truncated
        # Look for patterns like "key": "value that is not closed
        pattern = r'"[^"]*":\s*"[^"]*$'
        match = re.search(pattern, json_str)

        if match:
            # Add closing quote and any necessary brackets
            json_str = json_str + '"'

            # Count open brackets after the truncated string
            remaining = json_str[match.start():]
            open_brackets = remaining.count('[') - remaining.count(']')
            open_braces = remaining.count('{') - remaining.count('}')

            # Close any open arrays/objects
            json_str += ']' * open_brackets
            json_str += '}' * open_braces

        return json_str

    @classmethod
    def parse(
        cls,
        text: str,
        fallback_default: Optional[Dict[str, Any]] = None
    ) -> Tuple[Dict[str, Any], bool]:
        """
        Parse potentially malformed JSON with multiple fallback strategies.

        Args:
            text: Text to parse
            fallback_default: Default value if parsing fails

        Returns:
            Tuple of (parsed_data, success_flag)
        """
        if not text:
            return fallback_default or {}, False

        # Strategy 1: Try direct parsing
        try:
            return json.loads(text), True
        except json.JSONDecodeError:
            pass

        # Strategy 2: Clean and try again
        try:
            cleaned = cls.clean_json_string(text)
            return json.loads(cleaned), True
        except json.JSONDecodeError:
            pass

        # Strategy 3: Extract JSON object
        try:
            json_str = cls.extract_json_object(text)
            if json_str:
                return json.loads(json_str), True
        except json.JSONDecodeError:
            pass

        # Strategy 4: Fix truncated strings
        try:
            json_str = cls.extract_json_object(text)
            if json_str:
                fixed = cls.fix_truncated_string(json_str)
                return json.loads(fixed), True
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parsing failed after all strategies: {e}")

        # Strategy 5: Try to extract partial data
        try:
            # Look for requirements array even if overall structure is broken
            req_pattern = r'"requirements"\s*:\s*\[(.*?)\]'
            match = re.search(req_pattern, text, re.DOTALL)
            if match:
                # Try to parse just the requirements array
                req_text = '[' + match.group(1) + ']'
                requirements = json.loads(req_text)

                return {
                    "requirements": requirements,
                    "metadata": {
                        "extraction_notes": "Partial extraction due to JSON parsing issues"
                    },
                    "confidence_avg": 0.6,
                    "document_type": "unknown"
                }, True
        except:
            pass

        # Return fallback
        return fallback_default or {
            "requirements": [],
            "metadata": {
                "extraction_notes": "Failed to parse AI response"
            },
            "confidence_avg": 0.0,
            "document_type": "unknown"
        }, False

    @classmethod
    def validate_requirements_response(cls, data: Dict[str, Any]) -> bool:
        """
        Validate that the parsed data has the expected structure.

        Args:
            data: Parsed JSON data

        Returns:
            True if valid, False otherwise
        """
        if not isinstance(data, dict):
            return False

        if "requirements" not in data:
            return False

        if not isinstance(data["requirements"], list):
            return False

        # Check that requirements have minimum required fields
        for req in data["requirements"]:
            if not isinstance(req, dict):
                return False
            required_fields = ["category", "description", "importance", "is_mandatory"]
            if not all(field in req for field in required_fields):
                return False

        return True