# Knowledge graph querying

## Prerequisites

1. A **loaded graph database** (Neo4j is the primary supported backend for `DatabaseAgent`).
2. **`schema_info.yaml`** from `bc.write_schema_info()` after build — must include `is_schema_info: true` and `present_in_knowledge_graph` per entity. A plain `schema_config.yaml` alone is weaker; prefer schema info when available.

## BioCypherPromptEngine (Cypher generation only)

```python
import yaml
from biochatter.prompts import BioCypherPromptEngine
from biochatter.llm_connect import GptConversation

def create_conversation():
    conv = GptConversation(model_name="gpt-4o", prompts={})
    conv.set_api_key(api_key="...")
    return conv

with open("biocypher-out/schema_info.yaml") as f:
    schema = yaml.safe_load(f)

engine = BioCypherPromptEngine(
    schema_config_or_info_dict=schema,
    conversation_factory=create_conversation,
    model_provider="openai",
    model_name="gpt-4o",
)

cypher = engine.generate_query("Which proteins interact with TP53?")
# Execute cypher yourself against the DB
```

The engine selects entities, relationships, and properties from schema before generating Cypher. Edge `source`/`target` in schema config constrain direction — LLMs often reverse edge direction without this.

## DatabaseAgent (generate + execute)

```python
from biochatter.database_agent import DatabaseAgent
from biochatter.llm_connect import LangChainConversation

def conversation_factory():
    return LangChainConversation(
        model_provider="google",
        model_name="gemini-2.0-flash",
    )

agent = DatabaseAgent(
    model_provider="google",
    model_name="gemini-2.0-flash",
    connection_args={
        "host": "bolt://localhost",
        "port": "7687",
        "user": "neo4j",
        "password": "",
        "db_name": "neo4j",
    },
    schema_config_or_info_dict=schema,
    conversation_factory=conversation_factory,
    use_reflexion=False,
)
agent.connect()

docs = agent.get_query_results("How many nodes are in the graph?", k=10)
# docs[0].metadata["cypher_query"] — always show Cypher to the user
```

Set `use_reflexion=True` only when the user wants iterative query refinement (slower, less auditable).

## LLM providers

`biochatter.llm_connect` exposes provider-specific classes: `GptConversation`, `LangChainConversation`, `OllamaConversation`, `GeminiConversation`, etc. Match `model_provider` / `model_name` to the class and env vars (`OPENAI_API_KEY`, `GOOGLE_API_KEY`, …).

## Verify answers

- Surface generated Cypher in every response.
- Empty results → check labels/properties against `schema_info.yaml` or run `MATCH (n) RETURN labels(n), keys(n) LIMIT 25` in Neo4j Browser.
- Wrong counts → suspect graph construction, not the LLM — fix data upstream.

## Other BioChatter modes

- **General chat** — `Conversation.query()` without KG; see docs/features/chat.md
- **RAG** — vectorstore over documents; docs/features/rag.md
- **API agents** — structured database/API calls; docs/api-docs/api-calling-base.md

Load only the mode the user asked for.
