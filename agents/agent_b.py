"""
Agent B: Table and Column Selector

This agent selects relevant tables and columns from the chosen database
based on the natural language question.

For detailed development and testing, see: notebooks/agent-development/agent-b-dev.ipynb

Project Context:
- Works with selected database from Agent A
- Each database has ~28 columns and ~9 foreign keys on average
- Must handle complex schema relationships and foreign key constraints
- Processes JSON schema descriptions from Spider dataset

Responsibilities:
- Identify appropriate tables and columns within selected schema
- Handle foreign key relationships and table joins
- Work with complex schemas (multiple tables, relationships)
- Provide explanations for table/column selection decisions

Implementation Strategies:
- Schema linking with explicit linking prompts
- Foreign-key surfacing and relationship mapping
- Decomposition prompts for complex queries
- Validation of table join possibilities
"""
