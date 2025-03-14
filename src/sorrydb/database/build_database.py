import datetime
import subprocess
import json
from pathlib import Path
import hashlib
import logging
from typing import Optional
import uuid
import tempfile
from sorrydb.crawler.git_ops import get_git_blame_info, get_repo_metadata, leaf_commits, prepare_repository, remote_heads_hash
from sorrydb.repro.repl_api import LeanRepl, get_goal_parent_type, setup_repl

# Create a module-level logger
logger = logging.getLogger(__name__)

def hash_string(s: str) -> str:
    """Create a truncated SHA-256 hash of a string.
    Returns first 12 characters of the hex digest."""
    return hashlib.sha256(s.encode()).hexdigest()[:12]

def build_lean_project(repo_path: Path, timeout: int = 600) -> list[Path] | None:
    """Run lake commands to build the Lean project.
    
    Args:
        repo_path: Path to the repository root
        timeout: Timeout in seconds for the lake build command (default: 600)
    
    Returns:
        List of relative paths to Lean files containing sorries
        None if build failed or could not read `lake-manifest.json`
    """

    # Check if the project uses mathlib4
    use_cache = False
    manifest_path = repo_path / "lake-manifest.json"
    if manifest_path.exists():
        try:
            manifest_content = manifest_path.read_text()
            if "https://github.com/leanprover-community/mathlib4" in manifest_content:
                use_cache = True
                logger.debug("Project uses mathlib4, will get build cache")
            elif "\"name\": \"mathlib\"" in manifest_content:
                use_cache = True
                logger.debug("Mathlib4 branch, will get build cache")
        except Exception as e:
            logger.warning(f"Could not read lake-manifest.json: {e}")
            return None
    
    # Only get build cache if the project uses mathlib4
    if use_cache:
        logger.info("Getting build cache...")
        result = subprocess.run(["lake", "exe", "cache", "get"], cwd=repo_path)
        if result.returncode != 0:
            logger.warning("lake exe cache get failed, continuing anyway")
    else:
        logger.debug("Project does not use mathlib4, skipping build cache step")
    
    logger.info(f"Building project with timeout of {timeout} seconds...")
    try:
        # Run lake build with the specified timeout
        result = subprocess.run(
            ["lake", "build"], 
            cwd=repo_path, 
            capture_output=True, 
            text=True, 
            timeout=timeout
        )
    except subprocess.TimeoutExpired:
        logger.warning(f"lake build timed out after {timeout} seconds")
        return None

    # Check for build failure
    if result.returncode != 0:
        logger.warning("lake build failed")
        return None
    
    # Extract paths to files containing sorries from build output
    # Sample output line: 
    # warning: ././././SorryClientTestRepo/Basic.lean:4:8: declaration uses 'sorry'
    sorry_files = []
    if result.stdout:
        for line in result.stdout.splitlines():
            if "declaration uses 'sorry'" in line:
                if line.startswith("warning: "):
                    line = line[9:]
                file_path_str = line.split(":", 1)[0]
                file_path = Path(file_path_str)
                full_path = repo_path / file_path                
                if file_path not in sorry_files:
                    if full_path.exists():
                        logger.debug(f"Found sorry file: {file_path}")
                        sorry_files.append(file_path)
                    else:
                        logger.warning(f"Could not find file: {full_path}")
    
    logger.info(f"Found {len(sorry_files)} files containing sorries from build output")
    return sorry_files

def find_sorries_in_file(relative_path: Path, repl: LeanRepl) -> list | None:
    """Find sorries in a Lean file using the REPL.
            
    Returns:
        List of sorries, where each sorry is a dict containing:
            - proofState: int, repl identifier for the proof state at the sorry
            - pos, endPos: dicts with line and column of the sorry's start and end positions
            - goal: str, the goal at the sorry position
        Returns None if no sorries found
    """
    logger.info(f"Using REPL to find sorries in {relative_path}...")

    command = {"path": str(relative_path), "allTactics": True}
    output = repl.send_command(command)
    
    if output is None:
        logger.warning("REPL returned no output")
        return None
        
    if "error" in output:
        logger.warning(f"REPL error: {output['error']}")
        return None
        
    if "sorries" not in output:
        logger.info("REPL output missing 'sorries' field")
        return None
    
    logger.info(f"REPL found {len(output['sorries'])} sorries")
    return output["sorries"]

