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
- `mark_read`: Mark the email as read to keep your unread count clean.

### 5. Production-Ready Robustness
- **Persistence:** Uses a local SQLite database to track processed message IDs, ensuring no email is ever processed twice.
- **Retry Logic:** Implements exponential backoff with jitter to handle Gmail API rate limits (429) and transient network errors.
- **Label Caching:** Thread-safe caching of Gmail labels to minimize API overhead and stay within quotas.
- **Full Inbox Coverage:** Handles API pagination to ensure 100% of unread messages are reached.

### 6. Seamless Deployment
- **Dockerized:** Includes `Dockerfile` and `docker-compose.yml` for easy, isolated deployment.
- **Graceful Shutdown:** Handles `SIGINT` and `SIGTERM` to ensure clean exits.
- **Managed Logging:** Uses rotating file handlers to maintain logs without consuming excessive disk space.

## Setup

1. **FOSS Dependencies:** `pip install -r requirements.txt`
2. **Credentials:** Place your Google Cloud `credentials.json` in the root.
3. **Configuration:**
   - Create a `.env` file based on the environment variables in `src/config.py`.
   - Configure multiple accounts in the `GMAIL_ACCOUNTS` variable.
4. **Run:** `python main.py` or `docker-compose up -d`

## FOSS Principle
This project is built using 100% Free and Open Source Software.
