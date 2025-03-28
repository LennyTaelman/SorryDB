import datetime
import json

from sorrydb.database.build_database import (
    init_database,
    prepare_and_process_lean_repo,
    update_database,
)


def test_prepare_and_process_lean_repo_with_mutiple_lean_versions():
    """
    Verify that the database builder can handle repositories
    that use different versions of Lean.

    sorryClientTestRepoMath uses v4.17.0-rc1 and sorryClientTestRepo uses v4.16.0
    """
    mathRepoResults = prepare_and_process_lean_repo(
        repo_url="https://github.com/austinletson/sorryClientTestRepoMath",
    )

    assert len(mathRepoResults["sorries"]) > 0
    repoResults = prepare_and_process_lean_repo(
        repo_url="https://github.com/austinletson/sorryClientTestRepo",
    )

    assert len(repoResults["sorries"]) > 0


def test_init_database_with_mock_repos(mock_repos, init_db_mock_repos_path, tmp_path):
    """
    Test that init_database correctly initializes a database with mock repositories.
    """
    temp_db_path = tmp_path / "test_database.json"

    # Initialize the database
    init_database(
        [repo["remote"] for repo in mock_repos],  # repo urls
        datetime.datetime(2025, 3, 10, tzinfo=datetime.timezone.utc),  # fixed test date
        temp_db_path,
    )

    # Load the generated database
    with open(temp_db_path, "r") as f:
        generated_db = json.load(f)

    # Load the expected database
    with open(init_db_mock_repos_path, "r") as f:
        expected_db = json.load(f)

    assert generated_db == expected_db, (
        "Generated database does not match expected database"
    )


def normalize_sorrydb_for_comparison(data):
    """Normalize run-specific timestamps in database to allow comparison across runs."""
    for repo in data.get("repos", []):
        repo["last_time_visited"] = "NORMALIZED_TIMESTAMP"

    for sorry in data.get("sorries", []):
        sorry["metadata"]["inclusion_date"] = "NORMALIZED_TIMESTAMP"

    return data


def test_update_database_single_repo(
    init_db_mock_single_path, update_db_single_test_repo_path, tmp_path
):
    """Test that update_database correctly updates the database file."""

    tmp_write_db = tmp_path / "updated_sorry_database.json"

    update_stats = update_database(init_db_mock_single_path, tmp_write_db)

    assert update_stats == {
        "https://github.com/austinletson/sorryClientTestRepo": {
            "78202012bfe87f99660ba2fe5973eb1a8110ab64": {"count": 3},
            "f8632a130a6539d9f546a4ef7b412bc3d86c0f63": {"count": 4},
        }
    }

    assert tmp_write_db.exists(), "The updated database file was not created"

    with (
        open(tmp_write_db, "r") as f1,
        open(update_db_single_test_repo_path, "r") as f2,
    ):
        tmp_content = json.load(f1)
        expected_content = json.load(f2)

    # Normalize time fields and ids in both JSONs
    normalized_tmp = normalize_sorrydb_for_comparison(tmp_content)
    normalized_expected = normalize_sorrydb_for_comparison(expected_content)

    assert normalized_tmp == normalized_expected, (
        "The sorries data doesn't match the expected content"
    )


def test_update_database_multiple_repo(
    init_db_mock_multiple_repos_path, update_db_multiple_repos_test_repo_path, tmp_path
):
    """Test that update_database correctly updates the database file."""

    tmp_write_db = tmp_path / "updated_sorry_database.json"

    update_stats = update_database(init_db_mock_multiple_repos_path, tmp_write_db)

    assert update_stats == {
        "https://github.com/austinletson/sorryClientTestRepo": {
            "78202012bfe87f99660ba2fe5973eb1a8110ab64": {"count": 3},
            "f8632a130a6539d9f546a4ef7b412bc3d86c0f63": {"count": 4},
        },
        "https://github.com/austinletson/sorryClientTestRepoMath": {
            "e853cb7ab1cdb382ea12b3f11bcbe6bbfeb32d47": {"count": 1},
            "c1c539f7432bafccd8eaf55f363eaad4e0b92374": {"count": 2},
        },
    }

    assert tmp_write_db.exists(), "The updated database file was not created"

    with (
        open(tmp_write_db, "r") as f1,
        open(update_db_multiple_repos_test_repo_path, "r") as f2,
    ):
        tmp_content = json.load(f1)
        expected_content = json.load(f2)

    # Normalize time fields and ids in both JSONs
    normalized_tmp = normalize_sorrydb_for_comparison(tmp_content)
    normalized_expected = normalize_sorrydb_for_comparison(expected_content)

    assert normalized_tmp == normalized_expected, (
        "The sorries data doesn't match the expected content"
    )
