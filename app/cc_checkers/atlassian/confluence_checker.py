"""
Confluence Checker using Rovo MCP
Monitors Confluence pages and collects data via Rovo MCP
"""

import asyncio
import logging
import os
from pprint import pprint
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, ResultMessage
from app.config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


async def fetch_recent_pages(hours: int = 1) -> List[Dict[str, Any]]:
    """
    Fetch recently updated Confluence pages using Rovo MCP (excluding pages authored by the bot)

    Args:
        hours: Time range to query (default 1 hour)

    Returns:
        List of recently updated pages
    """
    if not settings.ATLASSIAN_ENABLED:
        logger.error("[CONFLUENCE_CHECKER] Atlassian MCP is not enabled")
        return []

    # Cutoff time for time filter
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    cutoff_str = cutoff_time.strftime("%Y-%m-%d %H:%M")

    prompt = f"""You are a Confluence data collection agent.

**Task Instructions:**
1. Use Atlassian MCP to query recently updated Confluence pages
2. CQL: `lastmodified >= "{cutoff_str}" ORDER BY lastmodified DESC`
3. limit: 10

**Output Format:**
Respond with only a JSON array (no explanations):
```json
[
  {{
    "id": "123456",
    "title": "Example Page",
    "spaceId": "SPACE",
    "version": {{
      "authorId": "user-id-123",
      "authorEmail": "user@example.com",
      "createdAt": "2024-01-01T00:00:00.000Z"
    }}
  }}
]
```

**Note:** Return empty array [] if no pages found"""

    # Atlassian MCP server configuration (Data Center) - use environment variables
    mcp_servers = {
        "atlassian": {
            "command": "npx",
            "args": ["mcp-cache", "npx", "-y", "mcp-remote", "http://localhost:9000/mcp"],
            "env": {
                "CONFLUENCE_URL": settings.CONFLUENCE_URL,
                "CONFLUENCE_PERSONAL_TOKEN": settings.CONFLUENCE_PERSONAL_TOKEN,
                "CONFLUENCE_SSL_VERIFY": "false"
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
            await client.query("Please query the page list.")

            result_message = ""
            async for message in client.receive_response():
                pprint(message)
                if isinstance(message, ResultMessage):
                    result_message = message.result.strip()
                    logger.info(f"[CONFLUENCE_CHECKER] MCP result received: {len(result_message)} chars")
                    break

            if not result_message:
                logger.info("[CONFLUENCE_CHECKER] No result from MCP")
                return []

            # JSON parsing
            import json

            # Remove ```json ``` blocks
            if "```json" in result_message:
                result_message = result_message.split("```json")[1].split("```")[0].strip()
            elif "```" in result_message:
                result_message = result_message.split("```")[1].split("```")[0].strip()

            pages = json.loads(result_message)

            if not isinstance(pages, list):
                logger.error(f"[CONFLUENCE_CHECKER] Invalid response format: expected list, got {type(pages)}")
                return []

            # Filter by time and bot in Python (same as Legacy)
            filtered_pages = []
            for page in pages:
                version = page.get("version", {})
                modified_date_str = version.get("createdAt")
                author_id = version.get("authorId")
                author_email = version.get("authorEmail")

                if modified_date_str:
                    try:
                        # Parse ISO 8601 format
                        modified_date = datetime.fromisoformat(modified_date_str.replace('Z', '+00:00'))

                        # Re-validate time (MCP may have filtered incorrectly)
                        if modified_date >= cutoff_time:
                            # Exclude pages authored by the bot (same as Legacy)
                            if author_email and author_email == settings.BOT_EMAIL:
                                logger.info(f"[CONFLUENCE_CHECKER] Skipping page by bot: {page.get('title')}")
                                continue

                            filtered_pages.append(page)
                            logger.debug(f"[CONFLUENCE_CHECKER] Added page: {page.get('title')} by {author_email or author_id}")
                    except (ValueError, TypeError) as e:
                        logger.warning(f"[CONFLUENCE_CHECKER] Failed to parse date: {modified_date_str}, error: {e}")
                        continue

            logger.info(f"[CONFLUENCE_CHECKER] Fetched {len(filtered_pages)} pages modified in last {hours} hours (after Python filtering)")
            return filtered_pages

    except json.JSONDecodeError as e:
        logger.error(f"[CONFLUENCE_CHECKER] JSON parsing error: {e}")
        logger.error(f"[CONFLUENCE_CHECKER] Raw result: {result_message[:500]}")
        return []
    except Exception as e:
        logger.error(f"[CONFLUENCE_CHECKER] Error fetching pages: {e}", exc_info=True)
        return []


async def process_pages_batch(pages: List[Dict[str, Any]], chunk_size: int = 5):
    """
    Process multiple pages in batches (background)
    Split into smaller chunks to prevent context overflow

    Args:
        pages: List of pages
        chunk_size: Number of pages to process at once (default 5)
    """
    logger.info(f"[CONFLUENCE_PROCESSOR] Processing {len(pages)} pages in background (chunk_size={chunk_size})")

    for idx, page in enumerate(pages, 1):
        page_id = page.get("id", "")
        title = page.get("title", "")

        version = page.get("version", {})
        modified_date = version.get("createdAt", "")
        modified_by = version.get("authorId", "")

        # Generate page URL
        page_url = f"{settings.ATLASSIAN_CONFLUENCE_SITE_URL}/wiki/spaces/{page.get('spaceId', '')}/pages/{page_id}"

        logger.info(f"[CONFLUENCE_PROCESSOR] [{idx}/{len(pages)}] Title: {title}")
        logger.info(f"[CONFLUENCE_PROCESSOR] [{idx}/{len(pages)}] URL: {page_url}")
        logger.info(f"[CONFLUENCE_PROCESSOR] [{idx}/{len(pages)}] Modified: {modified_date} by {modified_by}")

    # Call agent to summarize only important pages (processed in chunks)
    from app.cc_checkers.atlassian.confluence_agent import call_confluence_summarizer, save_to_memory

    # Split pages into chunks
    chunks = [pages[i:i + chunk_size] for i in range(0, len(pages), chunk_size)]
    logger.info(f"[CONFLUENCE_PROCESSOR] Split into {len(chunks)} chunks")

    all_results = []
    for chunk_idx, chunk in enumerate(chunks, 1):
        logger.info(f"[CONFLUENCE_PROCESSOR] Processing chunk {chunk_idx}/{len(chunks)} ({len(chunk)} pages)")

        result = await call_confluence_summarizer(chunk)

        if result:
            logger.info(f"[CONFLUENCE_PROCESSOR] Chunk {chunk_idx}: Important pages found")
            all_results.append(result)
        else:
            logger.info(f"[CONFLUENCE_PROCESSOR] Chunk {chunk_idx}: No important pages")

    # Combine all chunk results and save to memory
    if all_results:
        combined_result = "\n\n---\n\n".join(all_results)
        logger.info(f"[CONFLUENCE_PROCESSOR] Saving {len(all_results)} chunk results to memory")
        await save_to_memory(combined_result)
    else:
        logger.info(f"[CONFLUENCE_PROCESSOR] No important pages to save")

    logger.info(f"[CONFLUENCE_PROCESSOR] Completed processing {len(pages)} pages")


async def check_confluence_updates():
    """
    Check recent Confluence page updates and process in batches
    Called periodically by scheduler
    """
    if not settings.ATLASSIAN_ENABLED:
        logger.info("[CONFLUENCE_CHECKER] Atlassian MCP is not enabled")
        return

    if not settings.CONFLUENCE_CHECK_ENABLED:
        logger.info("[CONFLUENCE_CHECKER] Confluence check is not enabled")
        return

    logger.info("[CONFLUENCE_CHECKER] Checking recent Confluence updates...")

    try:
        # Query pages updated within the recent time period
        pages = await fetch_recent_pages(
            hours=settings.CONFLUENCE_CHECK_HOURS or 1
        )

        if pages:
            logger.info(f"[CONFLUENCE_CHECKER] Found {len(pages)} updated pages, starting background processing")
            # Process as background task
            asyncio.create_task(process_pages_batch(pages))
        else:
            logger.info("[CONFLUENCE_CHECKER] No recent page updates found")

    except Exception as e:
        logger.error(f"[CONFLUENCE_CHECKER] Error in check_confluence_updates: {e}", exc_info=True)