from pathlib import Path
import shutil
from git import Repo
from typing import Optional, Dict
import tempfile
import subprocess
from datetime import datetime, timezone
import logging
import git.cmd
import hashlib

# Create a module-level logger
logger = logging.getLogger(__name__)

def get_repo_metadata(repo_path: Path) -> Dict:
    """Get essential metadata about the repository state for reproducibility.
    
    Args:
        repo_path: Path to the local repository
        
    Returns:
        Dict containing:
            - commit_time: ISO formatted UTC timestamp of when the commit was made
            - remote_url: URL of the origin remote
            - sha: full commit hash
            - branch: current branch name or HEAD if detached
    """
    repo = Repo(repo_path)
    commit = repo.head.commit
    
    # Get remote URL
    remote_url = repo.remotes.origin.url
    if remote_url.endswith('.git'):
        remote_url = remote_url[:-4]
    
    # Get current branch or HEAD if detached
    try:
        current_branch = repo.active_branch.name
    except TypeError:  # HEAD is detached
        current_branch = 'HEAD'
    
    return {
        "commit_time": commit.committed_datetime.isoformat(),
        "remote_url": remote_url,
        "sha": commit.hexsha,
        "branch": current_branch
    }

def get_git_blame_info(repo_path: Path, file_path: Path, line_number: int) -> dict:
    """Get git blame information for a specific line."""
    repo = Repo(repo_path)
    blame = repo.blame('HEAD', str(file_path), L=f"{line_number},{line_number}")[0]
    commit = blame[0]
    return {
        "commit": commit.hexsha,
        "author": commit.author.name,
        "author_email": commit.author.email,
        "date": commit.authored_datetime.isoformat(),
        "summary": commit.summary
    }

def get_head_sha(remote_url: str, branch: str = None) -> str:
    """Get the HEAD SHA of a branch."""
    with tempfile.TemporaryDirectory() as temp_dir:
        repo = Repo.clone_from(
            remote_url,
            temp_dir,
            branch=branch,
            depth=1
        )
        return repo.head.commit.hexsha

def prepare_repository(remote_url: str, branch: str, head_sha: str, lean_data: Path) -> Optional[Path]:
    """Clone repository at specific commit into lean-data directory.
    
    Args:
        remote_url: Git remote URL (HTTPS or SSH)
        branch: Branch name
        head_sha: Commit SHA to checkout
        lean_data: Base directory for checkouts
    
    Returns:
        Path to checked out repository or None if failed
    """
    if head_sha is None:
        head_sha = get_head_sha(remote_url, branch)
    
    checkout_path = lean_data / head_sha
    
    # If directory exists and has correct commit checked out, we're done
    if checkout_path.exists():
        try:
            repo = Repo(checkout_path)
            if repo.head.commit.hexsha == head_sha:
                logger.info(f"Repository already exists at correct commit {head_sha}")
                return checkout_path
        except Exception:
            pass
    
    # Clean up if directory exists but wrong commit
    if checkout_path.exists():
        shutil.rmtree(checkout_path)
    
    try:
        # Clone repository
        logger.info(f"Cloning {remote_url} branch {branch}...")
        repo = Repo.clone_from(
            remote_url,
            checkout_path,
            branch=branch,
            single_branch=True
        )
        
        # Checkout specific commit
        logger.info(f"Checking out {head_sha}...")
        repo.git.checkout(head_sha)
        
        return checkout_path
        
    except Exception as e:
        logger.error(f"Error preparing repository: {e}")
        # Clean up on failure
        if checkout_path.exists():
            shutil.rmtree(checkout_path)
        return None

def get_default_branch(repo_path: Path) -> str:
    """Get the default branch of the repository."""
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo_path,
        capture_output=True,
        text=True
    )
    return result.stdout.strip()

def remote_heads(remote_url: str) -> list[dict]:
    """Get all branch heads from a remote repository.
    
    Args:
        remote_url: Git remote URL (HTTPS or SSH)
        
    Returns:
        List of dicts, each containing:
            - branch: name of the branch
            - sha: SHA of the HEAD commit
    """
    try:
        # Use git.cmd.Git for running git commands directly
        logger.debug(f"Getting remote heads for {remote_url}")
        git_cmd = git.cmd.Git()
        logger.debug(f"Running git command: git ls-remote --heads {remote_url}")
        output = git_cmd.ls_remote('--heads', remote_url)
        
        # Parse the output into a list of dicts
        heads = []
        for line in output.splitlines():
            if not line.strip():
                continue
            
            # Each line is of format: "<sha>\trefs/heads/<branch>"
            sha, ref = line.split('\t')
            branch = ref.replace('refs/heads/', '')
            
            heads.append({
                'branch': branch,
                'sha': sha
            })
        if len(heads) == 0:
            logger.warning(f"No branches found for {remote_url}")
        else:
            logger.debug(f"Found {len(heads)} branches in {remote_url}")
        return heads
        
    except Exception as e:
        logger.error(f"Error getting remote heads for {remote_url}: {e}")
        return [] 

def remote_heads_hash(remote_url: str) -> str | None:
    """Get a hash of the (sorted) set of unique branch heads in a remote repository.
    
    Args:
        remote_url: Git remote URL (HTTPS or SSH)
        
    Returns:
        First 12 characters of SHA-256 hash of sorted set of unique head SHAs, or None if error
    """
    try:
        heads = remote_heads(remote_url)
        if not heads:
            return None
        
        # Extract unique SHAs and sort them
        shas = sorted(set(head['sha'] for head in heads))
        # Join them with a delimiter and hash
        combined = '_'.join(shas)
        return hashlib.sha256(combined.encode()).hexdigest()[:12]
        
    except Exception as e:
        logger.error(f"Error computing sorted hash of remote heads for {remote_url}: {e}")
        return None
