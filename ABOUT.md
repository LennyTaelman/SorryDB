# SorryDB and Leaderboard

This project creates a continuously updating benchmark and leaderboard based on
sorry statements in public Lean projects to stimulate the development of AI-assisted theorem
proving in real world conditions.

## Limitations of benchmarks for theorem proving

Benchmarks form an important driver for research in automated theorem proving,
but there are some drawbacks.

1. Many benchmarks focus on *competition mathematics*, which is not 
   representative for theorem proving in typical *research
   mathematics*.

Research mathematics is not necessarily harder, but typically far more heterogeneous. It
relies on a far larger and more diverse corpus of previously established definitions and results. Proofs may require anything from routine calculations to finding relevant lemmas, adapting techniques from other areas, or creating new abstractions. This
applies to both informal and formal proofs (e.g. in Lean).

2. Models based on LLMs are vulnerable to (pre)training *data contamination*.

As a consequence of these two points, it is hard to predict how benchmark scores
will translate into real-world performance in research mathematics. In fact:

3. Real-world adoption of models with state-of-the-art benchmark scores is
   almost non-existent.

Often, publishing benchmark results is the end goal of academic research
projects. Even when code and weights are available, turning those into
useful end-user systems remains challenging. See also [3].

## Using sorry statements from public repositories

Mathematicians often collaborate on formal mathematics projects in Lean, hosting their work on GitHub. These works-in-progress frequently contain formally stated theorems with proofs deferred to later stages, marked by the `sorry` placeholder.

Such statements vary wildly in subject area and difficulty. They range from major theorems
to routine lemmas that follow easily from the relevant results in the `mathlib`
library.

We propose to compare automated (formal) proof systems by testing their performance in proving such sorry statements. Advantages:

1. Sorry statements "in the wild" capture a wide range of different aspects of research mathematics.
2. Having a constant influx of *new* sorry statements mitigates the problem of data
   contamination.
3. Being able to fill a sorry in an ongoing formalization projection is almost
   by definition something that is useful to someone.

Compare with *SWE-Bench* [1], which aims to evaluate language models on real-world
software engineering tasks by using GitHub issues as a benchmark. See also
*LeanAgent* [2], which generated automated pull requests providing proofs for some sorry statements on repositories hosted on GitHub.

## The ecosystem

We envision a setup consisting of a *database* of sorries, a *leaderboard* server serving sorries from the database, and competing *clients* implementing different theorem proving systems. Below we describe this in more detail.

### The database

*SorryDB* is a continuously updating database of sorry statements from public
Lean repositories. It locally reproduces and verifies these statements, ensuring
they compile correctly and represent mathematical propositions (with type
`Prop`), not definitions to be filled. The database stores all information
necessary to locally reproduce the sorry statements.

This provides a source of real-world problems for training and evaluating AI
theorem provers. The continuous influx of new problems helps mitigate training
data contamination.

### The leaderboard server

The *leaderboard server* manages the live competition by selecting recent open sorry statements from the database, serving them to competitors, and verifying their solutions. It maintains a live ranking of all participating clients.

Eventually, when competitors become sufficiently performant, the leaderboard could also generate automated pull requests to incorporate the generated proofs into their repositories.

### Client

Clients poll the server for sorry statements, reproduce them locally, and
attempt to prove them within the given time limit. Successful solutions are uploaded
back to the server. We plan to provide sample client implementations using various Lean
interaction tools to facilitate participation.

### Scoring

Traditional benchmark percentages don't adequately capture performance in this
context due to widely varying problem difficulty, inclusion of potentially unsolvable
statements, and asynchronous participation of competitors.

Instead, we propose an ELO-like rating system that measures relative performance, updating scores whenever one competitor solves a problem that another failed to prove.

## References

1. Jimenez, C. E., Yang, J., Wettig, A., Yao, S., Pei, K., Press, O., & Narasimhan, K. (2023). SWE-bench: Can Language Models Resolve Real-World GitHub Issues? arXiv:2310.06770. https://arxiv.org/abs/2310.06770

2. Kumarappan, A., Tiwari, M., Song, P., George, R. J., Xiao, C., & Anandkumar, A. (2024). LeanAgent: Lifelong Learning for Formal Theorem Proving. arXiv:2410.06209. https://arxiv.org/abs/2410.06209

3. Rute, J. (2025). The last mile [Video]. Lean Together 2025. https://www.youtube.com/watch?v=Yr8dzfVkeHg
