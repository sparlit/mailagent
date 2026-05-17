# Autonomous AI Gmail Agent

A sophisticated, multi-threaded, and FOSS-compliant autonomous agent designed to keep your Gmail accounts organized and spam-free.

## Key Capabilities

### 1. Multi-Account Orchestration
Manage multiple Gmail accounts from a single instance. The agent iterates through all configured accounts and processes them in parallel.

### 2. High-Performance Parallel Processing
Built with a `ThreadPoolExecutor`, the agent processes multiple emails concurrently, ensuring rapid organization even for high-volume inboxes.

### 3. Intelligent Classification Engine
- **Regex-Powered:** Uses compiled regular expressions for precise and efficient matching.
- **Dynamic Rules:** Classification rules are stored in `rules.json`. You can add new categories or refine existing patterns without touching the code.
- **Context Aware:** Analyzes Subject, Sender, and Snippets to determine the best category.

### 4. Dynamic Action Workflows
Define what happens to each category in `rules.json`. The agent supports:
- `trash`: Move to trash (ideal for SPAM).
- `label`: Automatically apply the category as a label (e.g., "SOCIAL").
- `mark_read`: Mark the email as read.
- `archive`: Remove the email from the Inbox.
- `star`: Add a star to the email.

### 5. Production-Ready Robustness
- **Persistence:** Uses a local SQLite database with composite primary keys to track processed messages across multiple accounts.
- **Retry Logic:** Implements exponential backoff with jitter for Gmail API resilience.
- **Dynamic Rule Reloading:** Automatically reloads `rules.json` at every loop iteration, allowing for live configuration updates.

## How To Guide

### 1. Configuration (`.env`)
Create a `.env` file in the root directory. Supported variables:
- `GMAIL_ACCOUNTS`: A JSON array of account objects.
  - Example: `[{"credentials": "creds1.json", "token": "token1.json"}]`
- `CHECK_INTERVAL`: Time in seconds between pass-throughs (default: `300`).
- `MAX_WORKERS`: Number of threads for parallel processing (default: `10`).
- `DRY_RUN`: If `True`, logs actions but does not modify Gmail (default: `False`).
- `DASHBOARD_ENABLED`: Enable the web dashboard (default: `True`).
- `DASHBOARD_PORT`: Port for the Flask dashboard (default: `5000`).

### 2. Classification Rules (`rules.json`)
The agent uses `rules.json` to decide how to handle emails.
```json
{
  "SPAM": {
    "patterns": ["lottery", "prize"],
    "header_rules": [{"name": "X-Spam-Flag", "pattern": "YES"}],
    "actions": ["trash"]
  },
  "FINANCE": {
    "patterns": ["bank", "statement"],
    "actions": ["label", "star"]
  }
}
```
**Supported Actions:** `trash`, `label`, `mark_read`, `archive`, `star`.

### 3. Web Dashboard
If enabled, visit `http://localhost:5000` to view real-time statistics on processed emails, monitored accounts, and executed actions. The dashboard auto-refreshes every 30 seconds.

### 4. n8n Hierarchical Management Workflow
We provide a `workflow.json` for orchestration within n8n. This workflow implements a hierarchical team structure to manage project tasks continuously:
1. **Import:** In n8n, click "Workflows" -> "Import from File" and select `workflow.json`.
2. **Setup Assistants:** The workflow uses OpenAI Assistants. Ensure you have your OpenAI API Key configured in n8n.
3. **Hierarchy:**
   - **Project Manager:** Identifies codebase gaps and assigns tasks.
   - **Team Leaders:** Divide tasks and manage team members.
   - **Team Members:** Execute specific fixes/improvements.
4. **Loop:** The workflow runs in a continuous loop to ensure the agent is always improving.

## Setup

1. **FOSS Dependencies:** `pip install -r requirements.txt`
2. **Credentials:** Place your Google Cloud `credentials.json` in the root.
3. **Run:** `python main.py` or `docker-compose up -d`

## FOSS Principle
This project is built using 100% Free and Open Source Software.
