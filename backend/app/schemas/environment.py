"""API shapes for a deploy target's environment variables."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

# POSIX-ish environment variable name. Anything else would not survive being
# passed to a build, so it is rejected at the edge rather than later.
KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

MAX_VALUE_LENGTH = 32_768
MAX_VARIABLES = 200


class EnvVarIn(BaseModel):
    """One variable being saved."""

    key: str = Field(min_length=1, max_length=256)
    # None means "keep the stored value" — a secret's plaintext is never sent
    # to the browser, so the form cannot echo it back on save.
    value: str | None = Field(default=None, max_length=MAX_VALUE_LENGTH)
    is_secret: bool = False

    @field_validator("key")
    @classmethod
    def _valid_key(cls, value: str) -> str:
        key = value.strip()
        if not KEY_PATTERN.match(key):
            raise ValueError(
                f"{key!r} is not a valid environment variable name — use letters, "
                "digits and underscores, not starting with a digit."
            )
        return key


class EnvVarsIn(BaseModel):
    """The complete set for a target. Saving replaces what is stored."""

    variables: list[EnvVarIn] = Field(default_factory=list, max_length=MAX_VARIABLES)

    @field_validator("variables")
    @classmethod
    def _no_duplicate_keys(cls, variables: list[EnvVarIn]) -> list[EnvVarIn]:
        seen = set()
        for variable in variables:
            if variable.key in seen:
                raise ValueError(f"Duplicate environment variable: {variable.key}")
            seen.add(variable.key)
        return variables


class EnvVarOut(BaseModel):
    """
    One stored variable.

    `value` is null for secrets — the plaintext never leaves the server once
    saved. `has_value` tells the UI something is stored so it can show a mask
    rather than an empty box.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    value: str | None = None
    is_secret: bool
    has_value: bool = True
    created_at: datetime
    updated_at: datetime
