"""
Prompt Generation Functions

This module generates system prompts and state prompts used by Claude SDK agents.
"""

import json
import os
from typing import Optional
from app.config.settings import get_settings
from app.cc_utils.language_helper import detect_language


def create_state_prompt(slack_data: Optional[dict] = None, message_data: Optional[dict] = None) -> str:
    """Generate state prompt based on Slack API data and current message information

    Args:
        slack_data: Data received from Slack API (channel, members, recent messages, etc.). Skipped if None
        message_data: Current message information (user_id, text, channel_id, thread_ts, etc.). Skipped if None

    Returns:
        str: Prompt for agent to understand current state
    """
    # Filesystem base directory
    settings = get_settings()
    filesystem_base_dir = settings.FILESYSTEM_BASE_DIR or os.getcwd()
    bot_name = settings.BOT_NAME or "bot"
    bot_email = settings.BOT_EMAIL or ""
    bot_organization = settings.BOT_ORGANIZATION or "Your Organization"
    bot_team = settings.BOT_TEAM or ""
    authorized_users_en = settings.BOT_AUTHORIZED_USERS_EN or ""
    authorized_users_kr = settings.BOT_AUTHORIZED_USERS_KR or ""
    confluence_default_page_id = settings.ATLASSIAN_CONFLUENCE_DEFAULT_PAGE_ID or ""

    # Build combined_data (only include non-None values)
    combined_data = {
        "filesystem_base_dir": filesystem_base_dir
    }
    if slack_data is not None:
        combined_data["slack_data"] = slack_data
    if message_data is not None:
        combined_data["current_message"] = message_data

    state_json = json.dumps(combined_data, ensure_ascii=False, indent=2)

    # Build sections (dynamic numbering)
    sections = []
    section_num = 0

    # 0. Your Identity (always included)
    sections.append(f"""### {section_num}. Your Identity
- Name: {bot_name}
- Email: {bot_email}
- Organization: {bot_organization}
- Team: {bot_team}
- Business Stakeholders (English): {authorized_users_en}
- Business Stakeholders (Korean): {authorized_users_kr}""")
    section_num += 1

    # 1. Channel information (only when slack_data is present)
    if slack_data is not None:
        # Check if this is a chat message (desktop chat)
        is_chat_message = slack_data.get("is_chat_message", False)

        channel_info = ""
        if is_chat_message:
            channel_info = f"""- This is a **desktop chat** message (not from Slack)
- Use `mcp__answer__answer` with `channel_type="console"` for responses
- For desktop chat, only `text` parameter is required"""

        sections.append(f"""### {section_num}. Channel Information (slack_data):
- `channel`: Current channel basic info (name, type, topic, purpose, member count)
- `members`: Users in the channel (user_id, real_name, display_name, email)
- `recent_messages`: Recent conversation history ("[username]: message content" format)
{channel_info}""")
        section_num += 1

    # 2. Current message (only when message_data is present)
    if message_data is not None:
        sections.append(f"""### {section_num}. Current Message (current_message):
- `user_id`: Slack ID of the user who sent the message
- `user_text`: Content of the message sent by the user
- `channel_id`: Channel ID where the message was sent
- `thread_ts`: Only present for thread messages
- `message_ts`: Timestamp of this message
- `files`: Attached file information (if present). Includes filename, URL, MIME type, etc.""")
        section_num += 1

    # 3. File system information (always included)
    sections.append(f"""### {section_num}. File System Information (FILESYSTEM_BASE_DIR):
- This directory is the base path used for creating or saving files.
- When working with files, use this path as the base and create subfolders as needed.""")
    section_num += 1

    # 4. Confluence Default Page (only when configured)
    if confluence_default_page_id:
        sections.append(f"""### {section_num}. Confluence Default Page:
- When user requests "upload to wiki", "write to Confluence", etc., use page ID `{confluence_default_page_id}`.
- Unless explicitly specifying a different page, create subpages under this page.""")
        section_num += 1

    # 5. Response language detection
    user_text = message_data.get("user_text", "") if message_data else ""
    response_language = detect_language(user_text)

    # Provide more explicit instructions based on detected language
    if response_language == "Traditional Chinese":
        response_instruction = "Traditional Chinese (繁體中文)"
    elif response_language == "Korean":
        response_instruction = "Korean (한국어)"
    else:
        response_instruction = "English"

    state_prompt = f"""
## RESPONSE LANGUAGE
You MUST respond in {response_instruction}. This is a critical requirement.

## State Information Required for Task Execution:
<state_data>
{chr(10).join(sections)}

{state_json}
</state_data>""".strip()

    return state_prompt



