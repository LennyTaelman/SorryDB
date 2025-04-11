import datetime
import json
import logging
import tempfile
from pathlib import Path
from typing import Optional

from sorrydb.database.process_sorries import prepare_and_process_lean_repo
from sorrydb.database.sorry import DebugInfo, Location, Metadata, RepoInfo, Sorry
from sorrydb.database.sorry_database import JsonDatabase
from sorrydb.utils.git_ops import leaf_commits, remote_heads_hash
from sorrydb.utils.lean_repo import LakeTimeoutError

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


def process_new_commits(commits, remote_url, lean_data, database: JsonDatabase):
    """
    Process a list of new commits for a repository, building a Sorry object for each new sorry in the repo

    Args:

        commits: List of commit dictionaries to process
        remote_url: URL of the repository
        lean_data: Path to the lean data directory
    Returns:
        tuple: (list of new sorries, dict of statistics by commit)
    """

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

                database.add_sorry(sorry_instance)

            try:
                commit_sorry_count = database.update_stats[remote_url][commit["sha"]][
                    "count"
                ]
            except (KeyError, TypeError):
                commit_sorry_count = 0

            logger.info(
                f"Processed commit {commit['sha']} with {commit_sorry_count} sorries"
            )

        except LakeTimeoutError:
            database.set_lake_timeout(remote_url, True)
            logger.warning(f"Lake timeout on {remote_url}. Skipping further processing")
            break  # if there is a Lake timeout skip processing the rest of the commits for this repo
        except Exception as e:
            logger.error(
                f"Error processing commit {commit} on repository {remote_url}: {e}"
            )
            logger.exception(e)
            continue  # Continue with next commit


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


def find_new_sorries(repo, lean_data, database: JsonDatabase):
    """
    Find new sorries in a repository since the last time it was visited.

    Returns:
        tuple: (list of new sorries, dict of statistics by commit)
    """
    # only look for new sorries if the repo has updates since the last update
    new_remote_hash = repo_has_updates(repo)
    if new_remote_hash is None:
        logger.info(f"No new leaf commits for {repo['remote_url']}")
        database.set_new_leaf_commit(repo["remote_url"], False)
        return
    else:
        database.set_new_leaf_commit(repo["remote_url"], True)

    # record the time before starting processing repo
    time_before_processing_repo = datetime.datetime.now(
        datetime.timezone.utc
    ).isoformat()

    database.set_start_processing_time(repo["remote_url"], time_before_processing_repo)

    new_leaf_commits = get_new_leaf_commits(repo)

    if lean_data is None:
        with tempfile.TemporaryDirectory() as temp_dir:
            logger.info(f"Using temporary directory for lean data: {temp_dir}")
            process_new_commits(
                new_leaf_commits, repo["remote_url"], Path(temp_dir), database
            )
    else:
        # If lean_data is provided, make sure it exists
        lean_data = Path(lean_data)
        lean_data.mkdir(exist_ok=True)
        logger.info(f"Using non-temporary directory for lean data: {lean_data}")
        process_new_commits(new_leaf_commits, repo["remote_url"], lean_data, database)

    # update repo with new time visited and remote hash
    repo["last_time_visited"] = time_before_processing_repo
    repo["remote_heads_hash"] = new_remote_hash

    # record the time after finishing processing the repo
    time_after_processing_repo = datetime.datetime.now(
        datetime.timezone.utc
    ).isoformat()
    database.set_end_processing_time(repo["remote_url"], time_after_processing_repo)


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

    database = JsonDatabase()

    database.load_database(database_path)

    for repo in database.get_all_repos():
        find_new_sorries(repo, lean_data, database)

    database.write_database(write_database_path)
    if stats_file:
        database.write_stats(stats_file)

    return database.update_stats
