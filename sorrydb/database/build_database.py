import datetime
import json
import logging
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from sorrydb.database.process_sorries import prepare_and_process_lean_repo
from sorrydb.database.sorry import DebugInfo, Location, Metadata, RepoInfo, Sorry
from sorrydb.utils.git_ops import leaf_commits, remote_heads_hash

# Create a module-level logger
logger = logging.getLogger(__name__)


def init_database(
    repo_list: list, starting_date: datetime.datetime, database_file: Path
):
    """
    Initialize a sorry database from a list of repositories.

    Args:
        repo_list: List of repository URLs to include in the database
        starting_date: Datetime object to use as the last_time_visited for all repos
        output_path: Path to save the database JSON file
    """
    logger.info(f"Initializing database from {len(repo_list)} repositories")
    # Create the initial database structure
    database = {"repos": [], "sorries": []}

    # Format the datetime as ISO 8601 string for JSON storage
    formatted_date = starting_date.isoformat()

    # Add each repository to the database
    for repo_url in repo_list:
        repo_entry = {
            "remote_url": repo_url,
            "last_time_visited": formatted_date,
            "remote_heads_hash": None,
        }
        database["repos"].append(repo_entry)

    # Write the database to the output file
    database_file.parent.mkdir(parents=True, exist_ok=True)
    with open(database_file, "w") as f:
        json.dump(database, f, indent=2)

    logger.info(
        f"Initialized database with {len(repo_list)} repositories at {database_file}"
    )


def load_database(database_path: Path) -> dict:
    """
    Load a SorryDatabase from a JSON file.

    Args:
        database_path: Path to the database JSON file

    Returns:
        dict: The loaded database

    Raises:
        FileNotFoundError: If the database file doesn't exist
        ValueError: If the database file contains invalid JSON
    """
    logger.info(f"Loading sorry database from {database_path}")
    try:
        with open(database_path, "r") as f:
            database = json.load(f)
        return database
    except FileNotFoundError:
        logger.error(f"Database file not found: {database_path}")
        raise FileNotFoundError(f"Database file not found: {database_path}")
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in database file: {database_path}")
        raise ValueError(f"Invalid JSON in database file: {database_path}")


def compute_new_sorries_stats(sorries) -> dict:
    """
    Compute statistics about a list of sorries.

    Args:
        sorries: List of sorry dictionaries

    Returns:
        dict: Statistics about the sorries, including count
    """
    if not sorries:
        return {"count": 0}

    return {"count": len(sorries)}


def process_new_commits(commits, remote_url, lean_data) -> tuple[list[Sorry], dict]:
    """
    Process a list of new commits for a repository, building a Sorry object for each new sorry in the repo

    Args:

        commits: List of commit dictionaries to process
        remote_url: URL of the repository
        lean_data: Path to the lean data directory
    Returns:
        tuple: (list of new sorries, dict of statistics by commit)
    """

    new_sorries = []
    new_sorries_stats = {}

    for commit in commits:
        logger.debug(f"processing commit on {remote_url}: {commit}")
        try:
            time_visited = datetime.datetime.now(datetime.timezone.utc)

            repo_results = prepare_and_process_lean_repo(
                repo_url=remote_url, lean_data=lean_data, branch=commit["branch"]
            )

            for sorry in repo_results["sorries"]:
                # Create dataclass instances for each component of the Sorry
                repo_info = RepoInfo(
                    remote=remote_url,
                    branch=commit["branch"],
                    commit=commit["sha"],
                    lean_version=repo_results["metadata"].get("lean_version", ""),
                )

                location = Location(
                    start_line=sorry["location"]["start_line"],
                    start_column=sorry["location"]["start_column"],
                    end_line=sorry["location"]["end_line"],
                    end_column=sorry["location"]["end_column"],
                    file=sorry["location"]["file"],
                )

                debug_info = DebugInfo(
                    goal=sorry["goal"],
                    url=f"{remote_url}/blob/{commit['sha']}/{sorry['location']['file']}#L{sorry['location']['start_line']}",
                )

                blame_date = sorry["blame"]["date"]
                if isinstance(blame_date, str):
                    blame_date = datetime.datetime.fromisoformat(blame_date)

                metadata = Metadata(
                    blame_email_hash=sorry["blame"]["author_email_hash"],
                    blame_date=blame_date,
                    inclusion_date=time_visited,
                )

                # Sorry instance `id` field will be auto-generated
                sorry_instance = Sorry(
                    repo=repo_info,
                    location=location,
                    debug_info=debug_info,
                    metadata=metadata,
                )

                new_sorries.append(sorry_instance)

            commit_stats = compute_new_sorries_stats(repo_results["sorries"])

            new_sorries_stats[commit["sha"]] = commit_stats

            logger.info(
                f"Processed commit {commit['sha']} with {commit_stats['count']} sorries"
            )

        except Exception as e:
            logger.error(
                f"Error processing commit {commit} on repository {remote_url}: {e}"
            )
            logger.exception(e)
            continue  # Continue with next commit

    return new_sorries, new_sorries_stats


