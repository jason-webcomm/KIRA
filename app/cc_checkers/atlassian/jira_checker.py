"""
Jira Checker using Rovo MCP
Monitors Jira issues and collects data via Rovo MCP
"""

import asyncio
import logging
import os
from pprint import pprint
from typing import List, Dict, Any

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, ResultMessage
from app.config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


async def fetch_assigned_issues() -> List[Dict[str, Any]]:
    """
    Fetches Jira tickets assigned to the current user using Rovo MCP

    Returns:
        List of assigned issues
    """
    if not settings.ATLASSIAN_ENABLED:
        logger.error("[JIRA_CHECKER] Atlassian MCP is not enabled")
        return []

    prompt = """You are a Jira data collection agent.

**Task Instructions:**
1. Use `mcp__atlassian__*` tools to query Jira tickets assigned to you
2. Only return issues that are NOT in "Done" status
3. Maximum 10 results

**Output Format:**
Respond with ONLY a JSON array (no explanations):
```json
[
  {
    "key": "PROJ-123",
    "fields": {
      "summary": "...",
      "status": {"name": "..."},
      "priority": {"name": "..."},
      "assignee": {"displayName": "...", "emailAddress": "..."},
      "reporter": {"displayName": "...", "emailAddress": "..."},
      "created": "...",
      "updated": "...",
      "description": "...",
      "issuetype": {"name": "..."},
      "project": {"key": "...", "name": "..."}
    }
  }
]
```

**Note:** Return an empty array [] if no issues found"""

    # Atlassian MCP server configuration (Data Center) - use environment variables
    mcp_servers = {
        "atlassian": {
            "command": "npx",
            "args": ["mcp-cache", "npx", "-y", "mcp-remote", "http://localhost:9000/mcp"],
            "env": {
                "JIRA_URL": settings.JIRA_URL,
                "JIRA_PERSONAL_TOKEN": settings.JIRA_PERSONAL_TOKEN,
                "JIRA_SSL_VERIFY": "false"
            }
        }
    }

    options = ClaudeAgentOptions(
        system_prompt=prompt,
        model=settings.MODEL_FOR_SIMPLE,
        permission_mode="bypassPermissions",
        allowed_tools=["*"],
        disallowed_tools=[
            "Bash(curl:*)",
            "Bash(rm:*)",
            "Bash(rm -r*)",
            "Bash(rm -rf*)",
            "Read(./.env)",
            "Read(./credential.json)",
            "WebFetch",
            "Write",
            "Edit",
            "NotebookEdit",
        ],
        setting_sources=['project'],
        cwd=os.getcwd(),
        mcp_servers=mcp_servers,
    )

    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query("Please use mcp__atlassian__* tools to query Jira tickets assigned to you and return them as JSON.")

            result_message = ""
            async for message in client.receive_response():
                pprint(message)
                if isinstance(message, ResultMessage):
                    result_message = message.result.strip()
                    logger.info(f"[JIRA_CHECKER] MCP result received: {len(result_message)} chars")
                    break

            if not result_message:
                logger.info("[JIRA_CHECKER] No result from MCP")
                return []

            # JSON 파싱
            import json

            # ```json ``` 블록 제거
            if "```json" in result_message:
                result_message = result_message.split("```json")[1].split("```")[0].strip()
            elif "```" in result_message:
                result_message = result_message.split("```")[1].split("```")[0].strip()

            issues = json.loads(result_message)

            if not isinstance(issues, list):
                logger.error(f"[JIRA_CHECKER] Invalid response format: expected list, got {type(issues)}")
                return []

            logger.info(f"[JIRA_CHECKER] Fetched {len(issues)} assigned issues")
            if len(issues) == 0:
                logger.info(f"[JIRA_CHECKER] Raw response (empty): {result_message[:500]}")
            return issues

    except json.JSONDecodeError as e:
        logger.error(f"[JIRA_CHECKER] JSON parsing error: {e}")
        logger.error(f"[JIRA_CHECKER] Raw result: {result_message[:1000]}")
        return []
    except Exception as e:
        logger.error(f"[JIRA_CHECKER] Error fetching issues: {e}", exc_info=True)
        return []


