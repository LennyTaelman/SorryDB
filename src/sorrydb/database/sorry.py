import logging
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class Goal(BaseModel):
    """Represents the goal at a sorry position."""

    type: str
    hash: str
    parentType: Optional[str] = None


class Location(BaseModel):
    """Represents the location of a sorry in a file."""

    startLine: int
    startColumn: int
    endLine: int
    endColumn: int
    file: str


class Blame(BaseModel):
    """Git blame information for a sorry."""

    commit: str
    author: str
    author_email: str
    date: datetime
    summary: str


class Metadata(BaseModel):
    """Repository metadata for a sorry."""

    commit_time: datetime
    remote_url: str
    sha: str
    branch: str


class Sorry(BaseModel):
    """Represents a sorry in a Lean file."""

    goal: Goal
    location: Location
    blame: Blame
    metadata: Metadata

    @classmethod
    def from_json_file(cls, file_path: str) -> "Sorry":
        """Load a Sorry instance from a JSON file."""
        logger.info(f"Loading Sorry instance from {file_path}")
        with open(file_path, "r") as f:
            return cls.model_validate_json(f.read())

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        logger.info("Converting Sorry instance to JSON string")
        return self.model_dump_json(indent=indent)

    def to_json_file(self, file_path: str, indent: int = 2) -> None:
        """Save the Sorry instance to a JSON file."""
        logger.info(f"Saving Sorry instance to {file_path}")
        with open(file_path, "w") as f:
            f.write(self.to_json(indent=indent))
