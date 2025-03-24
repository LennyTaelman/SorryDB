import hashlib
import logging
import subprocess
from pathlib import Path

from sorrydb.crawler.git_ops import (
    get_git_blame_info,
    get_repo_metadata,
    prepare_repository,
)
from sorrydb.repro.repl_api import LeanRepl, get_goal_parent_type, setup_repl

# Create a module-level logger
logger = logging.getLogger(__name__)


def hash_string(s: str) -> str:
    """Create a truncated SHA-256 hash of a string.
    Returns first 12 characters of the hex digest."""
    return hashlib.sha256(s.encode()).hexdigest()[:12]


def build_lean_project(repo_path: Path):
    """Run lake commands to build the Lean project."""
    # Check if the project uses mathlib4
    use_cache = False
    manifest_path = repo_path / "lake-manifest.json"
    if manifest_path.exists():
        try:
            manifest_content = manifest_path.read_text()
            if "https://github.com/leanprover-community/mathlib4" in manifest_content:
                use_cache = True
                logger.info("Project uses mathlib4, will get build cache")
            elif '"name": "mathlib"' in manifest_content:
                use_cache = True
                logger.info(
                    "Project appears to be mathlib4 branch, will get build cache"
                )
        except Exception as e:
            logger.warning(f"Could not read lake-manifest.json: {e}")

    # Only get build cache if the project uses mathlib4
    if use_cache:
        logger.info("Getting build cache...")
        result = subprocess.run(["lake", "exe", "cache", "get"], cwd=repo_path)
        if result.returncode != 0:
            logger.warning("lake exe cache get failed, continuing anyway")
    else:
        logger.info("Project does not use mathlib4, skipping build cache step")

    logger.info("Building project...")
    result = subprocess.run(["lake", "build"], cwd=repo_path)
    if result.returncode != 0:
        logger.error("lake build failed")
        raise Exception("lake build failed")


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


def process_lean_file(
    relative_path: Path, repo_path: Path, repl_binary: Path
) -> list | None:
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
        for sorry in sorries:
            # Get the parent type of the goal
            parent_type = get_goal_parent_type(repl, sorry["proofState"])

            # Structure the sorry information
            structured_sorry = {
                "goal": {"type": sorry["goal"], "hash": hash_string(sorry["goal"])},
                "location": {
                    "startLine": sorry["pos"]["line"],
                    "startColumn": sorry["pos"]["column"],
                    "endLine": sorry["endPos"]["line"],
                    "endColumn": sorry["endPos"]["column"],
                },
                "blame": get_git_blame_info(
                    repo_path, relative_path, sorry["pos"]["line"]
                ),
            }

            # Add parent type if available
            if parent_type:
                structured_sorry["goal"]["parentType"] = parent_type

            results.append(structured_sorry)

        return results


def process_lean_repo(
    repo_path: Path, lean_data: Path, version_tag: str | None = None
) -> list:
    """Process all Lean files in a repository using the REPL.

    Args:
        repo_path: Path to the repository root
        lean_data: Path to the lean data directory

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
    repl_binary = setup_repl(lean_data, version_tag)

    # Build list of files to process
    lean_files = [
        (f.relative_to(repo_path), f)
        for f in repo_path.rglob("*.lean")
        if ".lake" not in f.parts and should_process_file(f)
    ]

    logger.info(f"Found {len(lean_files)} files containing potential sorries")

    results = []
    for rel_path, abs_path in lean_files:
        sorries = process_lean_file(rel_path, repo_path, repl_binary)
        if sorries:
            logger.info(f"Found {len(sorries)} sorries in {rel_path}")
            for sorry in sorries:
                sorry["location"]["file"] = str(rel_path)
                results.append(sorry)
        else:
            logger.info(
                f"No sorries found in {rel_path} (REPL processing failed or returned no results)"
            )

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
        if ":" in toolchain_content:
            lean_version = toolchain_content.split(":", 1)[1]
            logger.info(f"Extracted lean version {lean_version} from {toolchain_path}")
            return lean_version
        else:
            logger.warning(f"Unexpected format in lean-toolchain: {toolchain_content}")
            raise ValueError(
                f"Unexpected format in lean-toolchain: {toolchain_content}"
            )

    except IOError as e:
        logger.warning(f"Error reading lean-toolchain file: {e}")
        raise IOError(f"Error reading lean-toolchain file: {e}")


def prepare_and_process_lean_repo(
    repo_url: str, lean_data: Path, branch: str | None = None
):
    """
    Comprehensive function that prepares a repository, builds a Lean project,
    processes it to find sorries, and collects repository metadata.

    Args:
        repo_url: Git remote URL (HTTPS or SSH) of the repository to process
        branch: Optional branch to checkout (default: repository default branch)
        lean_data: Path to the lean data directory
        lean_version_tag: Optional Lean version tag to use for REPL

    Returns:
        dict: A dictionary containing repository metadata and sorries information
    """
    logger.info(f"Processing repository: {repo_url}")
    if branch:
        logger.info(f"Using branch: {branch}")

    # Prepare the repository (clone/checkout)
    checkout_path = prepare_repository(repo_url, branch, None, lean_data)
    if not checkout_path:
        logger.error(f"Failed to prepare repository: {repo_url}")
        raise Exception(f"Failed to prepare repository: {repo_url}")

    # Build the Lean project
    build_lean_project(checkout_path)

    # Get Lean version from repo
    try:
        lean_version = get_repo_lean_version(checkout_path)
    except (FileNotFoundError, ValueError, IOError) as e:
        logger.warning(f"Encountered error when trying to get lean version: {e}")
        logger.info("Continuing without specific Lean version")
        lean_version = None

    # Process Lean files to find sorries
    sorries = process_lean_repo(checkout_path, lean_data, lean_version)

    # Get repository metadata and add lean_version
    metadata = get_repo_metadata(checkout_path)
    metadata["lean_version"] = lean_version

    # Combine results
    results = {
        "metadata": metadata,
        "sorries": sorries,
    }

    logger.info(f"Database build complete. Found {len(sorries)} sorries.")
    return results