def should_process_file(lean_file: Path) -> bool:
    """Check if file potentially contains sorries.
    Not strictly needed, but speeds up processing by filtering out files
    that don't need to be processed by REPL.
    """
    text = lean_file.read_text()
    return any(term in text for term in ["sorry"])

def process_lean_file(relative_path: Path, repo_path: Path, repl_binary: Path) -> list | None:
    """Process a Lean file to find sorries and their proof states.
    
    Returns:
        List of sorries, each containing:
            - goal: dict with goal information
                - type: str, the goal at the sorry position
                - parentType: str, the parent type of the goal (if available)
                - hash: str, hash of the goal string for duplicate detection
            - location: dict with position information
                - file: str, relative path to the file
                - startLine: int, starting line number
                - startColumn: int, starting column number
                - endLine: int, ending line number
                - endColumn: int, ending column number
            - blame: dict, git blame information for the sorry line
        Returns None if no sorries found
    """
    
    with LeanRepl(repo_path, repl_binary) as repl:
        # First get all sorries in the file
        sorries = find_sorries_in_file(relative_path, repl)
        if not sorries:
            return None
            
        # For each sorry, get its full proof state using the same REPL instance
        results = []
        num_prop_sorries = 0
        for sorry in sorries:
            # Get the parent type of the goal
            parent_type = get_goal_parent_type(repl, sorry["proofState"])
            
            # Structure the sorry information
            structured_sorry = {
                "goal": {
                    "type": sorry["goal"],
                    "hash": hash_string(sorry["goal"])
                },
                "location": {
                    "startLine": sorry["pos"]["line"],
                    "startColumn": sorry["pos"]["column"],
                    "endLine": sorry["endPos"]["line"],
                    "endColumn": sorry["endPos"]["column"]
                },
                "blame": get_git_blame_info(repo_path, relative_path, sorry["pos"]["line"])
            }
            
            # Add parent type if available
            if parent_type:
                structured_sorry["goal"]["parentType"] = parent_type
                if parent_type == "Prop":
                    num_prop_sorries += 1
                
            results.append(structured_sorry)
            
        logger.info(f"Found {num_prop_sorries} Prop sorries in {relative_path}")
        return results

def process_lean_repo(repo_path: Path, lean_data: Path, version_tag: str | None = None, sorry_files: list[Path] | None = None) -> list:
    """Process all Lean files in a repository using the REPL.
    
    Args:
        repo_path: Path to the repository root
        lean_data: Path to the lean data directory
        version_tag: Optional Lean version tag to use for REPL
        sorry_files: List of paths to files containing sorries
    
    Returns:
        List of sorries, each containing:
            - goal: dict with goal information
                - type: str, the goal at the sorry position
                - parentType: str, the parent type of the goal (if available)
                - hash: str, hash of the goal string for duplicate detection
            - location: dict with position information
                - file: str, relative path to the file
                - startLine: int, starting line number
                - startColumn: int, starting column number
                - endLine: int, ending line number
                - endColumn: int, ending column number
            - blame: dict, git blame information for the sorry line
    """
    
    # Build list of files to process
    if sorry_files is None:
        logger.warning("No sorry files provided, processing lean files containing 'sorry' string")
        lean_files = [f for f in repo_path.rglob("*.lean") 
                      if ".lake" not in f.parts and should_process_file(f)]
    else:
        lean_files = sorry_files

    if len(lean_files) == 0:
        logger.info("No files with potential sorries found, returning empty list")
        return []

    logger.info(f"Found {len(lean_files)} files containing potential sorries")

    repl_binary = setup_repl(lean_data, version_tag)
    
    results = []
    for rel_path in lean_files:
        sorries = process_lean_file(rel_path, repo_path, repl_binary)
        if sorries:
            logger.info(f"Found {len(sorries)} sorries in {rel_path}")
            for sorry in sorries:
                sorry["location"]["file"] = str(rel_path)
                results.append(sorry)
        else:
            logger.info(f"No sorries found in {rel_path} (REPL processing failed or returned no results)")
    
    logger.info(f"Total sorries found: {len(results)}")
    return results


