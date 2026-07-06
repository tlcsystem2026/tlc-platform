import re
from typing import Literal
from pydantic import BaseModel, Field, field_validator

_PACKAGE_RE = re.compile(r"^[A-Za-z0-9_.-]+\.zip$", re.IGNORECASE)

class DeployRequest(BaseModel):
    package_name: str = Field(min_length=5, max_length=255)
    run_tests: bool = True
    start_api: bool = False

    @field_validator("package_name")
    @classmethod
    def validate_package_name(cls, value: str) -> str:
        if not _PACKAGE_RE.fullmatch(value):
            raise ValueError("package_name must be a simple ZIP filename")
        if ".." in value or "/" in value or "\\" in value:
            raise ValueError("path components are not allowed")
        return value

class DeployResult(BaseModel):
    status: Literal["success", "failed"]
    package_name: str
    return_code: int
    output_tail: str = ""
