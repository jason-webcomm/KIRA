"""
Bot Thread Context Detector Agent

Agent that determines if the bot is participating in a thread and if the current message is a follow-up query to the bot.
"""

import logging
import os

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
)
from slack_sdk.web.async_client import AsyncWebClient

from app.config.settings import get_settings


def create_system_prompt(bot_name: str) -> str:
    """Create system prompt for thread context detection

    Args:
        bot_name: Name of the bot

    Returns:
        str: System prompt for thread context detection
    """
    system_prompt = f"""You are an agent that analyzes thread conversations to determine if the user's message is a follow-up query to "{bot_name}".

## Core Action Principles
<important_actions>
1. Check if "{bot_name}" has previously answered in the thread conversation history.
2. Threads where the target did not participate must always return false.
3. Even if the target participated, return false if the current message is unrelated to the target.
4. Return true in the following cases:
   - Follow-up questions to the target's answer (e.g., "What is that?", "Tell me more", "How do I do it?")
   - References to the target's previous answers (e.g., "what you mentioned earlier", "what you told me about ~")
   - Additional requests for tasks the target has handled
   - When the thread topic is relevant to the target and the context indicates asking the target
5. Return false in the following cases:
   - Completely new questions on different topics
   - Conversations between other people
   - When the target has never participated in the thread
   - Everyday reactions/exclamations (e.g., "oh", "lol", "nice")
</important_actions>

## Output Format
<output_format>
Follow-up query to target: Output "true"
Not a query to target: Output "false"
</output_format>"""

    return system_prompt


async def call_bot_thread_context_detector(
    thread_ts: str,
    channel_id: str,
    current_message: str,
    client: AsyncWebClient
) -> bool:
    """
    Determine if the bot is participating in a thread and if the current message is a follow-up query to the bot

    Args:
        thread_ts: Thread timestamp
        channel_id: Channel ID
        current_message: Current user message
        client: Slack AsyncWebClient

    Returns:
        bool: True if it's a follow-up query to the bot
    """
    settings = get_settings()
    bot_name = settings.BOT_NAME or "KIRA"

    try:
        # 1. Fetch thread conversation history
        response = await client.conversations_replies(
            channel=channel_id,
            ts=thread_ts,
            limit=10  # Last 10 messages
        )

        if not response.get("ok"):
            logging.warning(f"[BOT_THREAD_CONTEXT] Failed to fetch thread replies: {response.get('error')}")
            return False

        # Lazy import to avoid circular import
        from app.cc_slack_handlers import get_bot_user_id
        bot_user_id = get_bot_user_id()
        thread_messages = []
        bot_participated = False

        for msg in response.get("messages", []):
            user_id = msg.get("user")
            text = msg.get("text", "")

            if user_id == bot_user_id:
                thread_messages.append(f"{bot_name}: {text}")
                bot_participated = True
            else:
                # Get user info (simply use user_id)
                thread_messages.append(f"User({user_id}): {text}")

        # Return False if bot didn't participate
        if not bot_participated:
            logging.info(f"[BOT_THREAD_CONTEXT] Bot not participated in thread {thread_ts}")
            return False

        # 2. Request judgment from LLM
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

        async with ClaudeSDKClient(options=options) as sdk_client:
            conversation = "\n".join(thread_messages)
            query = f"""Thread conversation history:
{conversation}

Current user message: {current_message}

Is this message a follow-up query to "{bot_name}"?"""

            await sdk_client.query(query)

            async for message in sdk_client.receive_response():
                if isinstance(message, ResultMessage):
                    result_text = message.result.strip().lower()
                    logging.info(f"[BOT_THREAD_CONTEXT] Response: {result_text}")
                    return "true" in result_text

    except Exception as e:
        logging.error(f"[BOT_THREAD_CONTEXT] Error: {e}")

    return False