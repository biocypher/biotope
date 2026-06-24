---
name: biochatter
description: Connect biomedical LLM chat to knowledge graphs, APIs, and document RAG with BioChatter. Use for natural-language Cypher over Neo4j, BioCypherPromptEngine query generation, DatabaseAgent, or general biomedical conversation with structured backends. Trigger on BioChatter, NL graph queries, Cypher generation, KG chat, schema_info.yaml querying, or conversational AI over biomedical data.
---

# BioChatter: LLM layer for biomedical apps

BioChatter is the harness — LLM connectivity, prompts, and agents. It does not build graphs; it queries graphs, APIs, and documents that already exist.

```bash
pip install biochatter
pip install "biochatter[ollama]"   # local models via Ollama
```

Docs: https://biochatter.org/

## Choose a mode

| Task | Entry point |
|------|-------------|
| NL query over a Neo4j KG | `DatabaseAgent` — see `references/kg-query.md` |
| Cypher generation only | `BioCypherPromptEngine.generate_query()` |
| General biomedical chat | `GptConversation` / `LangChainConversation` + `query()` |
| Document RAG | `DocumentEmbedder` + vectorstore — docs/features/rag.md |
| External API (OncoKB, etc.) | `APIAgent` — docs/api-docs/api-calling-base.md |

## Knowledge graph querying (primary)

**Prerequisites:** running graph DB + `schema_info.yaml` (from BioCypher `write_schema_info()`).

Read `references/kg-query.md` for full `DatabaseAgent` and `BioCypherPromptEngine` setup.

**Always** show the generated Cypher to the user. Prefer `use_reflexion=False` unless they ask for iterative refinement.

## General conversation

```python
from biochatter.llm_connect import GptConversation

conversation = GptConversation(model_name="gpt-4o", prompts={})
conversation.set_api_key(api_key="...")
msg, token_usage, correction = conversation.query("Explain CRISPR off-target effects.")
```

Supply domain system prompts via `prompts={}` or `append_system_message()` — raw passthrough to the LLM is rarely enough for production use.

## Providers

OpenAI, Anthropic, Google/Gemini, Azure, Ollama, Xinference, OpenRouter — each has a `*Conversation` class in `biochatter.llm_connect`. Set API keys / base URLs per provider docs.

## House rules

- BioChatter does not fix bad graphs — empty or wrong answers often mean upstream schema or id issues.
- One mode per task; don't pull in RAG/API agents unless the user asked.
- For web UI: BioChatter Light (Streamlit) or BioChatter Next (FastAPI + Next.js).
