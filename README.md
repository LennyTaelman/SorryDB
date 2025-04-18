# Lean4 SorryDB

The SorryDB project aims to help bridge the gap between automated (formal) theorem
proving "in the lab" and adoption by mathematicians. It provides tools and
infrastructure to facilitate developing and testing AI proof agents
against "real world" mathematical propositions in Lean.

At its core, it provides a continuously updating *dataset* of `sorry`
statements in public Lean 4 repositories. It also provides template *agents*
that attempt to prove such statements, and a *verifier* that checks the
correctness of proposed proofs. Eventually, we hope to host a continuously running sorry-filling competition, with a public *leaderboard*.

For a detailed explanation of the project's motivation, philosophy, and goals, see [ABOUT.md](doc/ABOUT.md).

## Components

### The nightly SorryDB dataset

The main instance of a SorryDB database is hosted at [sorrydb-data](https://github.com/austinletson/sorrydb-data). It is updated nightly, by crawling Lean 4 repositories listed on [Reservoir](https://reservoir.lean-lang.org/) for sorried (`Prop`-valued) statements.

For each such statement, it contains all information needed to locally reproduce
it. This includes repository information (remote url, branch, commit hash), the
Lean 4 version used, and coordinates of the sorry within the repository (path, line, column).

See [DATABASE.md](doc/DATABASE.md) for more detailed information on the database
format.

### The sorry crawler

The dataset is updated nightly using a crawler which uses `git` and `lake build` to
clone and build the repository locally, and then uses the [Lean
REPL](https://github.com/leanprover-community/repl/) to locate and analyze
sorries in the repository.

### The sorry-proving agents

We treat each entry of the database as a theorem-proving challenge, where the
precise task is to replace the `"sorry"` string with a string of tactics that
fills the proof. The input to an agent is an item of the dataset, and the agent
is asked to clone and build the repository, and attempt to find a proof of the
given sorry.

We provide two sample agents:

1. `rfl_agent` which checks if the tactic `rfl` completes the sorried proof
2. `llm_agent` which polls an LLM to make a one-shot attempt at filling the proof.

These are deliberately primitive (and hence weak), and *not* meant for
consumption. Rather, we hope they are helpful as templates on which one can base
stronger sorry-proving agents.

See [AGENTS.md](doc/AGENTS.md) for the specification of input and output of an
agent, and more information on the sample agents.

## Getting started

SorryDB uses [Poetry](https://python-poetry.org/) for dependency management and
packaging. To get started

1. [Install Poetry if you haven't already](https://python-poetry.org/docs/#installation)

2. Clone the repository and install dependencies:
   ```sh
   git clone https://github.com/SorryDB/SorryDB.git
   cd SorryDB
   poetry install
   ```

3. Activate the virtual environment:
   ```sh
   eval $(poetry env activate)
   ```

The command line scripts in [sorrydb/cli](sorrydb/cli) can now be run
from poetry's virtual environment by running:

`poetry run <script name> <options>`.

See the documents in [doc/](doc/) for more information on the various scripts
provided.

### Setting up your own database

We provide various tools to create and manage your own database. See
[DATABASE-SCRIPTS.md](doc/DATABASE-SCRIPTS.md) for instructions in setting up
your own database (e.g. to scrape your own repository).

## Contributing

See `CONTRIBUTING.md` for contribution guidelines.
