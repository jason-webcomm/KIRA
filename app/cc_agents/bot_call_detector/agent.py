"""
Bot Call Detector Agent

This module determines whether a message is directly calling the bot.
"""

import logging
import os

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
)

from app.config.settings import get_settings
from app.cc_utils.language_helper import detect_language


def create_system_prompt(bot_name: str) -> str:
    """Create system prompt for bot call detection.

    Args:
        bot_name: The name of the bot

    Returns:
        str: System prompt for bot call detection
    """
    # Create abbreviated name only for Korean names
    is_korean_name = detect_language(bot_name) == "Korean" if bot_name else False
    bot_short_name = bot_name[1:] if is_korean_name and len(bot_name) > 2 else None

    # Abbreviated name description
    short_name_desc = f' or "{bot_short_name}"' if bot_short_name else ''

    # Korean patterns
    korean_patterns = f'"{bot_name}", "{bot_name}야", "{bot_name}아", "{bot_name}씨", "{bot_name}님"'
    if bot_short_name:
        korean_patterns += f'\n  - "{bot_short_name}", "{bot_short_name}야", "{bot_short_name}아", "{bot_short_name}씨", "{bot_short_name}님"'

    system_prompt = f"""You are an agent that determines whether the user's message is directly calling the target "{bot_name}"{short_name_desc}.

## Core Behavior Rules
<important_actions>
1. If the message calls the target by name to talk or request a task, respond with true.
2. The following patterns indicate a direct call (respond with true):
  Korean patterns:
  - {korean_patterns}
  English patterns:
  - "{bot_name}", "Hey {bot_name}", "Hi {bot_name}", "{bot_name}," (case-insensitive)
  Slack mention patterns (IMPORTANT - these are direct calls):
  - "{bot_name} (@U...)" or "({bot_name}) (@U...)" followed by "님", "씨", etc.
  - Any message containing the target name with a Slack user ID mention (@U...) is a direct call
3. If the target name is mentioned but NOT directly addressed, respond with false.
4. If the target name is not present at all, respond with false.
</important_actions>

## Output Format
<output_format>
Target called: output "true"
Target not called: output "false"
</output_format>"""

    return system_prompt


async def call_bot_call_detector(
    message_text: str,
    bot_name: str = None
) -> bool:
    """
    Execute the bot call detection agent.

    Args:
        message_text: The message text sent by the user
        bot_name: The name of the bot (default: from settings)

    Returns:
        bool: Whether the bot was called
    """
    settings = get_settings()
    if not bot_name:
        bot_name = settings.BOT_NAME or "KIRA"

    system_prompt = create_system_prompt(bot_name)

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
            query = f"""Determine if the following message is directly calling the target "{bot_name}".

Message: {message_text}"""

            await client.query(query)

            async for message in client.receive_response():
                if isinstance(message, ResultMessage):
                    result_text = message.result.strip().lower()
                    logging.info(f"[BOT_CALL_DETECTOR] Response: {result_text}")
                    return "true" in result_text
    except Exception as e:
        logging.error(f"[BOT_CALL_DETECTOR] Error: {e}")

    return False
