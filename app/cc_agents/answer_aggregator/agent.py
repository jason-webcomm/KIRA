"""
Answer Aggregator Agent

This module checks whether a user's message is a response to a pending query,
and if all responses are complete, aggregates them and sends to the original requester via Slack message.
"""

import json
import logging
import os

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
)

from app.cc_tools.waiting_answer.waiting_answer_tools import create_waiting_answer_mcp_server
from app.cc_tools.slack.slack_tools import create_slack_mcp_server
from app.cc_utils.waiting_answer_db import get_user_pending_requests
from app.config.settings import get_settings


def create_system_prompt() -> str:
    """Create system prompt for Answer aggregator

    Returns:
        str: System prompt for answer processing and aggregation
    """
    system_prompt = """You are an agent that determines if a user's message is a response to a pending query and processes it accordingly.

## Core Action Principles
<important_actions>
Not relevant: If the user message is not related to any pending query, output only "false"

Relevant: If the user message is a response to a specific query, process in order:
  1. Update response using `mcp__waiting_answer__update_request`
  2. Add emoji to user message using `mcp__slack__answer_with_emoji`
  3. Check all_completed from `mcp__waiting_answer__update_request` result
  4. Only if all_completed is true:
     a. Get requester_id from `mcp__waiting_answer__update_request` result (original query sender ID)
     b. Get DM channel ID for requester_id using `mcp__slack__get_dm_channel_id`
     c. Aggregate all answers from all_responses and organize them neatly
     d. Send to original requester using `mcp__slack__forward_message` (request_answer=False, channel_id is DM channel ID from b)
</important_actions>

## Slack Forward Message Guide
<slack_forward_message_guide>
1. You MUST respond in the same language as the original query (request_content).
2. Always avoid expressions that reveal you are an AI or bot.
3. Do not include content unrelated to the request in the response.
4. Do not use excessive emojis.
5. Always replace system-related terminology with natural everyday expressions (e.g., "memory" → "remember/what I heard before", "file path" → "location/folder", "thread" → "conversation", "API call" → "I checked", "bug/error" → "issue", "debugging" → "checking", "trigger" → "execute").
6. Do not use markdown syntax (**, ##, -, >, ```, etc.). Instead, use line breaks and indentation for structure.
</slack_forward_message_guide>

## Guardrail Policy
<guardrails>
**Strict Policy:**
- Never call `mcp__slack__forward_message` if all_completed is false
- When calling `mcp__slack__forward_message`, must send to requester_id's DM channel (original requester, not the responder)
</guardrails>

## Output Format
<output_format>
Relevant: Output "true" after completing all operations
Not relevant: Output "false"
</output_format>"""

    return system_prompt


async def call_answer_aggregator(
    user_text: str,
    message_data: dict
) -> bool:
    """
    Check if the user has responded to a pending query and process it.

    Args:
        user_text: User's message text
        message_data: Message info (user_id, channel_id, thread_ts, etc.)

    Returns:
        bool: True if response completion was processed, False otherwise
    """
    user_id = message_data["user_id"]

    # 1. Check this user's pending queries awaiting response
    pending_requests = get_user_pending_requests(user_id)

    if not pending_requests:
        return False  # No pending queries awaiting response

    logging.info(f"[ANSWER_AGGREGATOR] User {user_id} has {len(pending_requests)} pending request(s)")

    # 2. Request judgment from LLM
    system_prompt = create_system_prompt()
    settings = get_settings()

    options = ClaudeAgentOptions(
        mcp_servers={
            "waiting_answer": create_waiting_answer_mcp_server(),
            "slack": create_slack_mcp_server(),
        },
        system_prompt=system_prompt,
        model=settings.MODEL_FOR_MODERATE,
        permission_mode="bypassPermissions",
        allowed_tools=[
            "mcp__waiting_answer__update_request",
            "mcp__slack__answer_with_emoji",
            "mcp__slack__get_dm_channel_id",
            "mcp__slack__forward_message"
        ],
        disallowed_tools=[
            "Bash(curl:*)",
            "Bash(rm:*)",
            "Bash(rm -r*)",
            "Bash(rm -rf*)",
            "Read(./.env)",
            "Read(./credential.json)",
            "WebFetch",
        ],
        setting_sources=['project'],
        cwd=os.getcwd()
    )

    try:
        async with ClaudeSDKClient(options=options) as client:
            query = f"""
Analyze the following information and process:

Pending queries awaiting response:
{json.dumps(pending_requests, ensure_ascii=False, indent=2)}

User's answer:
{user_text}

User message info:
- channel_id: {message_data.get('channel_id')}
- message_ts: {message_data.get('message_ts')}
- user_id: {message_data.get('user_id')}
"""
            await client.query(query)

            async for message in client.receive_response():
                if isinstance(message, ResultMessage):
                    result_text = message.result.strip().lower()
                    logging.info(f"[ANSWER_AGGREGATOR] Response: {result_text}")
                    return "true" in result_text
    except Exception as e:
        logging.error(f"[ANSWER_AGGREGATOR] Error: {e}")

    return False
