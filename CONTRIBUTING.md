## Contribution Guidelines

Thank you for your interest in contributing to SorryDB!

SorryDB is under active development, 
and we welcome contributions in the form of GitHub issues, pull requests, or even just questions and feedback.

### 1. Understand the Project

Before diving in, we recommend:
- Reading the `ABOUT.md` file to understand the project's goals and scope
- Exploring the codebase to get familiar with its structure
- Checking existing issues to see what's already being worked on
- Come chat with us at the [Lean community Zulip chat](https://leanprover.zulipchat.com/)

### 2. Setting Up Your Development Environment

#### Using Poetry (Recommended)

SorryDB uses [Poetry](https://python-poetry.org/) for dependency management and packaging.

1. [Install Poetry if you haven't already](https://python-poetry.org/docs/#installation)

2. Clone the repository and install dependencies:
   ```sh
   git clone https://github.com/LeannyTaelman/SorryDB.git
   cd SorryDB
   poetry install
   ```

3. Activate the virtual environment:
   ```sh
   eval $(poetry env activate)
   ```

4. Run SorryDB commands:
   ```sh
   # Initialize a database
   init_db --repos-file repo_lists/mock_repos.json --database-file sorry_database.json --starting-date 2025-03-11
   
   # Update an existing database
   update_db --database-file sorry_database.json --log-level DEBUG
   ```

#### Using Docker

For Docker-based development and deploying SorryDB, please refer to `DEPLOY.md` for detailed instructions.

#### Code Quality Tools

SorryDB uses pre-commit and ruff to maintain code quality:

1. Install pre-commit hooks:
   ```sh
   pre-commit install
   ```

2. The hooks will run automatically on each commit, or manually with:
   ```sh
   pre-commit run --all-files
   ```

3. Ruff is configured in `pyproject.toml` and handles:
   - Code formatting
   - Import sorting
   - Linting

4. Run ruff manually:
   ```sh
   # Format code
   ruff format 
   
   # Lint code
   ruff check
   ```

## Contributing Process

### 1. Find or Create an Issue

- Browse existing [issues](https://github.com/LennyTaelman/SorryDB/issues) to find something to work on
- If you have a new idea for a feature or improvement, create a GitHub issue first to discuss it with others 
- For bug fixes, create an issue describing the bug before submitting a fix

### 2. Develop and Test

- Follow the existing code style and conventions
- Add unit tests for new functionality
- Run the test suite to ensure everything works:
  ```sh
  # Run all tests
  pytest
  
  # Run a specific test
  pytest tests/test_git_ops.py::test_remote_heads
  ```

### 3. Submit a Pull Request

- We prefer small, focused PRs rather than large changes
- Ensure your PR description clearly explains the changes and their purpose
- Link to any related issues using keywords like "Fixes #28"
(see [linking a pull request to an issue](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue#linking-a-pull-request-to-an-issue-using-a-keyword))
- At least one other collaborator should review your PR before it can be merged

## Advanced Topics

### Stacking PRs

We encourage [stacking](https://www.stacking.dev/) small PRs instead of creating large, monolithic changes:

1. Create a PR with a small change
2. Create subsequent PRs that build on top by selecting the previous PR's branch as the base
3. GitHub will automatically update PR targets when base branches are merged

This approach makes reviews easier and allows dependent features to progress in parallel.

## Testing Resources

### Mock Repository Lists

The `repo_lists` folder contains various JSON files with repository configurations for testing:
- `mock_repos.json`: Basic test repositories
- `mock_with_carleson.json`: Basic test repositories plus the Carleson project

### Test Databases

We maintain two test databases that are updated daily:

1. [sorry-db-data-test-mock-only](https://github.com/austinletson/sorry-db-data-test-mock-only)
   - Contains data from `mock_repos.json`
   - Good for basic testing

2. [sorry-db-data-test](https://github.com/austinletson/sorry-db-data-test)
   - Contains data from `mock_with_carleson.json`
   - Good for testing on a real world repo
   - Will eventually mirror the production database configuration

> Note: These test databases are currently maintained via systemd timer units on a personal machine, so availability may occasionally be affected.

## Need Help?
If you have questions or need assistance feel free to open an issue or reach out on Zulip to Lenny Taelman or Austin Letson
