#!/usr/bin/env python3

import json
import logging
import subprocess
from pathlib import Path

from git import Repo

logger = logging.getLogger(__name__)


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
        repo = Repo.clone_from("https://github.com/leanprover-community/repl", repl_dir)

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

    def send_command(self, command: dict) -> dict | None:
        """Send a command to the REPL and get the response.

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


def get_goal_parent_type(repl: LeanRepl, proof_state_id: int) -> str | None:
    """Get the parent type of the goal at a given proof state.

    Args:
        repl: An active REPL instance
        proof_state_id: The proofState identifier

    Returns:
        The parent type as a string, or None if failed
    """
    logger.info("Getting goal parent type for proof state %d", proof_state_id)

    # Original tactic:
    # run_tac (do let parentType ← Lean.Meta.inferType (← Lean.Elab.Tactic.getMainTarget); Lean.logInfo m!"Goal parent type: {parentType}")

    command = {
        "tactic": 'run_tac (do let parentType ← Lean.Meta.inferType (← Lean.Elab.Tactic.getMainTarget); Lean.logInfo m!"Goal parent type: {parentType}")',
        "proofState": proof_state_id,
    }
    response = repl.send_command(command)

    if response and "messages" in response:
        for msg in response["messages"]:
            if msg.get("severity") == "info" and "data" in msg:
                if "Goal parent type:" in msg["data"]:
                    parent_type = msg["data"].split("Goal parent type:", 1)[1].strip()
                    logger.info("Found goal parent type: %s", parent_type)
                    return parent_type

    logger.warning("Failed to get goal parent type for proof state %d", proof_state_id)
    return None
