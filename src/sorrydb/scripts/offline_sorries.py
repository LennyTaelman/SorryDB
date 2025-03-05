#!/usr/bin/env python3

import argparse
from pathlib import Path
import json
import logging
from typing import Optional

from sorrydb.database.build_database import prepare_and_process_lean_repo

def main():
    parser = argparse.ArgumentParser(description='Process Lean files in a repository using lean-repl-py.')
    parser.add_argument('--repo-url', type=str, required=True,
                       help='Git remote URL (HTTPS or SSH) of the repository to process')
    parser.add_argument('--branch', type=str,
                       help='Branch to process (default: repository default branch)')
    parser.add_argument('--lean-data-dir', type=str, default="",
                       help='Directory for repository checkouts and Lean data (default: create a temporary directory)')
    parser.add_argument('--dir', type=str,
                       help='Subdirectory to search for Lean files (default: entire repository)')
    # Add simple logging options
    parser.add_argument('--log-level', type=str, default='WARNING',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                       help='Set the logging level (default: WARNING)')
    parser.add_argument('--log-file', type=str,
                       help='Log file path (default: output to stdout)')
    
    args = parser.parse_args()
    
    # Simple logging configuration
    log_kwargs = {
        'level': getattr(logging, args.log_level),
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    }
    if args.log_file:
        log_kwargs['filename'] = args.log_file
    logging.basicConfig(**log_kwargs)
    
    # Create lean data directory
    lean_data: Optional[Path] = Path(args.lean_data_dir) if args.lean_data_dir != '' else None
    if lean_data:
        lean_data.mkdir(exist_ok=True)
    
    results = prepare_and_process_lean_repo(
        repo_url=args.repo_url,
        branch=args.branch,
        lean_data=lean_data,
        subdir=args.dir,
    )
    
    # Write results
    with open("output.json", "w") as f:
        json.dump(results, f, indent=2)
        
    logging.info("Complete! Results saved in output.json") 

if __name__ == "__main__":
    main() 