def get_repo_lean_version(repo_path: Path) -> str:
    """
    Extract the Lean version from the lean-toolchain file in the repository.
    
    Args:
        repo_path: Path to the repository root
        
    Returns:
        str: The Lean version (e.g., 'v4.17.0-rc1')
        
    Raises:
        FileNotFoundError: If the lean-toolchain file doesn't exist
        ValueError: If the lean-toolchain file has an unexpected format
        IOError: If there's an error reading the file
    """
    toolchain_path = repo_path / "lean-toolchain"
    
    if not toolchain_path.exists():
        logger.warning(f"No lean-toolchain file found at {toolchain_path}")
        raise FileNotFoundError(f"No lean-toolchain file found at {toolchain_path}")
    
    try:
        # Read the lean-toolchain file
        toolchain_content = toolchain_path.read_text().strip()
        
        # The format of lean-toolchain is "leanprover/lean4:v4.17.0-rc1"
        # Extract the version part after the colon
        if ':' in toolchain_content:
            lean_version = toolchain_content.split(':', 1)[1]
            logger.info(f"Extracted lean version {lean_version} from {toolchain_path}")
            return lean_version
        else:
            logger.warning(f"Unexpected format in lean-toolchain: {toolchain_content}")
            raise ValueError(f"Unexpected format in lean-toolchain: {toolchain_content}")
            
    except IOError as e:
        logger.warning(f"Error reading lean-toolchain file: {e}")
        raise IOError(f"Error reading lean-toolchain file: {e}")


def prepare_and_process_lean_repo(repo_url: str, lean_data: Path | None = None, branch: str | None = None, timeout: int = 600) -> dict | None:
    """
    Comprehensive function that prepares a repository, builds a Lean project, 
    processes it to find sorries, and collects repository metadata.
    
    Args:
        repo_url: Git remote URL (HTTPS or SSH) of the repository to process
        lean_data: Path in which to  create temporary directory for repository (default: system temp directory)
        branch: Optional branch to checkout (default: repository default branch)
        timeout: Timeout in seconds for the lake build command (default: 600)
        
    Returns:
        dict: A dictionary containing repository metadata and sorries information
        None if failed to build or process the repository
    """
    # Use a temporary directory to host the repository
    with tempfile.TemporaryDirectory(dir=lean_data) as temp_dir:
        logger.debug(f"Using temporary directory for lean data: {temp_dir}")
        return _process_repo_with_lean_data(repo_url, branch, Path(temp_dir), timeout)

def _process_repo_with_lean_data(repo_url: str, branch: str | None, lean_data: Path, timeout: int = 600) -> dict | None:
    """
    Helper function that does the actual repository processing with a given lean_data directory.
    
    Args:
        repo_url: Git remote URL (HTTPS or SSH) of the repository to process
        branch: Optional branch to checkout (default: repository default branch)
        lean_data: Path to the lean data directory
        timeout: Timeout in seconds for the lake build command (default: 600)
    """
    if branch:
        logger.info(f"Processing respository: {repo_url}, branch: {branch}")
    else:
        logger.info(f"Processing respository: {repo_url}")
    
    # Prepare the repository (clone/checkout)
    checkout_path = prepare_repository(repo_url, branch, None, lean_data)
    if not checkout_path:
        logger.warning(f"Failed to check out repository: {repo_url}, branch: {branch}")
        return None
    
    # Build the Lean project
    sorry_files = build_lean_project(checkout_path, timeout)
    if sorry_files is None:
        logger.warning(f"Failed to build Lean project: {repo_url}, branch: {branch}")
        return None

    # Get Lean version from repo
    try:
        lean_version = get_repo_lean_version(checkout_path)
    except (FileNotFoundError, ValueError, IOError) as e:
        logger.warning(f"Encountered error when trying to get lean version: {e}")
        logger.info("Continuing without specific Lean version")
        lean_version = None
    
    # Process Lean files to find sorries
    sorries = process_lean_repo(checkout_path, lean_data, lean_version, sorry_files)
    
    # Get repository metadata and add lean_version
    metadata = get_repo_metadata(checkout_path)
    metadata["lean_version"] = lean_version
    
    # Combine results
    results = {
        "metadata": metadata,
        "sorries": sorries,
    }
    
    logger.info(f"Found {len(sorries)} sorries in {repo_url}, branch: {branch}")
    return results

    
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


