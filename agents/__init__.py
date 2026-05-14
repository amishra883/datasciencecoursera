"""agentic-clipper — sub-agent package.

Each agent is a single module exposing one or two async entry points.
Shared layer:
  - agents.db      SQLite connection helper
  - agents.config  YAML config loader
  - agents.events  event-log writer
  - agents.models  dataclasses for records flowing between agents

See CLAUDE.md "Architecture / Agent topology" for the data flow.
"""
