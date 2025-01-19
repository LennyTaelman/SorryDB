#!/usr/bin/env python3

import os
import time
import requests
import sys
import argparse
from pathlib import Path
import base64
from typing import List, Dict, Any, Set
import json
from datetime import datetime, timedelta

def check_rate_limit(session):
    """Check GitHub API rate limit status."""
    response = session.get("https://api.github.com/rate_limit")
    remaining = response.json()["rate"]["remaining"]
    if remaining < 10:
        reset_time = response.json()["rate"]["reset"]
        sleep_time = reset_time - time.time() + 1
        if sleep_time > 0:
            print(f"Rate limit nearly exceeded. Waiting {sleep_time:.0f} seconds...")
            time.sleep(sleep_time)

def get_line_blame_info(repo: str, path: str, line_number: int, session: requests.Session) -> Dict[str, Any]:
    """Get blame information for a specific line using GraphQL."""
    owner, name = repo.split('/')
    query = """
    query ($owner: String!, $name: String!, $path: String!) {
      repository(owner: $owner, name: $name) {
        defaultBranchRef {
          target {
            ... on Commit {
              blame(path: $path) {
                ranges {
                  startingLine
                  endingLine
                  commit {
                    authoredDate
                    author {
                      name
                      email
                    }
                    message
                  }
                }
              }
            }
          }
        }
      }
    }
    """
    
    variables = {
        "owner": owner,
        "name": name,
        "path": path
    }
    
    try:
        response = session.post(
            'https://api.github.com/graphql',
            json={'query': query, 'variables': variables}
        )
        response.raise_for_status()
        data = response.json()
        
        # Navigate through the response to find the blame range for our line
        ranges = data['data']['repository']['defaultBranchRef']['target']['blame']['ranges']
        for range_info in ranges:
            if range_info['startingLine'] <= line_number <= range_info['endingLine']:
                commit = range_info['commit']
                return {
                    "author": commit['author']['name'],
                    "email": commit['author']['email'],
                    "date": commit['authoredDate'],
                    "message": commit['message'].split('\n')[0]  # First line only
                }
        return None
    except Exception as e:
        print(f"Error getting blame for {path}:{line_number}: {e}")
        return None

def get_recent_commits(repo: str, session: requests.Session, cutoff_date: datetime) -> Dict[str, List[str]]:
    """Get recent commits for each active branch.
    Returns a dict mapping branch_name -> list of commit SHAs, ordered from newest to oldest.
    Only includes branches that have had commits since cutoff_date."""
    check_rate_limit(session)
    
    # First get all branches and their current HEADs
    branches = {}  # Maps branch_name -> (HEAD commit SHA, commit date)
    page = 1
    while True:
        response = session.get(
            f"https://api.github.com/repos/{repo}/branches",
            params={"page": page, "per_page": 100}
        )
        response.raise_for_status()
        branch_page = response.json()
        if not branch_page:
            break
            
        for branch in branch_page:
            # Get commit date for the HEAD
            commit_response = session.get(branch["commit"]["url"])
            commit_response.raise_for_status()
            commit_date = commit_response.json()["commit"]["committer"]["date"]
            branches[branch["name"]] = (branch["commit"]["sha"], commit_date)
        
        page += 1
    
    # For each branch, get its recent commit history
    branch_commits = {}  # Maps branch_name -> list of commit SHAs
    for branch_name, (head_sha, head_date) in branches.items():
        # Get commit history for this branch
        response = session.get(
            f"https://api.github.com/repos/{repo}/commits",
            params={
                "sha": head_sha,
                "since": cutoff_date.isoformat(),
                "per_page": 100
            }
        )
        response.raise_for_status()
        commits = response.json()
        
        # Include branch if it has any recent commits
        if commits:
            branch_commits[branch_name] = {
                "commits": [commit["sha"] for commit in commits],
                "head_date": head_date
            }
    
    return branch_commits

def get_file_content_at_ref(repo: str, path: str, ref: str, session: requests.Session) -> str:
    """Get file content at a specific ref (branch or commit)."""
    check_rate_limit(session)
    try:
        response = session.get(
            f"https://api.github.com/repos/{repo}/contents/{path}",
            params={"ref": ref}
        )
        response.raise_for_status()
        return base64.b64decode(response.json()["content"]).decode("utf-8")
    except requests.RequestException as e:
        print(f"Error getting file content: {e}")
        return None

def process_file_content(content: str) -> List[int]:
    """Process file content and return line numbers containing sorries."""
    lines = content.splitlines()
    sorry_lines = []
    
    for i, line in enumerate(lines):
        line = line.strip()
        
        # Skip line comments
        if line.startswith("--") or line.startswith("/--"):
            continue
            
        # Look for 'sorry' as a token
        parts = line.split()
        if 'sorry' in parts:
            sorry_lines.append(i + 1)
    
    return sorry_lines

