#!/usr/bin/env python3

import argparse
import json
import logging
from pathlib import Path
from typing import Optional

from sorrydb.database.build_database import build_database

def main():
    parser = argparse.ArgumentParser(description='Build a SorryDatabase from multiple Lean repositories.')
    parser.add_argument('--repos-file', type=str, required=True,
                       help='JSON file containing list of repositories to process')
    parser.add_argument('--output', type=str, default='sorry_database.json',
                       help='Output file path for the database (default: sorry_database.json)')
    parser.add_argument('--lean-data-dir', type=str, default="",
                       help='Directory for repository checkouts and Lean data (default: create a temporary directory)')
    # Add simple logging options
    parser.add_argument('--log-level', type=str, default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                       help='Set the logging level (default: INFO)')
    parser.add_argument('--log-file', type=str,
                       help='Log file path (default: output to stdout)')
    
    args = parser.parse_args()
    
    # Configure logging
    log_kwargs = {
        'level': getattr(logging, args.log_level),
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    }
    if args.log_file:
        log_kwargs['filename'] = args.log_file
    logging.basicConfig(**log_kwargs)
    
    logger = logging.getLogger(__name__)
    
    # Create lean data directory
    lean_data: Optional[Path] = Path(args.lean_data_dir) if args.lean_data_dir != '' else None
    if lean_data:
        lean_data.mkdir(exist_ok=True)
    
    with open(args.repos_file, 'r') as f:
        repos_data = json.load(f)

    repos_list = repos_data["repos"]
    
    # Build the database
    try:
        logger.info(f"Building database from {len(repos_list)} repositories")
        build_database(
            repo_list=repos_list,
            lean_data=lean_data,
            output_path=args.output
        )
        
    except Exception as e:
        logger.error(f"Error building database: {e}")
        logger.exception(e)
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