def update_database(database_path: Path, lean_data: Optional[Path] = None, timeout: int = 600):
    """
    Update a SorryDatabase by checking for changes in repositories and processing new commits.
    
    Args:
        database_path: Path to the database JSON file
        lean_data: Path to the lean data directory (default: create temporary directory)
        timeout: Timeout in seconds for the lake build command (default: 600)
    """

    # Load the existing database
    database = load_database(database_path)
    
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
        last_visited_str = repo["last_time_visited"]
        last_visited = datetime.datetime.fromisoformat(last_visited_str)
        logger.debug(f"Last visited datestring: {last_visited_str}")
        filtered_commits = []
            
        for commit in all_commits:
            # Parse the commit date
            commit_date_str = commit["date"]
            commit_date = datetime.datetime.fromisoformat(commit_date_str)
            logger.debug(f"Commit datestring: {commit_date_str}")
            
            # Only include commits that are newer than the last visited date
            if commit_date > last_visited:
                filtered_commits.append(commit)
                logger.debug(f"Including new commit {commit['sha']} on branch {commit['branch']} from {commit_date.isoformat()}")
            else:
                logger.debug(f"Skipping old commit {commit['sha']} on branch {commit['branch']} from {commit_date.isoformat()}")
        
        logger.info(f"Filtered {len(all_commits)} commits to {len(filtered_commits)} new commits after {last_visited.isoformat()}")
        
        # Update the last_time_visited timestamp
        current_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
        database["repos"][repo_index]["last_time_visited"] = current_time
        
        # Update the remote_heads_hash
        database["repos"][repo_index]["remote_heads_hash"] = current_hash

        for commit in filtered_commits:
            logger.debug(f"processing commit on {remote_url}: {commit}")
            try:
                # Process the repository to get sorries
                repo_results = prepare_and_process_lean_repo(
                    repo_url=remote_url,
                    lean_data=lean_data,
                    branch=commit["branch"],
                    timeout=timeout
                )
                if repo_results is None:
                    logger.warning(f"Failed to process repository {remote_url}, skipping commit {commit['sha']}")
                    continue

                # Generate a UUID for each sorry
                for sorry in repo_results["sorries"]:
                    sorry["uuid"] = str(uuid.uuid4())
                
                # Create a new commit entry
                commit_entry = {
                    "sha": repo_results["metadata"]["sha"],
                    "branch": commit["branch"],
                    "time_visited": current_time,
                    "lean_version": repo_results["metadata"].get("lean_version"),
                    "sorries": repo_results["sorries"]
                }
                    
                
                # Add the commit entry to the repository
                database["repos"][repo_index]["commits"].append(commit_entry)
                
                logger.info(f"Added new commit {commit_entry['sha']} with {len(commit_entry['sorries'])} sorries")
                
            except Exception as e:
                logger.warning(f"Error processing repository {remote_url}: {e}")
                logger.exception(e)
                # Continue with next repository
                continue
    
    # Write the updated database back to the file
    logger.info(f"Writing updated database to {database_path}")
    with open(database_path, 'w') as f:
        json.dump(database, f, indent=2)
    logger.info("Database update completed successfully")
