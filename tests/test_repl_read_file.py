#!/usr/bin/env python3

import json
import logging
import tempfile
from pathlib import Path

import pytest
from utils.repl_ops import LeanRepl, setup_repl

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_lean_version(repo_dir: Path) -> str:
    """Extract Lean version from lean-toolchain file."""
    toolchain_path = repo_dir / "lean-toolchain"
    if not toolchain_path.exists():
        return None
    try:
        toolchain_content = toolchain_path.read_text().strip()
        if ":" in toolchain_content:
            return toolchain_content.split(":", 1)[1]
        return None
    except Exception as e:
        logger.error(f"Error reading lean-toolchain file: {e}")
        return None


def gather_sorries_from_repo(repo_dir: Path) -> list:
    """Gather all sorries from Lean files in a repository."""
    # Get all .lean files in the repo
    lean_files = list(repo_dir.glob("**/*.lean"))
    logger.info(f"Found {len(lean_files)} Lean files in {repo_dir}")

    # Get Lean version from lean-toolchain
    lean_version = get_lean_version(repo_dir)

    # Create a temporary directory for building the REPL
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        repl_binary = setup_repl(temp_path, lean_version)
        all_sorries = []

        for lean_file in lean_files:
            relative_path = lean_file.relative_to(repo_dir)
            with LeanRepl(repo_dir, repl_binary) as repl:
                sorries = repl.read_file(relative_path)
                if sorries is None:
                    continue

                for sorry in sorries:
                    sorry_entry = {
                        "location": {
                            "file": str(relative_path),
                            "start_line": sorry["location"]["start_line"],
                            "start_column": sorry["location"]["start_column"],
                            "end_line": sorry["location"]["end_line"],
                            "end_column": sorry["location"]["end_column"],
                        },
                        "goal": sorry["goal"],
                        "proof_state_id": sorry["proof_state_id"],
                    }
                    all_sorries.append(sorry_entry)

    return all_sorries


def test_sorries_match():
    """Test that gathered sorries match the precompiled ones."""
    # Get the mock repository directory and precompiled sorries file
    repo_dir = Path(__file__).parent / "mock_lean_repository"
    precompiled_file = Path(__file__).parent / "mock_lean_repository_sorries.json"

    # Load precompiled sorries
    with open(precompiled_file) as f:
        precompiled_sorries = json.load(f)

    # Gather sorries from the repository
    gathered_sorries = gather_sorries_from_repo(repo_dir)

    # Compare the length of the two lists
    assert len(gathered_sorries) == len(precompiled_sorries), (
        f"Found {len(gathered_sorries)} sorries but expected {len(precompiled_sorries)}"
    )

    # Convert both lists to sets of strings for unorderedcomparison
    gathered_set = {json.dumps(sorry, sort_keys=True) for sorry in gathered_sorries}
    precompiled_set = {
        json.dumps(sorry, sort_keys=True) for sorry in precompiled_sorries
    }

    assert gathered_set == precompiled_set, (
        "Gathered sorries don't match precompiled ones"
    )
