# Agent setup

Repository skills guide a coding agent through the same Biotope CLI used in the
terminal. Install the [Python package](installation.md) in the project environment
as well; installing a skill does not install its dependencies.

## Choose a skill

| Skill               | Use it for                                                        |
| ------------------- | ----------------------------------------------------------------- |
| `biotope-croissant` | Source curation, typed Python mappings and Biotope graph builds   |
| `biocypher`         | Standalone BioCypher adapters, export schemas and database import |

Start with `biotope-croissant` for a Biotope project. Its reference files document
source generation, graph authoring and interpretation. Copy the entire skill
folder, including those references, when installing it manually.

## Claude Code

Add this repository as a marketplace and install its plugin:

```text
/plugin marketplace add biocypher/biotope
/plugin install biotope@biotope
```

Alternatively, copy the selected folders from the repository's `skills/` directory
into your project's `.claude/skills/`. See
[Claude Code's plugin guide](https://code.claude.com/docs/en/discover-plugins).

## Cursor

For a project-local installation, copy the selected skill folders into
`.cursor/skills/`.

Teams and Enterprise workspaces can use a team marketplace: open the Cursor
Dashboard, go to **Plugins → Team Marketplaces**, choose **Add Marketplace**, and
import `biocypher/biotope` from GitHub. See [Cursor's plugin guide](https://cursor.com/docs/plugins)
for access and installation settings.

## Codex

From the target project, with a clone of Biotope available at `../biotope`:

```bash
mkdir -p .agents/skills
cp -R ../biotope/skills/biotope-croissant .agents/skills/
```

Adjust the clone path to your checkout. Copy `skills/biocypher` in the same way
when working on a standalone BioCypher project. User-wide skills can be placed in
`~/.agents/skills/`. See the [Codex skills documentation](https://learn.chatgpt.com/docs/build-skills)
for discovery and scope.

## Work with the agent

Ask the agent to use the `biotope-croissant` skill and describe the intended graph,
for example:

> Use biotope-croissant to build a graph from the CSVs in `data/`. It should connect
> samples to donors so I can compare measurements by donor. Review the source
> metadata and explain any missing scientific decisions before choosing a mapping.

The agent records the purpose, reviews source descriptions, generates records and
authors the graph workspace. When construction is requested, it checks and runs
the selected pipeline, then reports outputs, exclusions and validation results.
Existing scientific choices remain part of the project; unresolved choices need
input from someone who knows the data.

Database import and querying require a separate task and environment. The
[tutorial](tutorial.md) covers file output, while the [authoring guide](mapping.md)
explains the Python contracts.

For an agent without skill support, `biotope init --agents-md` can add project-local
`AGENTS.md` instructions during initialization.
