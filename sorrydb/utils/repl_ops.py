#!/usr/bin/env python3

import json
import logging
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

from git import Repo

logger = logging.getLogger(__name__)


REPL_REPO_URL = "https://github.com/leanprover-community/repl"
PARENT_TYPE_TACTIC = 'run_tac (do let parentType ← Lean.Meta.inferType (← Lean.Elab.Tactic.getMainTarget); Lean.logInfo m!"Goal parent type: {parentType}")'


class ReplError(RuntimeError):
    """Class for error messages sent back by the REPL."""

    pass


def setup_repl(lean_data: Path, version_tag: str) -> Path:
    """Clone and build the REPL repository for the provided version tag. If the
    directory corresponding to the version tag already exists, it is assumed to
    contain a built REPL binary already.

    Args:
        lean_data: Path where the REPL should be cloned
        version_tag: git tag to checkout

    Returns:
        Path to the REPL binary
    """
    # Create a directory name that includes the version tag
    sanitized_tag = version_tag.replace(".", "_").replace("-", "_")
    repl_dir = lean_data / f"repl_{sanitized_tag}"

    if not repl_dir.exists():
        logger.info(f"Cloning REPL repository into {repl_dir}...")
        repo = Repo.clone_from(REPL_REPO_URL, repl_dir)

        logger.info(f"Checking out REPL at tag: {version_tag}")
        repo.git.checkout(version_tag)

        logger.info("Building REPL...")
        result = subprocess.run(["lake", "build"], cwd=repl_dir)

        if result.returncode != 0:
            raise RuntimeError(
                "Failed to build REPL. Lake build returned: %s", result.stderr
            )

    repl_binary = repl_dir / ".lake" / "build" / "bin" / "repl"
    if not repl_binary.exists():
        raise FileNotFoundError(f"REPL binary not found at {repl_binary}")

    # Make binary executable
    repl_binary.chmod(0o755)
    logger.info("REPL binary ready at %s", repl_binary)

    return repl_binary