def repo_has_updates(repo: dict) -> Optional[str]:
    """
    Check if a repository has updates by comparing remote heads hash.

    Returns:
        Optional[str]: The new remote heads hash if updates are available, None otherwise
    """
    remote_url = repo["remote_url"]
    logger.info(f"Checking repository for new commits: {remote_url}")

    current_hash = remote_heads_hash(remote_url)
    if current_hash is None:
        logger.warning(f"Could not get remote heads hash for {remote_url}, skipping")
        return None

    if current_hash == repo["remote_heads_hash"]:
        logger.info(f"No changes detected for {remote_url}, skipping")
        return None

    logger.info(f"New commits detected for {remote_url}, processing...")
    return current_hash


def get_new_leaf_commits(repo: dict) -> list:
    remote_url = repo["remote_url"]

    all_commits = leaf_commits(remote_url)

    last_visited = datetime.datetime.fromisoformat(repo["last_time_visited"])
    new_leaf_commits = []

    for commit in all_commits:
        commit_date = datetime.datetime.fromisoformat(commit["date"])

        if commit_date > last_visited:
            new_leaf_commits.append(commit)
            logger.info(
                f"Including new commit {commit['sha']} on branch {commit['branch']} from {commit_date.isoformat()}"
            )
        else:
            logger.debug(
                f"Skipping old commit {commit['sha']} on branch {commit['branch']} from {commit_date.isoformat()}"
            )

    logger.info(
        f"Filtered {len(all_commits)} commits to {len(new_leaf_commits)} new commits after {last_visited.isoformat()}"
    )
    return new_leaf_commits


def find_new_sorries(repo, lean_data) -> tuple[list[Sorry], dict]:
    """
    Find new sorries in a repository since the last time it was visited.

    Returns:
        tuple: (list of new sorries, dict of statistics by commit)
    """
    # only look for new sorries if the repo has updates since the last update
    new_remote_hash = repo_has_updates(repo)
    if new_remote_hash is None:
        return [], {}

    # record the time before starting processing repo
    time_before_processing_repo = datetime.datetime.now(
        datetime.timezone.utc
    ).isoformat()

    new_leaf_commits = get_new_leaf_commits(repo)

    if lean_data is None:
        with tempfile.TemporaryDirectory() as temp_dir:
            logger.info(f"Using temporary directory for lean data: {temp_dir}")
            new_sorries, new_sorry_stats = process_new_commits(
                new_leaf_commits, repo["remote_url"], Path(temp_dir)
            )
    else:
        # If lean_data is provided, make sure it exists
        lean_data = Path(lean_data)
        lean_data.mkdir(exist_ok=True)
        logger.info(f"Using non-temporary directory for lean data: {lean_data}")
        new_sorries, new_sorry_stats = process_new_commits(
            new_leaf_commits, repo["remote_url"], lean_data
        )

    # update repo with new time visited and remote hash
    repo["last_time_visited"] = time_before_processing_repo
    repo["remote_heads_hash"] = new_remote_hash

    return new_sorries, new_sorry_stats


def add_new_sorries_to_database(new_sorries: list[Sorry], database):
    new_sorries_dict = map(asdict, new_sorries)
    database["sorries"].extend(new_sorries_dict)


def update_database(
    database_path: Path,
    write_database_path: Optional[Path] = None,
    lean_data: Optional[Path] = None,
    stats_file: Optional[Path] = None,
) -> dict:
    """
    Update a SorryDatabase by checking for changes in repositories and processing new commits.

    Args:
        database_path: Path to the database JSON file
        write_database_path: Path to write the databse JSON file (default: database_path)
        lean_data: Path to the lean data directory (default: create temporary directory)
        stats_file: file to write database stats (default: don't write statistics to file)
    Returns:
        update_database_stats: statistics on the sorries that were added to the database
    """

    if not write_database_path:
        write_database_path = database_path

    database = load_database(database_path)

    update_database_stats = {}

    for repo in database["repos"]:
        new_sorries, new_sorry_stats = find_new_sorries(repo, lean_data)
        if new_sorries:
            add_new_sorries_to_database(new_sorries, database)

        update_database_stats[repo["remote_url"]] = new_sorry_stats

    logger.info(f"Writing updated database to {write_database_path}")
    with open(write_database_path, "w") as f:
        json.dump(
            database,
            f,
            indent=2,
            default=Sorry.default_json_serialization,
        )
    logger.info("Database update completed successfully")

    if stats_file:
        stats_path = Path(stats_file)
        with open(stats_path, "w") as f:
            json.dump(update_database_stats, f, indent=2)
        logger.info(f"Update statistics written to {stats_path}")

    return update_database_stats
