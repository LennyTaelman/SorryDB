#!/usr/bin/env python3

import argparse
import datetime
import json
import logging
from pathlib import Path

from sorrydb.database.build_database import init_database


def main():
    parser = argparse.ArgumentParser(
        description="Initialize a SorryDB json from multiple Lean repositories."
    )
    parser.add_argument(
        "--repos-file",
        type=str,
        required=True,
        help="JSON file containing list of repositories to process",
    )
    parser.add_argument(
        "--database-file",
        type=str,
        required=True,
        help="Output file path for the database",
    )
    parser.add_argument(
        "--starting-date",
        type=str,
        default=None,
        help="Starting date for all repositories (format: YYYY-MM-DD) (default: today)",
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

    # Parse the starting date if provided
    if args.starting_date:
        try:
            # Parse as YYYY-MM-DD format and make timezone-aware (UTC)
            starting_date = datetime.datetime.strptime(args.starting_date, "%Y-%m-%d")
            # Add UTC timezone information
            starting_date = starting_date.replace(tzinfo=datetime.timezone.utc)
            logger.info(f"Using starting date: {starting_date.isoformat()}")
        except ValueError:
            logger.error(
                f"Invalid date format: {args.starting_date}. Use YYYY-MM-DD format."
            )
            return 1
    else:
        # Use current date and time if not provided (with UTC timezone)
        starting_date = datetime.datetime.now(datetime.timezone.utc)
        logger.info(
            f"No starting date provided, using current date and time: {starting_date.isoformat()}"
        )

    with open(args.repos_file, "r") as f:
        repos_data = json.load(f)

    repos_list = [repo["remote"] for repo in repos_data["repos"]]

    database_path = Path(args.database_file)

    # Build the database
    try:
        init_database(
            repo_list=repos_list,
            starting_date=starting_date,
            database_file=database_path,
        )

    except Exception as e:
        logger.error(f"Error building database: {e}")
        logger.exception(e)
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
