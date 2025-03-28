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


def setup_repl(lean_data: Path, version_tag: str | None = None) -> Path:
    """Clone and build the REPL repository.

    Args:
        lean_data: Path where the REPL should be cloned
        version_tag: Optional git tag to checkout. If None, uses latest version
    """
    # Create a directory name that includes the version tag
    if version_tag is not None:
        sanitized_tag = version_tag.replace(".", "_").replace("-", "_")
        repl_dir = lean_data / f"repl_{sanitized_tag}"
    else:
        # TODO: We might need to make this a "most recent version of sorts"
        repl_dir = lean_data / "repl"

    if not repl_dir.exists():
        logger.info(f"Cloning REPL repository into {repl_dir}...")
        repo = Repo.clone_from(REPL_REPO_URL, repl_dir)

        if version_tag is not None:
            logger.info(f"Checking out REPL at tag: {version_tag}")
            repo.git.checkout(version_tag)

        logger.info("Building REPL...")
        result = subprocess.run(["lake", "build"], cwd=repl_dir)
        if result.returncode != 0:
            logger.error("Failed to build REPL")
            raise Exception("Failed to build REPL")

    repl_binary = repl_dir / ".lake" / "build" / "bin" / "repl"
    if not repl_binary.exists():
        logger.error("REPL binary not found at %s", repl_binary)
        raise Exception("REPL binary not found")

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
        logger.debug("REPL binary: %s", repl_binary.absolute())

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
            raise Exception(f"Failed to start REPL: {error}")

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
    def send_command(self, command: dict) -> dict | None:
        """Send a command to the REPL and get the response. See
        https://github.com/leanprover-community/repl/blob/master/README.md
        for some example commands and responses.

        Args:
            command: Dictionary containing the command to send

        Returns:
            Parsed JSON response or None if no response

        Raises:
            Exception if REPL process dies
        """
        try:
            logger.debug("Sending command to REPL: %s", json.dumps(command))
            self.process.stdin.write(json.dumps(command) + "\n\n")
            self.process.stdin.flush()

            response = ""
            while True:
                if self.process.poll() is not None:
                    error = self.process.stderr.read()
                    logger.error("REPL died: %s", error)
                    raise Exception(f"REPL died: {error}")

                line = self.process.stdout.readline()
                if not line.strip():
                    break
                response += line

            if response.strip():
                logger.debug("Raw REPL response: %s", response.strip())
                try:
                    result = json.loads(response)
                    logger.debug(f"REPL response contains: {', '.join(result.keys())}")
                    return result
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse REPL response: {e}")
                    return None
            else:
                logger.warning("REPL returned empty response")
                return None

        except Exception as e:
            logger.error("Error sending command to REPL: %s", e)
            # Try to get any stderr output
            error = self.process.stderr.read()
            if error:
                logger.error("REPL stderr: %s", error)
            return None

    #
    # High-Level REPL operations
    #
    def read_file(self, relative_path: Path) -> List[dict] | None:
        """Read a file into repl and return list of sorries.
        Args:
            relative_path: file to read, relative to the repo root

        Returns:
            List of dictionaries containing proof_state_id, sorry location, and
            goal text;
            None if failed
        """
        command = {"path": str(relative_path), "allTactics": True}
        response = self.send_command(command)

        if response is None:
            logger.warning("REPL returned no output")
            return None

        if "messages" in response:
            for m in response["messages"]:
                if m.get("severity") == "error":
                    logger.warning(f"REPL returned error: {m['data']}")
                    return None

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

    def apply_tactic(
        self, proof_state_id: int, tactic: str
    ) -> Optional[Tuple[int, List[str]]]:
        """Apply a tactic to a proof state.

        Args:
            proof_state_id: The proof state ID to apply the tactic to
            tactic: The tactic to apply

        Returns:
            If successful: Tuple of (new proof state ID, list of new goals)
            If failed (or introduced new sorries): None
        """
        command = {"tactic": tactic, "proofState": proof_state_id}
        response = self.send_command(command)

        # If response contains "sorries", return None
        # There is a genuine use for passing "sorry" in a tactic, e.g
        # when introducing intermediate "have h : ... := by sorry" statements
        # in non-linear proofs, but we want to keep things simple here.
        if response and "sorries" in response:
            logger.warning("Tactic introduced new sorries: {tactic}")
            return None

        # Check if we have a valid response with a new proof state
        if response and "proofState" in response and "goals" in response:
            new_proof_state_id = response["proofState"]
            new_goals = response["goals"]
            return new_proof_state_id, new_goals

        # Handle failure
        logger.warning("Tactic failed. Raw response: {response}")

        return None

    def get_goal_parent_type(self, proof_state_id: int) -> str | None:
        """Get the parent type of the goal at a given proof state.

        Args:
            proof_state_id: The proofState identifier

        Returns:
            The parent type as a string, or None if failed
        """
        logger.info("Getting goal parent type for proof state %d", proof_state_id)

        command = {
            "tactic": PARENT_TYPE_TACTIC,
            "proofState": proof_state_id,
        }
        response = self.send_command(command)

        if response and "messages" in response:
            for msg in response["messages"]:
                if msg.get("severity") == "info" and "data" in msg:
                    if "Goal parent type:" in msg["data"]:
                        parent_type = (
                            msg["data"].split("Goal parent type:", 1)[1].strip()
                        )
                        logger.info("Found goal parent type: %s", parent_type)
                        return parent_type

        logger.warning(
            "Failed to get goal parent type for proof state %d", proof_state_id
        )
        return None
