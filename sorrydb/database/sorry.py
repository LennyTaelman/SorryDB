import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class RepoInfo:
    remote: str
    branch: str
    commit: str
    lean_version: str  # Version of Lean used on the commit where the sorry was found


@dataclass
class Location:
    start_line: int
    start_column: int
    end_line: int
    end_column: int
    file: str  # File path where the sorry was found


@dataclass
class DebugInfo:
    goal: str  # The goal state at the sorry
    url: str  # URL to the sorry in the repository


@dataclass
class Metadata:
    blame_email_hash: str  # Hash of the email of the person who added the sorry
    blame_date: datetime  # Date when the sorry was added
    inclusion_date: datetime  # Date when the sorry was included in the database


@dataclass
class Sorry:
    repo: RepoInfo
    location: Location
    debug_info: DebugInfo
    metadata: Metadata
    id: Optional[str] = field(
        default=None, init=False
    )  # Unique identifier for the sorry

    @staticmethod
    def default_json_serialization(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        else:
            return str(obj)

    def __post_init__(self):
        if self.id is None:
            hash_dict = asdict(self)

            # Remove fields we don't want to include in the hash
            hash_dict.pop("id", None)
            hash_dict["metadata"].pop("inclusion_date")

            # Convert to a stable string representation so that Sorry ids are consistent across database runs
            hash_str = json.dumps(
                hash_dict, sort_keys=True, default=Sorry.default_json_serialization
            )
            self.id = hashlib.sha256(hash_str.encode()).hexdigest()
