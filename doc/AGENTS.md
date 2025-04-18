# Sorry-proving agents

Sorry-proving *agents* attempt to fill sorries provided by SorryDB. They
recreate the repository locally, locate the sorry, and use symbolic or neural
tools to attempt to find a proof of the sorry. The "context" consists of all
definitions above the given sorry in the current file, and all (transitively)
imported files. In particular, this may include all or part of Mathlib. It is
the responsibility of the agent to extract the relevant information from this context.

## Specification

The input to an agent is a JSON file with a list of sorries, as specified in
[DATABASE.md](DATABASE.md).
The output is a JSON containing the same list of sorries, but where each record
contains a new field `proof` containing either `null` or a
proof string to replace the sorry string.

See [sample_sorry_list.json](sample_sorry_list.json) and
[sample_proof_list.json](sample_proof_list.json) for sample input and output files.

## Datasets

To develop, test, or benchmark agents, one can use various lists of sorries:

1. [sample_sorry_list.json](sample_sorry_list.json) with 2 easy "mock" sorries
2. The static April-2025 benchmark hosted at [TODO](url)
3. The nigtly updated [decuplicated_sorries.json](https://github.com/SorryDB/sorrydb-data/blob/master/deduplicated_sorries.json)


## Template agents

To aid the development of agents, we provide two naive sample agents. These are
not meant for consumption, but we hope they can serve as templates for the
development of more serious agents.

### rfl_agent

The agent `rfl_agent` simply attempts to replace each sorry with the tactic
`rfl`. Usage:

`poetry run sorryb/cli/rfl_agent --sorry-file doc/sample_sorry_list.json
--output-file proofs.json`

### llm_agent
