# Database format

The SorryDB database tracks sorry statements from public Lean 4 repositories.
The database consists of a JSON file with as format

```json
{
  "repos": [...]
  "sorries": [...]
}
```
Below we describe the contents of the two entries.

## List of sorries

The `sorries` field contains a list of sorry record. Each record has the following format:

```json
{
  "repo": {
    "remote": "https://github.com/ImperialCollegeLondon/FLT",
    "branch": "quat-alg-weight-2",
    "commit": "00bee2838ab99689836c6396ea310e0bedfbcddd",
    "lean_version": "v4.18.0-rc1"
  },
  "location": {
    "path": "FLT/GlobalLanglandsConjectures/GLzero.lean",
    "start_line": 127,
    "start_column": 19,
    "end_line": 127,
    "end_column": 24,
  },
  "debug_info": {
      "goal": "z : \u2102\nn : \u2115\n\u03c1 : Weight n\nh\u03c1 : \u03c1.IsTrivial\n\u22a2 IsSmooth fun x => z",
      "url": "https://github.com/ImperialCollegeLondon/FLT/blob/00bee2838ab99689836c6396ea310e0bedfbcddd/FLT/GlobalLanglandsConjectures/GLzero.lean#L127"
  },
  "metadata": {
    "blame_email_hash": "1679c78ca90b",
    "blame_date": "2024-06-12T14:33:04+02:00",
    "inclusion_date": "2025-03-14T12:00:00+00:00"
  },
  "id": "a7f9b3c5d2e1"
}
```

Below we specify in more detail the contents of the individual fields.

### `repo`

This field contains all information necessary to rebuild the repository locally. For example:

```bash
# clone and check out the relevant commit
git clone <repo.remote> $repo_dir
cd $repo_dir
git checkout <repo.commit>

# obtain mathlib cache and build the repository
lake exe cache get
lake build
```

The `repo.lean_version` contains the [lean version-tag](https://docs.lean-lang.org/lean4/doc/dev/release_checklist.html) of this commit, obtained by inspecting the `lean-toolchain` file of the
repository. To interact with the repository using a tool such as [REPL](https://github.com/leanprover-community/repl/) or
[Pantograph](https://github.com/lenianiva/Pantograph), you will need a release of this tool matching this lean version.

### `location`

Specifies the location of the sorried proof within the specific commit of the repository (typically encoded with the lean "sorry" keyword). For example, opening the file in VS Code using

```shell
# open the file containing the sorry in VS Code
code <location.path>
```

and navigating the cursor to `(location.start_line, location.start_column)`, one should see a goal
matching `debug_info.goal` in the Lean infoview.

Alternatively, one can use the basic REPL client provided to reproduce the sorry
in [REPL](https://github.com/leanprover-community/repl/). See [doc to be
written] for more information.

### `debug_info`

This field is provided to help with debugging, and should not be relied upon in
the design of a client. It currently provides a pretty-printed proof goal, and a direct link to the relevant
line of code on GitHub. 

### `metadata`

Contains various items for internal use by the database. `metadata.blame_date` is the date on which the line of code containing the sorry was committed and `metadata.blame_email_hash` the hashed email address of the author of that commit, both according to `git blame`. The field `metadata.inclusion_date` specifies when this record was added to the database.

### `id`

Finally, we provide a unique ID to the sorry, built as a hash from the `repo`
and `location` fields. This is a very fine-grained ID, as we consider *any*
change to *any* file in the repository as affecting *all* sorries in the
repository (a crucial definition may have changed the meaning of the statement,
or a new lemma may have made the statement easier to prove).

## List of repositories

The `repos` field of the database contains the repositories being tracked, and
helps decide when to revisit a repository for updates. It contains a list of
records, each of the following form:

```json
{
      "remote_url": "https://github.com/austinletson/sorryClientTestRepo",
      "last_time_visited": "2025-03-17T11:35:11.161845+00:00",
      "remote_heads_hash": "24f2d32ed5ed"
}
```

The first field is a `git` remote url and `last_time_visited` denotes either the last time the database updater visited this repository, or a user-provided cut-off date to be used in deciding which branches to check on the initial visit.

The `remote_heads_hash` provides a combined hash of all the commit SHAs of the leaf commits at the time of the last visit. This allows for an efficient check using `git ls-remote` to decide if the repository needs to be cloned for further inspection.

## Database update stats

When updating the database optionally collect statistics on the database update with the `--stats-file` option.

The statistics will be written as JSON with the following format:


- **`<repository_url>`**: The key is the URL of the repository being processed.
  - **`counts`**: An object where each key is a commit hash, and its value is an object with:
    - **`count`**: The number of sorries found in the commit.
    - **`count_new_proof`**: The number of the sorries found with new goals, i.e., no other sorry in the database as the same pretty-printed goal.
  - **`new_leaf_commit`**: A boolean indicating whether this repo had new leaf commits.
  - **`start_processing_time`**: The timestamp (ISO 8601 format) when processing for this repository started.
  - **`end_processing_time`**: The timestamp (ISO 8601 format) when processing for this repository ended.
  - **`total_processing_time`**: The total time taken to process this repository, represented as a string.
  - **`lake_timeout`**: A boolean indicating if there was a `lake build` timeout on this repo.

A null value for a specific field means that it wasn't updated during the database update,
either due to an error, or more likely, because a repo was skipped due to no new leaf_commits.

```json
{
  "https://github.com/AlexKontorovich/PrimeNumberTheoremAnd": {
    "counts": {
      "5365476bb7e0988aaeb959174f4a06734f34bb6c": {
        "count": 14,
        "count_new_proof": 0
      }
    },
    "new_leaf_commit": true,
    "start_processing_time": "2025-04-03T23:00:27.118546+00:00",
    "end_processing_time": "2025-04-03T23:14:05.266052+00:00",
    "total_processing_time": "13m 38s",
    "lake_timeout": null
  },
}
  ```

