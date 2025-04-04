import json
import logging
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from sorrydb.database.sorry import Sorry

logger = logging.getLogger(__name__)


class JsonDatabase:
    def __init__(self):
        self.data = None
        self.update_stats = defaultdict(
            lambda: {
                "counts": defaultdict(lambda: {"count": 0, "count_new_proof": 0}),
                "new_leaf_commit": None,
                "start_processing_time": None,
                "end_processing_time": None,
                "total_processing_time": None,
                "lake_timeout": None,
            }
        )

    def set_new_leaf_commit(self, repo_url, new_leaf_commit):
        self.update_stats[repo_url]["new_leaf_commit"] = new_leaf_commit

    def set_start_processing_time(self, repo_url, start_processing_time):
        self.update_stats[repo_url]["start_processing_time"] = start_processing_time

    def set_end_processing_time(self, repo_url, end_processing_time):
        self.update_stats[repo_url]["end_processing_time"] = end_processing_time
        self._update_total_processing_time(repo_url)

    def _update_total_processing_time(self, repo_url):
        start_time = self.update_stats[repo_url]["start_processing_time"]
        end_time = self.update_stats[repo_url]["end_processing_time"]

        if start_time and end_time:
            start_dt = datetime.fromisoformat(start_time)
            end_dt = datetime.fromisoformat(end_time)
            total_seconds = (end_dt - start_dt).total_seconds()

            # Format the time in a human-readable format
            hours, remainder = divmod(int(total_seconds), 3600)
            minutes, seconds = divmod(remainder, 60)

            if hours > 0:
                human_readable = f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                human_readable = f"{minutes}m {seconds}s"
            else:
                human_readable = f"{seconds}s"

            self.update_stats[repo_url]["total_processing_time"] = human_readable

    def set_lake_timeout(self, repo_url, lake_timeout):
        self.update_stats[repo_url]["lake_timeout"] = lake_timeout

    def load_database(self, database_path):
        """
        Load a SorryDatabase from a JSON file.

        Raises:
            FileNotFoundError: If the database file doesn't exist
            ValueError: If the database file contains invalid JSON
        """
        logger.info(f"Loading sorry database from {database_path}")

        try:
            with open(database_path, "r") as f:
                database = json.load(f)
            self.data = database
        except FileNotFoundError:
            logger.error(f"Database file not found: {database_path}")
            raise FileNotFoundError(f"Database file not found: {database_path}")
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in database file: {database_path}")
            raise ValueError(f"Invalid JSON in database file: {database_path}")

    def get_all_repos(self):
        return self.data["repos"]

    def add_sorry(self, sorry: Sorry):
        sorry_dict = asdict(sorry)
        self.data["sorries"].append(sorry_dict)

        repo_url = sorry.repo.remote
        commit_sha = sorry.repo.commit

        is_new_goal = False
        current_goal = sorry.debug_info.goal if sorry.debug_info else None
        if current_goal:
            is_new_goal = all(
                existing_sorry.get("debug_info", {}).get("goal") != current_goal
                for existing_sorry in self.data["sorries"][:-1]
            )

        repo_stats = self.update_stats[repo_url]["counts"][commit_sha]
        repo_stats["count"] += 1
        if is_new_goal:
            repo_stats["count_new_proof"] += 1

    def write_database(self, write_database_path: Path):
        logger.info(f"Writing updated database to {write_database_path}")
        with open(write_database_path, "w") as f:
            json.dump(
                self.data,
                f,
                indent=2,
                default=Sorry.default_json_serialization,
            )
        logger.info("Database update completed successfully")

    def write_stats(self, write_stats_path: Path):
        logger.info(f"Writing database update stats to {write_stats_path}")
        with open(write_stats_path, "w") as f:
            json.dump(
                self.update_stats,
                f,
                indent=2,
            )
        logger.info("Database stats written successfully")
