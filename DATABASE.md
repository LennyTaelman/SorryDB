# Database format

The SorryDB database tracks sorry statements from public Lean 4 repositories. The database consists of two JSON files: one containing the actual sorry statements and another tracking repositories to crawl.

## List of sorries

The main content of the database is a JSON containing the list of sorries. Each sorry has the following format:

```json
{
  "repo": {
    "remote": "https://github.com/ImperialCollegeLondon/FLT",
    "branch": "quat-alg-weight-2",
    "commit": "00bee2838ab99689836c6396ea310e0bedfbcddd",
    "lean_version": "v4.18.0-rc1"
  },
  "location": {
    "start_line": 127,
    "start_column": 19,
    "end_line": 127,
    "end_column": 24,
    "file": "FLT/GlobalLanglandsConjectures/GLzero.lean"
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

### `location`

Specifies the location of the sorried proof within the specific commit of the repository (typically encoded with the lean "sorry" keyword). For example, opening the file in VS Code using

```shell
# open the file containing the sorry in VS Code
code <location.file>
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

Finally, we provide a unique ID to the sorry, built as a hash from the `repo` and `location` fields. We consider *any* change to *any* file in the repository as a change to *all* sorries in the repository (as a change elsewhere may affect definitions used in the statement, or lemmas available to the prover).

## List of repositories

This is a secondary JSON, which contains the repositories being tracked, and
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

