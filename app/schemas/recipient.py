from typing import Any, Dict, Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


class RecipientInput(BaseModel):
    """Input payload for a single certificate recipient."""

    name: str = Field(..., min_length=1, max_length=255, description="Full name of recipient")
    email: EmailStr = Field(..., description="Valid email address of recipient")
    extra_data: Optional[Dict[str, Any]] = Field(default=None, description="Optional extra metadata (e.g. grade, honors)")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Recipient name cannot be empty or whitespace only")
        return cleaned


class RecipientValidationFailure(BaseModel):
    """Information regarding a recipient that failed initial schema/data validation."""

    index: int = Field(..., description="Position in the original input list (0-indexed)")
    raw_data: Dict[str, Any] = Field(..., description="Raw recipient payload provided")
    error: str = Field(..., description="Explanation of why validation failed")
