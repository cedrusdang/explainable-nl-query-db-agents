"""
Agent A: Database Selector

This agent selects the most relevant database from the available options
based on the natural language question.

For detailed development and testing, see: notebooks/agent-development/agent-a-dev.ipynb

Project Context:
- Spider dataset: 200 SQLite databases across 138 domains
- Each database: ~28 columns, ~9 foreign keys on average
- Database folders contain SQLite file + SQL creation script
- JSON files describe all database table schemas

Responsibilities:
- Choose most relevant database from 200+ available databases
- Use semantic understanding and similarity-based selection
- Work with pre-embedded database schemas
- Handle 138 different domains from Spider dataset

Implementation Strategies:
- Few-shot prompting, database-aware (DAIL)
- Schema linking with explicit linking prompts and foreign-key surfacing
- Semantic similarity for database matching
- Provide confidence scores and selection reasoning
"""
