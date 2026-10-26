# Milestone specs

Each milestone has one spec here, named `<id>-<slug>.md`, such as `b1-extraction.md`.

## Lifecycle

1. **Draft.** A spec is written and opened as a PR.
1. **Approved.** Vlad reviews the spec and merges it to `main`. Implementation starts only after that.
1. **Frozen.** The implementation PR links the spec. A change to what the milestone delivers needs Vlad's approval, in chat or in a PR comment, and is committed as `spec-change: …`, quoting his words and the time. A factual correction, such as a wrong number or contradicting wording, needs no approval and is committed the same way. These commits are the one exception to Conventional Commits; the PR description lists them under "Spec changes", since a squash merge drops commit subjects.

Specs have no status line: merged means approved. Implementation status is tracked in the tracking issue, [#53](https://github.com/biocypher/biotope/issues/53).

## Rules for writing a spec

- A spec **opens with its gap**: one sentence on what its need lacks today, then a map of what biotope already does for that need and why, verified in code. The spec covers only the gap ([#53](https://github.com/biocypher/biotope/issues/53)).
- A spec says **what and why**, not how. Most of it covers the goal and its reasons, scope, non-goals, interfaces and acceptance criteria. The design is a short sketch.
- **Binding:** the goal, scope, non-goals, interfaces and acceptance criteria. **Guidance:** the design sketch and the risks. The implementer may depart from the sketch and explains why in the PR; that needs no spec change.
- A spec aligns on goals, scope and interfaces; the implementer works out the details during development. **Interfaces** name only the surface others depend on, at the level of concepts and contracts, such as a Python protocol described in words or what a stored output promises later stages. Command options, configuration key names, file layouts and formats are decided by the implementer and documented in `docs/` by the implementation PR.
- Each **acceptance criterion** describes an observable outcome, carries an id (`AC-1`, `AC-2`, …) and names its test tier:
  - `unit`: runs on committed fixtures, without network, by default and in CI;
  - `live`: calls a real model endpoint or reads local documents that are not committed, may cost money, is marked `@pytest.mark.live` and never runs in CI;
  - `manual`: judged by Vlad, or by a user of a project such as REACH or InTRAC, and recorded in the PR.
- **Non-goals** are listed explicitly, so scope cannot grow unnoticed.
- **Freedom to operate** says what the implementer decides, so nobody needs a spec change for an internal choice.
- A spec fits in about 80 lines. If it grows much longer, it is probably describing the implementation.

## Template

```markdown
# <ID>: <title>

Needs: <milestones> · Roadmap decisions: <numbers>

## Gap and what biotope already does
One sentence on what the need lacks today. Then what biotope already does for it and why, verified in code.

## Goal and why
What exists afterwards that did not exist before, who needs it, and why. Quote the roadmap decisions this milestone must respect.

## Scope
## Non-goals
## Interfaces
The surface others depend on, as concepts and contracts.
## Acceptance criteria
- **AC-1** (unit) …
## Freedom to operate
## Design sketch (non-binding)
## Risks and open questions
## Evidence required in the PR
```
