"""
Agent C: SQL Generator

This agent generates SQL queries from the selected tables, columns, and
natural language question.

For detailed development and testing, see: notebooks/agent-development/agent-c-dev.ipynb

Project Context:
- Generates SQL for Spider dataset queries (5,693 complex SQL queries)
- Must handle complex queries with multiple tables and relationships
- Works with ~9 foreign keys per database on average
- Generates explainable SQL with reasoning

Responsibilities:
- Generate SQL queries tailored to selected tables and columns
- Handle complex queries with foreign key relationships
- Implement decomposition prompts for complex queries
- Generate explainable SQL with clear reasoning
- Support self-correction prompts for query refinement

Implementation Strategies:
- Decomposition prompts for complex query breakdown
- Self-correction prompts for query refinement
- Agentic planning and tooling approaches
- Generate SQL that can be executed and explained
- Support for complex joins and subqueries
"""
