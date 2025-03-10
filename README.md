# Lean4 SorryDB

This repository aims to build a continuously updating database of `sorry` statements in public Lean4 repositories. The idea is to use this as a basis for a continuously running benchmark which tests the performance of automated proof systems against *real world* Lean statements.

For a detailed explanation of the project's motivation, philosophy, and goals, see [ABOUT.md](ABOUT.md).

Currently we are building:

1. A list of repos/branches to continuously check for new sorries
2. A database updater which searches for sorries in the repos, tries to reproduce them locally using [REPL](https://github.com/leanprover-community/repl/), and updates the database
3. The database itself, with all information needed to reproduce the sorries independently.
4. A simple sample client which locally reproduces a sorry from the database and tries to prove it.

At a later stage, this should be extended with:

- More advanced clients, which hopefully can obtain a non-zero success rate on
  sorries in the wild
- Sample clients built on different lean-interaction tools (e.g. [Pantograph](https://github.com/stanford-centaur/PyPantograph))
- A leaderboard server with an API that clients can poll to obtain sorries
- A web site with a *leaderboard* ranking the performance of different automated proof systems.


## Scripts for creating and updating the database

Scripts can be run from poetry's virtual environment by running
`poetry run <script name> <options>`.

To initialize a database file, one needs a json with a list of repositories to
monitor. The folder `repo_lists` provides some examples. Then run for example

`poetry run src/sorrydb/scripts/init_db.py --repos-file repo_lists/mock_repos.json --database-file mock_db.json`

This provides an initialised database `mock_db.json` which does not yet contain
any sorries. Now one can update the database repeatedly using:

`poetry run src/sorrydb/scripts/update_db.py --database-file mock_db.json`
