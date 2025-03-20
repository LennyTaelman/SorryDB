import datetime
import json
from pathlib import Path
import logging
from typing import Optional
import uuid
import tempfile
from sorrydb.crawler.git_ops import leaf_commits, remote_heads_hash
from sorrydb.database.process_sorries import prepare_and_process_lean_repo

# Create a module-level logger
logger = logging.getLogger(__name__)
    
def init_database(repo_list: list, starting_date: datetime.datetime, database_file: Path):
    """
    Initialize a sorry database from a list of repositories.
    
    Args:
        repo_list: List of repository URLs to include in the database
        starting_date: Datetime object to use as the last_time_visited for all repos
        output_path: Path to save the database JSON file
    """
    logger.info(f"Initializing database from {len(repo_list)} repositories")
    # Create the initial database structure
    database = {
        "repos": []
    }
    
    # Format the datetime as ISO 8601 string for JSON storage
    formatted_date = starting_date.isoformat()
    
    # Add each repository to the database
    for repo_url in repo_list:
        repo_entry = {
            "remote_url": repo_url,
            "last_time_visited": formatted_date,
            "remote_heads_hash": None,
            "commits": []
        }
        database["repos"].append(repo_entry)
    
    # Write the database to the output file
    database_file.parent.mkdir(parents=True, exist_ok=True)
    with open(database_file, 'w') as f:
        json.dump(database, f, indent=2)
    
    logger.info(f"Initialized database with {len(repo_list)} repositories at {database_file}")

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
        with open(database_path, 'r') as f:
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
    
    return {
        "count": len(sorries)
    }

def process_new_commits(database, repo_index, commits, remote_url, lean_data):
    """
    Process a list of new commits for a repository and add them to the database.
    
    Args:
        database: The database dictionary to update
        repo_index: Index of the repository in the database
        commits: List of commit dictionaries to process
        remote_url: URL of the repository
        lean_data: Path to the lean data directory
    Returns:
        new_sorries_stats: A dict of stats about the new commits and sorries found,
                          with commit hash as key and statistics as value
    """
    new_sorries_stats = {}
    for commit in commits:
        logger.debug(f"processing commit on {remote_url}: {commit}")
        try:
            # Record the time before processing the repo
            time_visited = datetime.datetime.now(datetime.timezone.utc).isoformat()

            # Process the repository to get sorries
            repo_results = prepare_and_process_lean_repo(
                repo_url=remote_url,
                lean_data=lean_data,
                branch=commit["branch"]
            )

            # Generate a UUID for each sorry
            for sorry in repo_results["sorries"]:
                sorry["uuid"] = str(uuid.uuid4())
            
            # Create a new commit entry
            commit_entry = {
                "sha": repo_results["metadata"]["sha"],
                "branch": commit["branch"],
                "time_visited": time_visited,
                "lean_version": repo_results["metadata"].get("lean_version"),
                "sorries": repo_results["sorries"]
            }
            
            # Compute statistics for this commit's sorries
            commit_stats = compute_new_sorries_stats(repo_results["sorries"])
            
            # Add stats to the new_sorries_stats dictionary using commit SHA as key
            new_sorries_stats[commit_entry["sha"]] = commit_stats
            
            # Add the commit entry to the repository
            database["repos"][repo_index]["commits"].append(commit_entry)
            
            logger.info(f"Added new commit {commit_entry['sha']} with {commit_stats['count']} sorries")
            
        except Exception as e:
            logger.error(f"Error processing repository {remote_url}: {e}")
            logger.exception(e)
            # Continue with next commit
            continue
    return new_sorries_stats


def update_database(database_path: Path, write_database_path: Optional[Path] = None, lean_data: Optional[Path] = None, stats_file: Optional[Path] = None) -> dict:
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

    # Load the existing database
    database = load_database(database_path)

    update_database_stats = {}
    
    # Iterate through repositories in the database
    for repo_index, repo in enumerate(database["repos"]):
        remote_url = repo["remote_url"]
        logger.info(f"Checking repository for new commits: {remote_url}")
        
        # Get the current hash of remote heads
        current_hash = remote_heads_hash(remote_url)
        if current_hash is None:
            logger.warning(f"Could not get remote heads hash for {remote_url}, skipping")
            continue
        
        # Check if the hash has changed
        if current_hash == repo["remote_heads_hash"]:
            logger.info(f"No changes detected for {remote_url}, skipping")
            continue
        
        logger.info(f"New commits detected for {remote_url}, processing...")

        # Get all leaf commits
        all_commits = leaf_commits(remote_url)
        
        # Filter commits after last visited date
        last_visited = datetime.datetime.fromisoformat(repo["last_time_visited"])
        filtered_commits = []
        
        for commit in all_commits:
            # Parse the commit date
            commit_date = datetime.datetime.fromisoformat(commit["date"])
            
            # Only include commits that are newer than the last visited date
            if commit_date > last_visited:
                filtered_commits.append(commit)
                logger.info(f"Including new commit {commit['sha']} on branch {commit['branch']} from {commit_date.isoformat()}")
            else:
                logger.debug(f"Skipping old commit {commit['sha']} on branch {commit['branch']} from {commit_date.isoformat()}")
        
        logger.info(f"Filtered {len(all_commits)} commits to {len(filtered_commits)} new commits after {last_visited.isoformat()}")
        
        # Update the last_time_visited timestamp
        current_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
        database["repos"][repo_index]["last_time_visited"] = current_time
        
        # Update the remote_heads_hash
        database["repos"][repo_index]["remote_heads_hash"] = current_hash

        if lean_data is None:
            with tempfile.TemporaryDirectory() as temp_dir:
                logger.info(f"Using temporary directory for lean data: {temp_dir}")
                new_sorry_stats = process_new_commits(database, repo_index, filtered_commits, remote_url, Path(temp_dir))
        else:
            # If lean_data is provided, make sure it exists
            lean_data = Path(lean_data)
            lean_data.mkdir(exist_ok=True)
            logger.info(f"Using non-temporary directory for lean data: {lean_data}")
            new_sorry_stats = process_new_commits(database, repo_index, filtered_commits, remote_url, lean_data)

        # add the repo's stats to the stats dict
        update_database_stats[remote_url] = new_sorry_stats
    
    # Write the updated database back to the file
    logger.info(f"Writing updated database to {write_database_path}")
    with open(write_database_path, 'w') as f:
        json.dump(database, f, indent=2)
    logger.info("Database update completed successfully")

    # Write database statistics if file is provided
    if stats_file:
        stats_path = Path(stats_file)
        with open(stats_path, 'w') as f:
            json.dump(update_database_stats, f, indent=2)
        logger.info(f"Update statistics written to {stats_path}")

    return update_database_stats