class LeanRepl:
    """Interface to the Lean REPL."""

    #
    # REPL lifecycle
    #
    def __init__(self, repo_path: Path, repl_binary: Path):
        """Start a new REPL process.

        Args:
            repo_path: Path to the repository root (used as working directory)
            repl_binary: Path to the REPL executable
        """
        logger.info("Starting REPL process...")
        logger.debug("Working directory: %s", repo_path)

        # Start the REPL in the project's environment
        cmd = ["lake", "env", str(repl_binary.absolute())]
        logger.debug("Running command: %s", " ".join(cmd))

        self.process = subprocess.Popen(
            cmd,
            cwd=repo_path,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        # Check if process started successfully
        if self.process.poll() is not None:
            error = self.process.stderr.read()
            logger.error("Failed to start REPL: %s", error)
            raise RuntimeError(f"Failed to start REPL: {error}")

        logger.info("REPL process started successfully")

    def close(self):
        """Terminate the REPL process."""
        try:
            logger.info("Terminating REPL process...")
            self.process.terminate()
            self.process.wait(timeout=5)  # Wait up to 5 seconds for clean termination
        except subprocess.TimeoutExpired:
            logger.warning("REPL process did not terminate cleanly, forcing kill")
            self.process.kill()  # Force kill if it doesn't terminate cleanly
        except Exception as e:
            logger.error("Error while closing REPL process: %s", e)
        finally:
            self.process.wait()  # Make sure process is fully cleaned up
            logger.info("REPL process terminated")

    def __enter__(self):
        """Support for 'with' statement."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ensure REPL is closed when exiting 'with' block."""
        self.close()

    #
    # Core REPL communication
    #
    def send_command(self, command: dict) -> dict:
        """Send a command to the REPL and get the response. See
        https://github.com/leanprover-community/repl/blob/master/README.md
        for some example commands and responses.

        Args:
            command: Dictionary containing the command to send

        Returns:
            Parsed JSON response

        Raises:
            RuntimeError if REPL process dies
            json.JSONDecodeError if REPL response is not valid JSON
            ReplError if REPL returns a message with severity "error"
        """
        logger.debug("Sending command to REPL: %s", json.dumps(command))
        self.process.stdin.write(json.dumps(command) + "\n\n")
        self.process.stdin.flush()

        response = ""
        while True:
            if self.process.poll() is not None:
                error = self.process.stderr.read()
                logger.error("REPL died: %s", error)
                raise RuntimeError(f"REPL died: {error}")

            line = self.process.stdout.readline()
            if not line.strip():
                break
            response += line

        logger.debug("Raw REPL response: %s", response.strip())
        result = json.loads(response)

        # Check for error messages
        messages = result.get("messages", [])
        error_messages = [m["data"] for m in messages if m.get("severity") == "error"]
        if error_messages:
            raise ReplError(f"REPL returned errors: {'; '.join(error_messages)}")

        return result

    #
    # High-Level REPL operations
    #
    def read_file(self, relative_path: Path) -> List[dict]:
        """Read a file into repl and return list of sorries.
        Args:
            relative_path: file to read, relative to the repo root

        Returns:
            List of dictionaries containing proof_state_id, sorry location, and
            goal text
        """
        command = {"path": str(relative_path), "allTactics": True}
        response = self.send_command(command)

        # it seems REPL does not include "sorries" field if there are no sorries
        if "sorries" not in response:
            logger.info("REPL output missing 'sorries' field")
            return []

        output = []
        for sorry in response["sorries"]:
            entry = {
                "proof_state_id": sorry["proofState"],
                "location": {
                    "start_line": sorry["pos"]["line"],
                    "start_column": sorry["pos"]["column"],
                    "end_line": sorry["endPos"]["line"],
                    "end_column": sorry["endPos"]["column"],
                },
                "goal": sorry["goal"],
            }
            output.append(entry)
        return output

    def apply_tactic(self, proof_state_id: int, tactic: str) -> Tuple[int, List[str]]:
        """Apply a tactic to a proof state.

        Args:
            proof_state_id: The proof state ID to apply the tactic to
            tactic: The tactic to apply

        Returns:
            Tuple of (new proof state ID, list of new goals)

        Raises:
            ValueError if tactic introduces new sorries
        """
        command = {"tactic": tactic, "proofState": proof_state_id}
        response = self.send_command(command)

        # If response contains "sorries", raise an exception
        # There is a genuine use for passing "sorry" in a tactic, e.g
        # when introducing intermediate "have h : ... := by sorry" statements
        # in non-linear proofs, but we want to keep things simple here.
        if response and "sorries" in response:
            raise ValueError(f"Tactic '{tactic}' introduced new sorries")

        new_proof_state_id = response["proofState"]
        new_goals = response["goals"]
        return new_proof_state_id, new_goals

    def get_goal_parent_type(self, proof_state_id: int) -> str:
        """Get the parent type of the goal at a given proof state.

        Args:
            proof_state_id: The proofState identifier

        Returns:
            The parent type as a string

        Raises:
            RuntimeError if goal parent type could not be determined
        """
        logger.info("Getting goal parent type for proof state %d", proof_state_id)

        command = {
            "tactic": PARENT_TYPE_TACTIC,
            "proofState": proof_state_id,
        }
        response = self.send_command(command)

        if "messages" in response:
            for msg in response["messages"]:
                if msg.get("severity") == "info" and "data" in msg:
                    if "Goal parent type:" in msg["data"]:
                        parent_type = (
                            msg["data"].split("Goal parent type:", 1)[1].strip()
                        )
                        logger.info("Found goal parent type: %s", parent_type)
                        return parent_type

        # If we don't find the goal parent type, raise an exception
        raise RuntimeError(f"REPL tactic did not return parent type")

    def find_sorry_proof_state(self, location: dict) -> Tuple[int, str]:
        """Find the proof state of a sorry.

        Args:
            location: Dict containing the sorry location information

        Returns:
            Tuple of (proof state ID, goal)

        Raises:
            ReplError: if REPL returns an error
            ValueError: if sorry cannot be found at given location
        """
        sorries = self.read_file(location["file"])

        # Find the sorry that matches the location
        for sorry in sorries:
            if (
                sorry["location"]["start_line"] == location["start_line"]
                and sorry["location"]["start_column"] == location["start_column"]
                and sorry["location"]["end_line"] == location["end_line"]
                and sorry["location"]["end_column"] == location["end_column"]
            ):
                logger.info(f"Found matching sorry at line {location['start_line']}")
                return sorry["proof_state_id"], sorry["goal"]
        logger.error("Could not find matching sorry")
        raise ValueError(f"Could not find sorry at specified location: {location}")
