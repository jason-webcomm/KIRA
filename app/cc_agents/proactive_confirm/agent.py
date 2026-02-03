"""
Proactive Confirm Agent

Agent that determines whether a user's response is an answer to a pending confirm
"""

import logging
import os
from typing import Tuple, Optional, Dict, Any

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
)

from app.cc_utils.confirm_db import (
    get_channel_pending_confirms,
    update_confirm_response,
)
from app.config.settings import get_settings


def create_system_prompt() -> str:
    """Create system prompt for proactive confirm

    Returns:
        str: System prompt for proactive confirm
    """
    system_prompt = """You are an agent that determines whether a user's response is an approval to a confirmation request.

## Core Action Principles
<important_actions>
1. Consider the original user request, the bot's confirmation message, and the current user response.

2. Responses considered as approval:
   - "예", "네", "응", "ㅇㅇ", "ㅇ", "yes", "ok", "okay"
   - "부탁해", "도와줘", "그래", "좋아", "ㄱㄱ"
   - "해줘", "하자", "가능해", "가능"

3. Responses considered as rejection:
   - "아니", "아니요", "노", "no", "nope", "ㄴㄴ", "ㄴ"
   - "괜찮아", "됐어", "필요없어", "안돼"
   - New questions/conversations unrelated to the confirmation message

4. Ambiguous cases are treated as rejection.
</important_actions>

## Output Format
<output_format>
Approval: output "true"
Rejection: output "false"
</output_format>"""

    return system_prompt


async def call_proactive_confirm(
    user_text: str,
    channel_id: str,
    user_id: str,
    thread_ts: str = None
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Execute the proactive confirm agent.

    Args:
        user_text: User message
        channel_id: Channel ID
        user_id: User ID
        thread_ts: Thread timestamp (for thread isolation)

    Returns:
        Tuple[bool, Optional[Dict]]: (approval status, original_message)
        - (True, original_message): Approved, original_message needs processing
        - (False, None): Rejected or no pending confirm
    """
    settings = get_settings()

    # 1. Get pending confirms (isolated by thread_ts)
    pending_confirms = get_channel_pending_confirms(channel_id, user_id, thread_ts)

    if not pending_confirms:
        logging.info(f"[PROACTIVE_CONFIRM] No pending confirms for user {user_id} in channel {channel_id}")
        return False, None

    # Use the most recent confirm
    confirm = pending_confirms[0]
    confirm_id = confirm["confirm_id"]

    logging.info(f"[PROACTIVE_CONFIRM] Found pending confirm: {confirm_id}, message: '{confirm['confirm_message']}'")

    # 2. Determine if user response is approval or rejection
    system_prompt = create_system_prompt()

    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
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
        ],
        setting_sources=['project'],
        cwd=os.getcwd()
    )

    try:
        async with ClaudeSDKClient(options=options) as client:
            # Extract original user request text from DB
            original_user_text = confirm["original_request_text"]

            query = f"""Please check the following information:

**Original User Request:** {original_user_text}
**Bot Confirmation Message:** {confirm['confirm_message']}
**Current User Response:** {user_text}

Determine if the user's response is approval or rejection.

If approved, return "true".
If rejected, return "false".
"""

            await client.query(query)

            async for message in client.receive_response():
                if isinstance(message, ResultMessage):
                    result_text = message.result.strip().lower()
                    logging.info(f"[PROACTIVE_CONFIRM] Response: {result_text}")

                    approved = "true" in result_text

                    if approved:
                        # Approval: Update DB + restore original_message
                        update_confirm_response(
                            confirm_id=confirm_id,
                            user_id=user_id,
                            approved=True,
                            response=user_text
                        )

                        # Restored original_message from DB (current context is handled by cc_slack_handlers)
                        reconstructed_message = {
                            "user_text": confirm["original_request_text"],
                            "user_id": confirm["user_id"],
                            "user_name": confirm["user_name"],
                            "channel_id": confirm["channel_id"]
                            # message_ts, thread_ts are set to current context in cc_slack_handlers
                        }

                        logging.info(f"[PROACTIVE_CONFIRM] Approved! Returning reconstructed original_message")
                        return True, reconstructed_message
                    else:
                        # Rejection: Update DB to mark as rejected
                        update_confirm_response(
                            confirm_id=confirm_id,
                            user_id=user_id,
                            approved=False,
                            response=user_text
                        )
                        logging.info(f"[PROACTIVE_CONFIRM] Rejected, marked as rejected in DB")
                        return False, None

    except Exception as e:
        logging.error(f"[PROACTIVE_CONFIRM] Error: {e}")

    return False, None
