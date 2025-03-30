import json

from sorrydb.database.build_database import (
    prepare_and_process_lean_repo,
    update_database,
)


def test_prepare_and_process_lean_repo_with_mutiple_lean_versions(tmp_path):
    """
    Verify that the database builder can handle repositories
    that use different versions of Lean.

    sorryClientTestRepoMath uses v4.17.0-rc1 and sorryClientTestRepo uses v4.16.0
    """
    mathRepoResults = prepare_and_process_lean_repo(
        repo_url="https://github.com/austinletson/sorryClientTestRepoMath",
        lean_data=tmp_path / "repo_math",
    )

    assert len(mathRepoResults["sorries"]) > 0
    repoResults = prepare_and_process_lean_repo(
        repo_url="https://github.com/austinletson/sorryClientTestRepo",
        lean_data=tmp_path / "repo",
    )

    assert len(repoResults["sorries"]) > 0


def normalize_sorrydb_for_comparison(data):
    """
    Normalize time-related fields and UUIDs in the database JSON to allow comparison
    independent of timestamps and randomly generated UUIDs.

    Args:
        data (dict): The database JSON as a dictionary

    Returns:
        dict: The modified database with normalized time fields and UUIDs
    """
    # Normalize the time fields and UUIDs in each repository directly
    for repo in data.get("repos", []):
        repo["last_time_visited"] = "NORMALIZED_TIMESTAMP"

        for commit in repo.get("commits", []):
            commit["time_visited"] = "NORMALIZED_TIMESTAMP"

            for sorry in commit.get("sorries", []):
                sorry["uuid"] = "NORMALIZED_UUID"

    return data


def test_update_database(
    init_db_single_test_repo_path, update_db_single_test_repo_path, tmp_path
):
    """Test that update_database correctly updates the database file."""

    tmp_write_db = tmp_path / "updated_sorry_database.json"

    # Update database
    update_stats = update_database(init_db_single_test_repo_path, tmp_write_db)

    assert update_stats == {
        "https://github.com/austinletson/sorryClientTestRepo": {
            "78202012bfe87f99660ba2fe5973eb1a8110ab64": {"count": 4},
            "f8632a130a6539d9f546a4ef7b412bc3d86c0f63": {"count": 5},
        }
    }

    assert tmp_write_db.exists(), "The updated database file was not created"

    # Compare the output to update_db_single_test_repo_path
    with (
        open(tmp_write_db, "r") as f1,
        open(update_db_single_test_repo_path, "r") as f2,
    ):
        tmp_content = json.load(f1)
        expected_content = json.load(f2)

    # Normalize time fields and UUIDs in both JSONs
    normalized_tmp = normalize_sorrydb_for_comparison(tmp_content)
    normalized_expected = normalize_sorrydb_for_comparison(expected_content)

    # Compare the normalized JSONs
    assert normalized_tmp == normalized_expected, (
        "The sorries data doesn't match the expected content"
    )
