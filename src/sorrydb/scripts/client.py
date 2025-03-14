#!/usr/bin/env python3

import argparse
import json
import logging
import sys
from pathlib import Path

from sorrydb.repl_client.repl_client import process_sorry_json


def main():
    parser = argparse.ArgumentParser(
        description="Reproduce a sorry with REPL."
    )
    parser.add_argument(
        "--sorry-file",
        type=str,
        required=True,
        help="Path to the sorry JSON file",
    )
    parser.add_argument(
        "--lean-data",
        type=str,
        default=None,
        help="Directory to store Lean data (default: use temporary directory)",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level (default: INFO)",
    )
    parser.add_argument(
        "--log-file", 
        type=str, 
        help="Log file path (default: output to stdout)"
    )

    args = parser.parse_args()

    # Configure logging
    log_kwargs = {
        "level": getattr(logging, args.log_level),
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    }
    if args.log_file:
        log_kwargs["filename"] = args.log_file
    logging.basicConfig(**log_kwargs)

    logger = logging.getLogger(__name__)

    # Convert file names arguments to Path
    sorry_file = Path(args.sorry_file)
    lean_data = Path(args.lean_data) if args.lean_data else None

    # Process the sorry JSON file
    # For now, this just prints the goal type
    try:
        logger.info(f"Processing sorry file: {sorry_file}")
        reproduced_goal = process_sorry_json(sorry_file, lean_data)
        print(reproduced_goal)
        return 0

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return 1
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        logger.exception(e)
        return 1


if __name__ == "__main__":
    sys.exit(main()) 