async def process_issues_batch(issues: List[Dict[str, Any]]):
    """
    Process multiple issues in batches (background)

    Args:
        issues: List of issues
    """
    logger.info(f"[JIRA_PROCESSOR] Processing {len(issues)} issues in background")

    for idx, issue in enumerate(issues, 1):
        issue_key = issue.get("key", "")
        fields = issue.get("fields", {})

        summary = fields.get("summary", "")
        status = fields.get("status", {}).get("name", "")
        priority = fields.get("priority", {}).get("name", "")
        updated = fields.get("updated", "")

        # Generate issue URL
        issue_url = f"{settings.ATLASSIAN_JIRA_SITE_URL}/browse/{issue_key}"

        logger.info(f"[JIRA_PROCESSOR] [{idx}/{len(issues)}] {issue_key}: {summary}")
        logger.info(
            f"[JIRA_PROCESSOR] [{idx}/{len(issues)}] Status: {status}, Priority: {priority}"
        )
        logger.info(f"[JIRA_PROCESSOR] [{idx}/{len(issues)}] URL: {issue_url}")
        logger.info(f"[JIRA_PROCESSOR] [{idx}/{len(issues)}] Updated: {updated}")

    # 1. Exclude tickets already in DB
    from app.cc_checkers.atlassian.jira_agent import call_jira_task_extractor
    from app.cc_utils.jira_tasks_db import (
        get_pending_tasks,
        complete_task,
        get_existing_issue_keys,
    )
    from app.queueing_extended import enqueue_message

    existing_issue_keys = get_existing_issue_keys()
    new_issues = [
        issue for issue in issues if issue.get("key") not in existing_issue_keys
    ]

    if not new_issues:
        logger.info(
            f"[JIRA_PROCESSOR] All {len(issues)} issues already exist in DB, skipping agent call"
        )
    else:
        logger.info(
            f"[JIRA_PROCESSOR] Found {len(new_issues)} new issues out of {len(issues)} total"
        )

        # 2. Call agent to extract tasks from new tickets and save to DB
        result = await call_jira_task_extractor(new_issues)

        if result:
            logger.info(f"[JIRA_PROCESSOR] Jira task extraction result:")
            logger.info(f"[JIRA_PROCESSOR] {result}")
        else:
            logger.info(f"[JIRA_PROCESSOR] No tasks extracted from tickets")

    # 3. Get pending tasks from DB (always execute)
    pending_tasks = get_pending_tasks()

    if pending_tasks:
        logger.info(f"[JIRA_PROCESSOR] Found {len(pending_tasks)} pending tasks")

        # 4. Enqueue message to Slack queue
        for task in pending_tasks:
            task_id = task["id"]
            user_id = task.get("user")
            text = task.get("text")
            channel_id = task.get("channel")

            # Only add to queue if user, text, and channel all exist
            if user_id and text and channel_id:
                # Add to Slack queue (same pattern as web interface)
                await enqueue_message({
                    "text": text,
                    "channel": channel_id,
                    "ts": "",
                    "user": user_id,
                    "thread_ts": None,
                })
                logger.info(f"[JIRA_PROCESSOR] Enqueued task {task_id} to user {user_id}")

                # 5. Mark task as complete
                complete_task(task_id)
            else:
                logger.warning(
                    f"[JIRA_PROCESSOR] Task {task_id} missing user/text/channel, skipping"
                )

        logger.info(f"[JIRA_PROCESSOR] Processed {len(pending_tasks)} tasks")
    else:
        logger.info(f"[JIRA_PROCESSOR] No pending tasks to process")

    logger.info(f"[JIRA_PROCESSOR] Completed processing {len(issues)} issues")


async def check_jira_updates():
    """
    Check assigned Jira tickets and process in batches
    Called periodically by scheduler
    """
    if not settings.ATLASSIAN_ENABLED:
        logger.info("[JIRA_CHECKER] Atlassian MCP is not enabled")
        return

    if not settings.JIRA_CHECK_ENABLED:
        logger.info("[JIRA_CHECKER] Jira check is not enabled")
        return

    logger.info("[JIRA_CHECKER] Checking assigned Jira issues...")

    try:
        issues = await fetch_assigned_issues()

        if issues:
            logger.info(
                f"[JIRA_CHECKER] Found {len(issues)} assigned issues, starting background processing"
            )
            # Process as background task
            asyncio.create_task(process_issues_batch(issues))
        else:
            logger.info("[JIRA_CHECKER] No assigned issues found")

    except Exception as e:
        logger.error(f"[JIRA_CHECKER] Error in check_jira_updates: {e}", exc_info=True)
