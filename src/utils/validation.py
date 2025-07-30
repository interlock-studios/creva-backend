import json
import jsonschema
import re
import structlog
from typing import Dict, Any, Tuple, List
from urllib.parse import urlparse
from src.models.workout import WORKOUT_JSON_SCHEMA
from src.models.parser_result import TikTokParseResult

logger = structlog.get_logger()


class ValidationError(Exception):
    def __init__(self, message: str, errors: list = None):
        self.message = message
        self.errors = errors or []
        super().__init__(self.message)


def validate_workout_json(workout_data: Dict[str, Any]) -> Tuple[bool, list]:
    try:
        jsonschema.validate(workout_data, WORKOUT_JSON_SCHEMA)
        return True, []
    except jsonschema.ValidationError as e:
        return False, [str(e)]
    except Exception as e:
        return False, [f"Validation error: {str(e)}"]


def validate_tiktok_url(url: str) -> bool:
    """
    Validate TikTok URL format
    
    Supports various TikTok URL formats:
    - https://www.tiktok.com/@user/video/123456789
    - https://vm.tiktok.com/ABCD123/
    - https://tiktok.com/@user/video/123456789
    """
    if not isinstance(url, str) or not url.strip():
        return False
    
    try:
        parsed = urlparse(url.strip())
        
        # Check domain
        valid_domains = [
            'tiktok.com',
            'www.tiktok.com', 
            'vm.tiktok.com',
            'm.tiktok.com'
        ]
        
        if parsed.netloc.lower() not in valid_domains:
            return False
        
        # Check URL structure
        if parsed.netloc == 'vm.tiktok.com':
            # Short URL format: vm.tiktok.com/XXXXX/
            return bool(re.match(r'^/\w+/?$', parsed.path))
        else:
            # Full URL format: tiktok.com/@user/video/123456789
            return bool(re.match(r'^/@[\w.-]+/video/\d+', parsed.path))
        
    except Exception as e:
        logger.warning("URL validation error", url=url, error=str(e))
        return False


def sanitize_text_content(text: str, max_length: int = 10000) -> str:
    """
    Sanitize text content for safe storage and display
    
    Args:
        text: Raw text content
        max_length: Maximum allowed length
        
    Returns:
        Sanitized text
    """
    if not isinstance(text, str):
        return ""
    
    # Remove control characters except newlines and tabs
    sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
    
    # Normalize whitespace
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    
    # Truncate if too long
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rsplit(' ', 1)[0] + '...'
    
    return sanitized


def sanitize_workout_data(workout_data: Dict[str, Any]) -> Dict[str, Any]:
    sanitized = {}
    
    if "title" in workout_data:
        sanitized["title"] = str(workout_data["title"]).strip()[:200]
    
    if "description" in workout_data:
        desc = workout_data["description"]
        sanitized["description"] = str(desc).strip()[:1000] if desc else None
    
    if "workout_type" in workout_data:
        sanitized["workout_type"] = str(workout_data["workout_type"]).lower()
    
    if "duration_minutes" in workout_data:
        try:
            sanitized["duration_minutes"] = max(1, min(480, int(workout_data["duration_minutes"])))
        except (ValueError, TypeError):
            sanitized["duration_minutes"] = None
    
    if "difficulty_level" in workout_data:
        try:
            sanitized["difficulty_level"] = max(1, min(10, int(workout_data["difficulty_level"])))
        except (ValueError, TypeError):
            sanitized["difficulty_level"] = 5
    
    if "exercises" in workout_data and isinstance(workout_data["exercises"], list):
        sanitized["exercises"] = []
        for exercise in workout_data["exercises"][:50]:  # Max 50 exercises
            if isinstance(exercise, dict):
                sanitized_exercise = sanitize_exercise(exercise)
                if sanitized_exercise:
                    sanitized["exercises"].append(sanitized_exercise)
    
    if "tags" in workout_data:
        tags = workout_data["tags"]
        if isinstance(tags, list):
            sanitized["tags"] = [str(tag).strip()[:50] for tag in tags[:20]]
        else:
            sanitized["tags"] = None
    
    if "creator" in workout_data:
        creator = workout_data["creator"]
        sanitized["creator"] = str(creator).strip()[:100] if creator else None
    
    return sanitized


def sanitize_exercise(exercise_data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(exercise_data, dict):
        return None
    
    sanitized = {}
    
    if "name" in exercise_data:
        sanitized["name"] = str(exercise_data["name"]).strip()[:200]
    else:
        return None
    
    if "muscle_groups" in exercise_data and isinstance(exercise_data["muscle_groups"], list):
        valid_groups = [
            "chest", "back", "shoulders", "biceps", "triceps",
            "legs", "glutes", "core", "full_body"
        ]
        sanitized["muscle_groups"] = [
            group for group in exercise_data["muscle_groups"][:10]
            if str(group).lower() in valid_groups
        ]
        if not sanitized["muscle_groups"]:
            sanitized["muscle_groups"] = ["full_body"]
    else:
        sanitized["muscle_groups"] = ["full_body"]
    
    if "equipment" in exercise_data:
        valid_equipment = [
            "none", "dumbbells", "barbell", "resistance_bands",
            "kettlebell", "machine", "bodyweight", "other"
        ]
        equipment = str(exercise_data["equipment"]).lower()
        sanitized["equipment"] = equipment if equipment in valid_equipment else "none"
    else:
        sanitized["equipment"] = "none"
    
    if "sets" in exercise_data and isinstance(exercise_data["sets"], list):
        sanitized["sets"] = []
        for set_data in exercise_data["sets"][:50]:  # Max 50 sets
            if isinstance(set_data, dict):
                sanitized_set = sanitize_set(set_data)
                if sanitized_set:
                    sanitized["sets"].append(sanitized_set)
        if not sanitized["sets"]:
            sanitized["sets"] = [{"reps": 10}]
    else:
        sanitized["sets"] = [{"reps": 10}]
    
    if "instructions" in exercise_data:
        instructions = exercise_data["instructions"]
        sanitized["instructions"] = str(instructions).strip()[:1000] if instructions else None
    
    return sanitized


def sanitize_set(set_data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(set_data, dict):
        return None
    
    sanitized = {}
    
    for field in ["reps", "duration_seconds", "rest_seconds"]:
        if field in set_data:
            try:
                value = int(set_data[field])
                if field == "reps" and value > 0:
                    sanitized[field] = min(1000, value)
                elif field in ["duration_seconds", "rest_seconds"] and value >= 0:
                    max_val = 7200 if field == "duration_seconds" else 3600
                    sanitized[field] = min(max_val, value)
            except (ValueError, TypeError):
                pass
    
    for field in ["weight_lbs", "distance_miles"]:
        if field in set_data:
            try:
                value = float(set_data[field])
                if value >= 0:
                    max_val = 10000 if field == "weight_lbs" else 1000
                    sanitized[field] = min(max_val, value)
            except (ValueError, TypeError):
                pass
    
    return sanitized if sanitized else {"reps": 10}