def get_affected_files(repo: str, branch_commits: Dict[str, List[str]], session: requests.Session) -> Dict[str, List[str]]:
    """Get files affected by recent commits for each branch.
    
    Args:
        repo: The repository name (owner/repo)
        branch_commits: Output from get_recent_commits - maps branch names to lists of commit SHAs
        session: GitHub API session
        
    Returns:
        Dict mapping branch_name -> list of file paths that were modified in any of the branch's commits
    """
    branch_files = {}
    
    for branch, commits in branch_commits.items():
        affected_files = set()
        
        for commit_sha in commits["commits"]:
            try:
                response = session.get(f"https://api.github.com/repos/{repo}/commits/{commit_sha}")
                response.raise_for_status()
                commit_data = response.json()
                
                # Add all .lean files modified in this commit
                for file_info in commit_data["files"]:
                    if file_info["filename"].endswith(".lean"):
                        affected_files.add(file_info["filename"])
            
            except Exception as e:
                print(f"Error getting files for commit {commit_sha}: {e}")
                continue
        
        if affected_files:
            branch_files[branch] = list(affected_files)
    
    return branch_files

def process_repository(repo: str, session: requests.Session, cutoff_date: datetime) -> List[Dict[str, Any]]:
    """Process a repository to find sorries in recently modified files across all branches."""
    print(f"Processing {repo}...")
    results = []
    
    try:
        # Get recent commits per branch
        branch_commits = get_recent_commits(repo, session, cutoff_date)
        
        if not branch_commits:
            print(f"Skipping {repo} - no recent commits")
            return []
            
        # Get affected files per branch
        branch_files = get_affected_files(repo, branch_commits, session)
        
        if not branch_files:
            print(f"Skipping {repo} - no affected .lean files")
            return []
            
        total_files = sum(len(files) for files in branch_files.values())
        print(f"Found {len(branch_files)} active branches with {total_files} affected .lean files")
        
        # Process each branch
        for branch, files in branch_files.items():
            print(f"Processing branch: {branch} ({len(files)} files)")
            head_sha = branch_commits[branch]["commits"][0]  # Use latest commit
            head_date = branch_commits[branch]["head_date"]
            
            # Process each file
            for file_path in files:
                try:
                    # Get file content at this commit
                    content = get_file_content_at_ref(repo, file_path, head_sha, session)
                    if not content:
                        continue
                    
                    # Find sorries
                    sorry_lines = process_file_content(content)
                    for line_number in sorry_lines:
                        # Get blame info
                        blame_info = get_line_blame_info(repo, file_path, line_number, session)
                        if not blame_info:
                            continue
                            
                        # Skip if sorry is older than cutoff
                        blame_date = datetime.fromisoformat(blame_info["date"].replace("Z", "+00:00"))
                        if blame_date < cutoff_date:
                            continue
                        
                        results.append({
                            "repository": repo,
                            "branch": branch,
                            "head_sha": head_sha,
                            "head_date": head_date,
                            "file_path": file_path,
                            "github_url": f"https://github.com/{repo}/blob/{head_sha}/{file_path}#L{line_number}",
                            "line_number": line_number,
                            "blame": blame_info
                        })
            
                except Exception as e:
                    print(f"Error processing file {file_path}: {e}")
                    continue
    
    except Exception as e:
        print(f"Error processing repository {repo}: {e}")
    
    return results

def main():
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description='Find recent sorries in Lean repositories.')
    parser.add_argument('--cutoff', type=int, default=10,
                       help='Number of days to look back for new sorries (default: 10)')

    args = parser.parse_args()

    # Check for GitHub token
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        print("Error: GITHUB_TOKEN environment variable is not set")
        sys.exit(1)

    # Setup session with authentication
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json"
    })

    # Set cutoff date using the command line argument
    cutoff_date = datetime.now(datetime.now().astimezone().tzinfo) - timedelta(days=args.cutoff)
    print(f"Checking for sorries in files modified since: {cutoff_date.strftime('%Y-%m-%d')}")

    # Read repository list
    try:
        with open("lean4_repos.txt") as f:
            repos = [line.strip() for line in f if line.strip()]
        print(f"Found {len(repos)} repositories in lean4_repos.txt")
    except FileNotFoundError:
        print("Error: lean4_repos.txt not found")
        sys.exit(1)

    # Process repositories
    results = []
    for i, repo in enumerate(repos, 1):
        print(f"\nProcessing {repo} ({i}/{len(repos)})...")
        repo_results = process_repository(repo, session, cutoff_date)
        if repo_results:
            results.extend(repo_results)
            # Save after each successful repository
            with open("new_sorries.json", "w") as f:
                json.dump(results, f, indent=2)

    print(f"\nComplete! Results saved in new_sorries.json")

    # Print summary
    repos_with_sorries = len({r["repository"] for r in results})
    files_with_sorries = len({(r["repository"], r["file_path"]) for r in results})
    total_sorries = len(results)
    
    print(f"\nSummary:")
    print(f"Repositories with sorries: {repos_with_sorries}")
    print(f"Files with sorries: {files_with_sorries}")
    print(f"Total sorry occurrences: {total_sorries}")

if __name__ == "__main__":
    main() 