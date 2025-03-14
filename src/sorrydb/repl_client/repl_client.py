#!/usr/bin/env python3

import json
import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from sorrydb.repro.repl_api import LeanRepl, setup_repl
from sorrydb.crawler.git_ops import prepare_repository
from sorrydb.database.build_database import build_lean_project

# Create a module-level logger
logger = logging.getLogger(__name__)

def load_sorry_json(json_path: Path) -> Dict:
    """Load a sorry JSON file.
    
    Args:
        json_path: Path to the sorry JSON file
        
    Returns:
        Dict containing the sorry data
        
    Raises:
        FileNotFoundError: If the JSON file doesn't exist
        json.JSONDecodeError: If the JSON file is invalid
    """
    logger.info(f"Loading sorry JSON from {json_path}")
    try:
        with open(json_path, 'r') as f:
            sorry_data = json.load(f)
        return sorry_data
    except FileNotFoundError:
        logger.error(f"Sorry JSON file not found: {json_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in sorry file: {json_path}")
        raise

def find_sorry_proof_state(repl: LeanRepl, file_path: Path, sorry_location: Dict) -> Tuple[int, str]:
    """Find the proof state ID for a sorry in a Lean file.
    
    Args:
        repl: An active REPL instance
        file_path: Path to the Lean file
        sorry_location: Dict containing the sorry location information
        
    Returns:
        Tuple of (proof_state_id, goal_type)
        
    Raises:
        Exception: If the sorry cannot be found or verified
    """
    logger.info(f"Finding sorry proof state in {file_path}...")
    
    command = {"path": str(file_path), "allTactics": True}
    output = repl.send_command(command)
    
    if output is None:
        logger.error("REPL returned no output")
        raise Exception("REPL returned no output")
        
    if "error" in output:
        logger.error(f"REPL error: {output['error']}")
        raise Exception(f"REPL error: {output['error']}")
        
    if "sorries" not in output:
        logger.error("REPL output missing 'sorries' field")
        raise Exception("REPL output missing 'sorries' field")
    
    sorries = output["sorries"]
    logger.info(f"REPL found {len(sorries)} sorries in {file_path}")
    
    # Find the sorry that matches the location
    for sorry in sorries:
        if (sorry["pos"]["line"] == sorry_location["startLine"] and 
            sorry["pos"]["column"] == sorry_location["startColumn"] and
            sorry["endPos"]["line"] == sorry_location["endLine"] and
            sorry["endPos"]["column"] == sorry_location["endColumn"]):
            
            logger.info(f"Found matching sorry at line {sorry_location['startLine']}")
            return sorry["proofState"], sorry["goal"]
    logger.error(f"Could not find matching sorry")
    raise Exception(f"Could not find sorry at specified location: {sorry_location}")

def _process_sorry_with_lean_data(
    remote_url: str, 
    commit_sha: str, 
    branch: str, 
    file_path: str, 
    location: Dict, 
    lean_version: str,
    lean_data: Path,
    sorry_data: Dict
) -> str:
    """Helper function that does the actual sorry processing with a given lean_data directory.
    
    Args:
        remote_url: Git remote URL
        commit_sha: Commit SHA to checkout
        branch: Branch name
        file_path: Path to the Lean file containing the sorry
        location: Dict containing the sorry location information
        lean_version: Lean version to use
        lean_data: Path to store Lean data
        sorry_data: Original sorry data from JSON
        
    Returns:
        String containing the actual goal type from REPL
        
    Raises:
        Exception: If the sorry cannot be verified or processed
    """
    # Prepare the repository (clone/checkout)
    checkout_path = prepare_repository(remote_url, branch, commit_sha, lean_data)
    if not checkout_path:
        logger.error(f"Failed to prepare repository: {remote_url}")
        raise Exception(f"Failed to prepare repository: {remote_url}")
    
    # Build the Lean project
    build_lean_project(checkout_path)
    
    # Setup REPL
    repl_binary = setup_repl(lean_data, lean_version)
    
    # Find the sorry proof state
    with LeanRepl(checkout_path, repl_binary) as repl:
        try:
            proof_state_id, actual_goal = find_sorry_proof_state(repl, file_path, location)
            return actual_goal
        except Exception as e:
            logger.error(f"Error finding sorry proof state: {e}")
            raise Exception(f"Error finding sorry proof state: {e}")
                

def process_sorry_json(json_path: Path, lean_data_dir: Optional[Path] = None) -> str:
    """Process a sorry JSON file and return the actual goal string from REPL.
    
    Args:
        json_path: Path to the sorry JSON file
        lean_data_dir: Optional path to store Lean data (default: create temporary directory)
        
    Returns:
        String containing the actual goal type from REPL
    """
    # Load the sorry JSON
    sorry_data = load_sorry_json(json_path)
    
    # Extract necessary information
    try:
        remote_url = sorry_data["remote_url"]
        commit_sha = sorry_data["sha"]
        branch = sorry_data["branch"]
        file_path = sorry_data["location"]["file"]
        location = {
            "startLine": sorry_data["location"]["startLine"],
            "startColumn": sorry_data["location"]["startColumn"],
            "endLine": sorry_data["location"]["endLine"],
            "endColumn": sorry_data["location"]["endColumn"]
        }
        lean_version = sorry_data.get("lean_version")
    except KeyError as e:
        logger.error(f"Missing required field in sorry JSON: {e}")
        raise Exception(f"Missing required field in sorry JSON: {e}")
    
    # Use a temporary directory for lean data if not provided
    if lean_data_dir is None:
        with tempfile.TemporaryDirectory() as temp_dir:
            lean_data = Path(temp_dir) / "lean_data"
            lean_data.mkdir(exist_ok=True)
            # Process the sorry and return the actual goal
            return _process_sorry_with_lean_data(
                remote_url, commit_sha, branch, file_path, location, lean_version, lean_data, sorry_data
            )
    else:
        lean_data = Path(lean_data_dir)
        lean_data.mkdir(exist_ok=True, parents=True)
        # Process the sorry and return the actual goal
        return _process_sorry_with_lean_data(
            remote_url, commit_sha, branch, file_path, location, lean_version, lean_data, sorry_data
        ) 