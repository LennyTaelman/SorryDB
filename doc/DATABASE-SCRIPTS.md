# Database scripts

The SorryDB database is created using a number of python scripts that use `git`, `lake
build`, and the Lean `REPL` to collect sorries from Lean repositories. Below we provide
instructions for setting up and managing your own database, e.g. for scraping your own repository.

## Building a database instance

### 1. Obtain a list of repositories

To initialize a database file, one needs a json with a list of repositories to
monitor. See [`sample_repo_list.json`](sample_repo_list.json) for a sample.

One can also generate a list of repositories from the Lean
[Reservoir](https://reservoir.lean-lang.org/packages) using the
`scrape_reservoir` script. Running

`poetry run sorrydb/cli/scrape_reservoir.py --updated-since 2025-01-01
--minimum-stars 10 --output repo_list.json`

will generate a json file containing all Lean repositories listed on reservoir
that have been updated since Jan 1, and have at least 10 GitHub stars.

### 2. Initialize a database file

Starting from a list of repositories, one can then initialize the database file using

`poetry run sorrydb/cli/init_db.py --repos-file repo_list.json --database-file database.json`

This provides an initialised database `database.json` which does not yet contain
any sorries. The cut-off date indicates that the database updater will only
revisit repositories that have been modified since the cutoff date.

### 3. Updating the database file

Now one can update the database regularly using:

`poetry run sorrydb/cli/update_db.py --database-file mock_db.json`

See [DEPLOY.md](DEPLOY.md) for instructions on running the database updater in a
docker.
