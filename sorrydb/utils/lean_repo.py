#!/usr/bin/env python3

import logging
import subprocess
from pathlib import Path

# Create a module-level logger
logger = logging.getLogger(__name__)


LAKE_BUILD_TIMEOUT = 60 * 30  # 30 minutes in seconds


class LakeTimeoutError(Exception):
    """Exception raised when the lake build process exceeds the timeout."""

    pass


def lake_build_with_timeout(repo_path: Path):
    """Run 'lake build' with a timeout.

    Args:
        repl_dir: Directory where the lake build command should run.
        timeout: Timeout in seconds for the build process.

    Raises:
        LakeTimeoutException: If the build process exceeds the timeout.
        Exception: If the build process fails for other reasons.
    """
    try:
        subprocess.run(
            ["lake", "build"], cwd=repo_path, timeout=LAKE_BUILD_TIMEOUT, check=True
        )
    except subprocess.TimeoutExpired as e:
        raise LakeTimeoutError("Lake build process exceeded the timeout.") from e
    except subprocess.CalledProcessError as e:
        logger.error("Failed to build REPL")
        raise Exception(f"Lake build process failed with return code {e.returncode}.")


def build_lean_project(repo_path: Path):
    """
    Run lake commands to build the Lean project.

    Args:
        repo_path: Path to the Lean project.
    """
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
    lake_build_with_timeout(repo_path)
