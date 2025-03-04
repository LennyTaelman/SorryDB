import json
from pathlib import Path

import pytest

from sorrydb.database.sorry import Sorry
from sorrydb.database.sorry_database import SorryDatabase


@pytest.fixture
def mock_sorry_path():
    """Path to the example sorry JSON file."""
    return Path("tests/mock_data/mock_sorry.json")


@pytest.fixture
def mock_database_path():
    """Path to the mock database JSON file."""
    return Path("tests/mock_data/mock_sorry_database.json")


@pytest.fixture
def mock_sorry(mock_sorry_path):
    """Create a Sorry object from the example JSON."""
    with open(mock_sorry_path, "r") as f:
        sorry_data = json.load(f)
    return Sorry.model_validate(sorry_data)


@pytest.fixture
def mock_database(mock_database_path):
    """Create a SorryDatabase from the mock database JSON."""
    return SorryDatabase.load_from_file(mock_database_path)


@pytest.fixture
def temp_file_path(tmp_path):
    """Create a temporary file path for testing."""
    return tmp_path / "test_database.json"


def test_init_empty():
    """Test initializing an empty database."""
    db = SorryDatabase()
    assert len(db.sorries) == 0


def test_init_with_sorries(mock_sorry):
    """Test initializing with a list of Sorry objects."""
    db = SorryDatabase(sorries=[mock_sorry])
    assert len(db.sorries) == 1
    assert db.sorries[0] == mock_sorry


def test_add_sorries(mock_sorry):
    """Test adding multiple Sorry objects."""
    db = SorryDatabase()
    db.add_sorries([mock_sorry, mock_sorry])
    assert len(db.sorries) == 2
    assert db.sorries[0] == mock_sorry
    assert db.sorries[1] == mock_sorry


def test_write_and_load(mock_database, temp_file_path):
    """Test writing to a file and loading it back."""
    # Write the database to a file
    mock_database.write_to_file(temp_file_path)

    # Verify the file exists
    assert temp_file_path.exists()

    # Load the database from the file
    loaded_db = SorryDatabase.load_from_file(temp_file_path)

    # Verify the content
    assert len(loaded_db.sorries) == len(mock_database.sorries)

    # Compare each Sorry object
    for i, sorry in enumerate(loaded_db.sorries):
        assert sorry.model_dump() == mock_database.sorries[i].model_dump()


def test_write_to_nonexistent_directory(mock_database, tmp_path):
    """Test writing to a file in a directory that doesn't exist yet."""
    nonexistent_dir = tmp_path / "new_dir" / "subdir"
    file_path = nonexistent_dir / "database.json"

    # The directory shouldn't exist yet
    assert not nonexistent_dir.exists()

    # Write should create the directory
    mock_database.write_to_file(file_path)

    # Verify the directory and file were created
    assert nonexistent_dir.exists()
    assert file_path.exists()


def test_load_from_file(mock_database_path):
    """Test loading from an existing file."""
    db = SorryDatabase.load_from_file(mock_database_path)
    assert len(db.sorries) == 3  # Based on the mock data having 3 entries


def test_using_add_sorries_for_single_item(mock_sorry):
    """Test adding a single Sorry object using add_sorries."""
    db = SorryDatabase()
    db.add_sorries([mock_sorry])
    assert len(db.sorries) == 1
    assert db.sorries[0] == mock_sorry
