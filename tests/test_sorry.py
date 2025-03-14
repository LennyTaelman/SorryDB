import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from sorrydb.database.sorry import Sorry, Goal, Location, Blame, Metadata


@pytest.fixture
def example_sorry_path():
    """Fixture that provides the path to the example_sorry.json file."""
    return Path("tests/mock_data/mock_sorry.json")


@pytest.fixture
def example_sorry_data(example_sorry_path):
    """Fixture that provides the parsed JSON data from example_sorry.json."""
    with open(example_sorry_path, "r") as f:
        return json.load(f)


def test_load_example_sorry_from_file(example_sorry_path):
    """Test loading the example_sorry.json file."""
    sorry = Sorry.from_json_file(str(example_sorry_path))
    
    # Verify the Sorry instance was created correctly
    assert isinstance(sorry, Sorry)
    assert isinstance(sorry.goal, Goal)
    assert isinstance(sorry.location, Location)
    assert isinstance(sorry.blame, Blame)
    assert isinstance(sorry.metadata, Metadata)


def test_sorry_fields(example_sorry_data, example_sorry_path):
    """Test that all fields in the Sorry model are correctly parsed."""
    sorry = Sorry.from_json_file(str(example_sorry_path))
    
    # Test Goal fields
    assert sorry.goal.type == example_sorry_data["goal"]["type"]
    assert sorry.goal.hash == example_sorry_data["goal"]["hash"]
    if "parentType" in example_sorry_data["goal"]:
        assert sorry.goal.parentType == example_sorry_data["goal"]["parentType"]
    
    # Test Location fields
    assert sorry.location.startLine == example_sorry_data["location"]["startLine"]
    assert sorry.location.startColumn == example_sorry_data["location"]["startColumn"]
    assert sorry.location.endLine == example_sorry_data["location"]["endLine"]
    assert sorry.location.endColumn == example_sorry_data["location"]["endColumn"]
    assert sorry.location.file == example_sorry_data["location"]["file"]
    
    # Test Blame fields
    assert sorry.blame.commit == example_sorry_data["blame"]["commit"]
    assert sorry.blame.author == example_sorry_data["blame"]["author"]
    assert sorry.blame.author_email == example_sorry_data["blame"]["author_email"]
    assert sorry.blame.summary == example_sorry_data["blame"]["summary"]
    
    # Test Metadata fields
    assert sorry.metadata.remote_url == example_sorry_data["metadata"]["remote_url"]
    assert sorry.metadata.sha == example_sorry_data["metadata"]["sha"]
    assert sorry.metadata.branch == example_sorry_data["metadata"]["branch"]


def test_datetime_parsing(example_sorry_data, example_sorry_path):
    """Test that datetime fields are correctly parsed."""
    sorry = Sorry.from_json_file(str(example_sorry_path))
    
    # Check that date strings were converted to datetime objects
    assert isinstance(sorry.blame.date, datetime)
    assert isinstance(sorry.metadata.commit_time, datetime)
    
    # Verify the datetime values match the expected format
    expected_blame_date = datetime.fromisoformat(
        example_sorry_data["blame"]["date"].replace("Z", "+00:00")
    )
    expected_commit_time = datetime.fromisoformat(
        example_sorry_data["metadata"]["commit_time"].replace("Z", "+00:00")
    )
    
    assert sorry.blame.date == expected_blame_date
    assert sorry.metadata.commit_time == expected_commit_time


def test_to_json():
    """Test converting a Sorry instance to a JSON string."""
    # Create a minimal Sorry instance
    sorry = Sorry(
        goal=Goal(type="target", hash="abcdef"),
        location=Location(
            startLine=1, startColumn=2, endLine=3, endColumn=4, file="test.lean"
        ),
        blame=Blame(
            commit="123456",
            author="Test User",
            author_email="test@example.com",
            date=datetime(2023, 1, 1, 12, 0, 0),
            summary="Test commit",
        ),
        metadata=Metadata(
            commit_time=datetime(2023, 1, 2, 12, 0, 0),
            remote_url="https://github.com/test/repo.git",
            sha="abcdef",
            branch="main",
        ),
    )
    
    json_str = sorry.to_json()
    parsed_json = json.loads(json_str)
    
    # Verify the JSON structure
    assert parsed_json["goal"]["type"] == "target"
    assert parsed_json["location"]["file"] == "test.lean"
    assert parsed_json["blame"]["author"] == "Test User"
    assert parsed_json["metadata"]["branch"] == "main"


def test_to_json_file():
    """Test saving a Sorry instance to a JSON file."""
    # Create a minimal Sorry instance
    sorry = Sorry(
        goal=Goal(type="target", hash="abcdef"),
        location=Location(
            startLine=1, startColumn=2, endLine=3, endColumn=4, file="test.lean"
        ),
        blame=Blame(
            commit="123456",
            author="Test User",
            author_email="test@example.com",
            date=datetime(2023, 1, 1, 12, 0, 0),
            summary="Test commit",
        ),
        metadata=Metadata(
            commit_time=datetime(2023, 1, 2, 12, 0, 0),
            remote_url="https://github.com/test/repo.git",
            sha="abcdef",
            branch="main",
        ),
    )
    
    # Create a temporary file
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temp_file:
        temp_path = temp_file.name
    
    try:
        # Save to the temporary file
        sorry.to_json_file(temp_path)
        
        # Verify the file was created
        assert os.path.exists(temp_path)
        
        # Load the file and verify its contents
        with open(temp_path, "r") as f:
            saved_json = json.load(f)
        
        assert saved_json["goal"]["type"] == "target"
        assert saved_json["location"]["file"] == "test.lean"
        assert saved_json["blame"]["author"] == "Test User"
        assert saved_json["metadata"]["branch"] == "main"
    finally:
        # Clean up
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_round_trip(example_sorry_path):
    """Test loading a Sorry from a file and then saving it back."""
    # Load the example Sorry
    sorry = Sorry.from_json_file(str(example_sorry_path))
    
    # Create a temporary file
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temp_file:
        temp_path = temp_file.name
    
    try:
        # Save to the temporary file
        sorry.to_json_file(temp_path)
        
        # Load it back
        reloaded_sorry = Sorry.from_json_file(temp_path)
        
        # Verify the reloaded Sorry matches the original
        assert reloaded_sorry.goal.type == sorry.goal.type
        assert reloaded_sorry.goal.hash == sorry.goal.hash
        assert reloaded_sorry.location.file == sorry.location.file
        assert reloaded_sorry.blame.author == sorry.blame.author
        assert reloaded_sorry.metadata.branch == sorry.metadata.branch
    finally:
        # Clean up
        if os.path.exists(temp_path):
            os.unlink(temp_path)

