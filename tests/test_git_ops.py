import datetime
import unittest.mock as mock

from sorrydb.crawler.git_ops import leaf_commits, remote_heads, remote_heads_hash


def test_remote_heads():
    """Test the remote_heads function with a real repository."""

    url = "https://github.com/austinletson/sorryClientTestRepoMath"

    # Get and display all heads
    heads = remote_heads(url)
    print("\nFound branches:")
    for head in heads:
        print(f"Branch: {head['branch']:<40} SHA: {head['sha']}")

    # Get and display the combined hash
    hash_value = remote_heads_hash(url)
    print(f"\nCombined hash of all branch heads: {hash_value}")


def test_remote_heads_hash_different():
    """Test that different sets of branch heads produce different hash values."""
    # Mock the remote_heads function to return controlled test data
    with mock.patch("sorrydb.crawler.git_ops.remote_heads") as mock_remote_heads:
        # First set of branch heads
        mock_remote_heads.return_value = [
            {"branch": "main", "sha": "abc123"},
            {"branch": "dev", "sha": "def456"},
        ]
        hash1 = remote_heads_hash("https://example.com/repo1")

        # Second set with update to one of the branches
        mock_remote_heads.return_value = [
            {"branch": "main", "sha": "abc123"},
            {"branch": "dev", "sha": "xyz789"},
        ]
        hash2 = remote_heads_hash("https://example.com/repo1")

        # Verify that different branch heads produce different hashes
        assert hash1 != hash2, "Modified branch should produce different hashes"

    with mock.patch("sorrydb.crawler.git_ops.remote_heads") as mock_remote_heads:
        # First set of branch heads
        mock_remote_heads.return_value = [
            {"branch": "main", "sha": "abc123"},
            {"branch": "dev", "sha": "def456"},
        ]
        hash1 = remote_heads_hash("https://example.com/repo1")

        # Second set with new branch
        mock_remote_heads.return_value = [
            {"branch": "main", "sha": "abc123"},
            {"branch": "dev", "sha": "def456"},
            {"branch": "feature-branch", "sha": "ghi789"},
        ]
        hash2 = remote_heads_hash("https://example.com/repo1")

        # Verify that different branch heads produce different hashes
        assert hash1 != hash2, "Additional branch should produce different hashes"


def test_leaf_commits():
    """Test the leaf_commits function with a real repository."""

    url = "https://github.com/fpvandoorn/carleson"

    # Get and display all branch heads with commit dates
    commits = leaf_commits(url)

    # Verify we got some results
    assert len(commits) > 0, "Should find at least one branch"

    print("\nFound branch commits:")
    for commit in commits:
        print(
            f"Branch: {commit['branch']:<20} SHA: {commit['sha']:<40} Date: {commit['date']}"
        )

    # Verify each commit has the expected fields
    for commit in commits:
        assert "branch" in commit, "Each commit should have a branch name"
        assert "sha" in commit, "Each commit should have a SHA"
        assert "date" in commit, "Each commit should have a date"

        # Verify SHA format (should be 40 hex characters)
        assert len(commit["sha"]) == 40, (
            f"SHA should be 40 characters, got {len(commit['sha'])}"
        )
        assert all(c in "0123456789abcdef" for c in commit["sha"].lower()), (
            "SHA should be hexadecimal"
        )

        # Verify date format (should be a valid ISO date string)
        try:
            # Try to parse the date string
            datetime.datetime.fromisoformat(commit["date"].replace("Z", "+00:00"))
        except ValueError as e:
            assert False, f"Date '{commit['date']}' is not a valid ISO format: {e}"
