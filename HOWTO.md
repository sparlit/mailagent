# How-To Guide: Using New Features and Orchestration

This guide explains how to use the newly implemented features and the multi-team orchestration script.

## 1. New Classification Actions
You can now use `unstar`, `mark_important`, and `forward` as actions in your `rules.json`.

### Example `rules.json` update:
```json
{
  "IMPORTANT_WORK": {
    "patterns": ["urgent project", "client feedback"],
    "actions": ["label", "mark_important", "star"]
  },
  "READ_LATER": {
    "patterns": ["weekly digest"],
    "actions": ["label", "unstar"]
  },
  "FORWARD_TO_ASSISTANT": {
    "patterns": ["invoice", "billing"],
    "actions": ["forward:assistant@example.com", "label"]
  }
}
```

## 2. Viewing the Enhanced Dashboard
The dashboard now includes an aggregated summary of classification categories.
1. Run the agent: `python3 main.py`
2. Open `http://localhost:5000` in your browser.
3. Scroll down to see the "Category Summary" table.

## 3. Running the Multi-Team Orchestration
To simulate the hierarchical management structure and continuous improvement loop:
1. Run the orchestrator: `python3 src/orchestrator.py`
2. The script will output logs showing the interaction between the CEO, Project Manager, Team Leaders, and Agents.
3. The process runs in a continuous loop (Step 9) until cancelled (Ctrl+C).

## 4. Running Tests
To ensure codebase stability after making changes:
1. Install pytest: `pip install pytest`
2. Run tests: `python3 -m pytest`
