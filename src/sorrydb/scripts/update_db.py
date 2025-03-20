#!/usr/bin/env python3

import argparse
import logging
from pathlib import Path

from sorrydb.database.build_database import update_database


def main():
    parser = argparse.ArgumentParser(
        description="Update a SorryDB database by checking for changes in repositories."
    )
    parser.add_argument(
        "--database-file",
        type=str,
        required=True,
        help="Path to the database JSON file",
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
        "--log-file", type=str, help="Log file path (default: output to stdout)"
    )
    parser.add_argument(
        "--stats-file",
        type=str,
        default=None,
        help="Path to write update statistics (JSON format)",
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
    lean_data = Path(args.lean_data) if args.lean_data else None
    database_path = Path(args.database_file)

    # Update the database
    try:
        update_database(database_path=database_path, lean_data=lean_data, stats_file=args.stats_file)
        return 0

    except Exception as e:
        logger.error(f"Error updating database: {e}")
        logger.exception(e)
        return 1


if __name__ == "__main__":
    exit(main())
