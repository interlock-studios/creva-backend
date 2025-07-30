from typing import List, Optional, Union, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum
import json


class WorkoutType(str, Enum):
    STRENGTH = "strength"
    CARDIO = "cardio"
    HIIT = "hiit"
    YOGA = "yoga"
    STRETCHING = "stretching"
    BODYWEIGHT = "bodyweight"
    MIXED = "mixed"


class Equipment(str, Enum):
    NONE = "none"
    DUMBBELLS = "dumbbells"
    BARBELL = "barbell"
    RESISTANCE_BANDS = "resistance_bands"
    KETTLEBELL = "kettlebell"
    MACHINE = "machine"
    BODYWEIGHT = "bodyweight"
    OTHER = "other"


class MuscleGroup(str, Enum):
    CHEST = "chest"
    BACK = "back"
    SHOULDERS = "shoulders"
    BICEPS = "biceps"
    TRICEPS = "triceps"
    LEGS = "legs"
    GLUTES = "glutes"
    CORE = "core"
    FULL_BODY = "full_body"


class Set(BaseModel):
    reps: Optional[int] = Field(None, ge=1, le=1000)
    weight_lbs: Optional[float] = Field(None, ge=0, le=10000)
    duration_seconds: Optional[int] = Field(None, ge=1, le=7200)
    distance_miles: Optional[float] = Field(None, ge=0, le=1000)
    rest_seconds: Optional[int] = Field(None, ge=0, le=3600)


class Exercise(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    muscle_groups: List[MuscleGroup] = Field(..., min_items=1, max_items=10)
    equipment: Equipment
    sets: List[Set] = Field(..., min_items=1, max_items=50)
    instructions: Optional[str] = Field(None, max_length=1000)


class Workout(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    workout_type: WorkoutType
    duration_minutes: Optional[int] = Field(None, ge=1, le=480)
    difficulty_level: int = Field(..., ge=1, le=10)
    exercises: List[Exercise] = Field(..., min_items=1, max_items=50)
    tags: Optional[List[str]] = Field(None, max_items=20)
    creator: Optional[str] = Field(None, max_length=100)
    
    @validator('tags')
    def validate_tags(cls, v):
        if v:
            for tag in v:
                if len(tag) > 50:
                    raise ValueError('Tag too long')
        return v


# JSON Schema for validation
WORKOUT_JSON_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "minLength": 1,
            "maxLength": 200
        },
        "description": {
            "type": ["string", "null"],
            "maxLength": 1000
        },
        "workout_type": {
            "type": "string",
            "enum": ["strength", "cardio", "hiit", "yoga", "stretching", "bodyweight", "mixed"]
        },
        "duration_minutes": {
            "type": ["integer", "null"],
            "minimum": 1,
            "maximum": 480
        },
        "difficulty_level": {
            "type": "integer",
            "minimum": 1,
            "maximum": 10
        },
        "exercises": {
            "type": "array",
            "minItems": 1,
            "maxItems": 50,
            "items": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 200
                    },
                    "muscle_groups": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 10,
                        "items": {
                            "type": "string",
                            "enum": [
                                "chest", "back", "shoulders", "biceps", "triceps",
                                "legs", "glutes", "core", "full_body"
                            ]
                        }
                    },
                    "equipment": {
                        "type": "string",
                        "enum": [
                            "none", "dumbbells", "barbell", "resistance_bands",
                            "kettlebell", "machine", "bodyweight", "other"
                        ]
                    },
                    "sets": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 50,
                        "items": {
                            "type": "object",
                            "properties": {
                                "reps": {
                                    "type": ["integer", "null"],
                                    "minimum": 1,
                                    "maximum": 1000
                                },
                                "weight_lbs": {
                                    "type": ["number", "null"],
                                    "minimum": 0,
                                    "maximum": 10000
                                },
                                "duration_seconds": {
                                    "type": ["integer", "null"],
                                    "minimum": 1,
                                    "maximum": 7200
                                },
                                "distance_miles": {
                                    "type": ["number", "null"],
                                    "minimum": 0,
                                    "maximum": 1000
                                },
                                "rest_seconds": {
                                    "type": ["integer", "null"],
                                    "minimum": 0,
                                    "maximum": 3600
                                }
                            },
                            "additionalProperties": False
                        }
                    },
                    "instructions": {
                        "type": ["string", "null"],
                        "maxLength": 1000
                    }
                },
                "required": ["name", "muscle_groups", "equipment", "sets"],
                "additionalProperties": False
            }
        },
        "tags": {
            "type": ["array", "null"],
            "maxItems": 20,
            "items": {
                "type": "string",
                "maxLength": 50
            }
        },
        "creator": {
            "type": ["string", "null"],
            "maxLength": 100
        }
    },
    "required": ["title", "workout_type", "difficulty_level", "exercises"],
    "additionalProperties": False
}