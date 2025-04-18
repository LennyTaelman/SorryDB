#!/usr/bin/env python3

import argparse
import json
import logging
import sys

from sorrydb.agents.llm_agent.llm_agent import LLMAgent


def main():
    parser = argparse.ArgumentParser(description="Solve sorries using LLMClient")

    parser.add_argument(
        "--sorry-db",
        type=str,
        default="https://raw.githubusercontent.com/austinletson/sorry-db-data/refs/heads/master/sorry_database.json",
        help="URL to the sorry database JSON file",
    )

    parser.add_argument(
        "--out",
        type=str,
        default="llm_proofs.json",
        help="Path to the output JSON file (default: llm_proofs.json)",
    )

    parser.add_argument(
        "--model-json",
        type=str,
        default=None,
        help="Path to the model config JSON file (default: None)",
    )

    parser.add_argument(
        "--lean-dir",
        type=str,
        default="lean_data",
        help="Directory to store Lean data (default: lean_data)",
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
        "datefmt": "%Y-%m-%d %H:%M:%S",  # No ms
    }

    if args.log_file:
        log_kwargs["filename"] = args.log_file

    logging.basicConfig(**log_kwargs)
    logger = logging.getLogger(__name__)

    # Process the sorry DB using the LLMClient
    try:
        logger.info(f"Solving sorry db at {args.sorry_db} using LLMAgent.")
        agent = LLMAgent(args.model_json, args.lean_dir)
        agent.solve_sorry_db(args.sorry_db, args.out)
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
