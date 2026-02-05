"""
Core Agent Operator Module

This module executes the core agent that performs actual tasks,
and manages pre/post tool usage hooks.
"""

import json
import logging
import os
import re

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
)

from app.cc_tools.slack.slack_tools import create_slack_mcp_server, get_slack_client
from app.cc_tools.scheduler.scheduler_tools import create_scheduler_mcp_server
from app.cc_tools.x.x_tools import create_x_mcp_server
from app.cc_tools.meeting_transcription.meeting_transcription_tools import (
    create_meetings_mcp_server,
)
from app.cc_tools.deepl.deepl_tools import create_deepl_tools_server
from app.cc_tools.files.files_tools import create_files_mcp_server
from app.cc_tools.answer import create_answer_mcp_server
from app.config.settings import get_settings, Settings
from app.cc_agents.state_prompt import create_state_prompt
from app.cc_utils.language_helper import detect_language

logger = logging.getLogger(__name__)


def build_mcp_servers_dict(settings: Settings) -> dict:
    """Generate a dictionary containing only MCP servers enabled by the configuration.

    Args:
        settings: Settings object

    Returns:
        dict: Dictionary of enabled MCP servers
    """
    import logging
    logger = logging.getLogger(__name__)
    # Default servers (always included)
    mcp_servers = {
        "slack": create_slack_mcp_server(),
        "scheduler": create_scheduler_mcp_server(),
        "files": create_files_mcp_server(),
        "answer": create_answer_mcp_server(),
        "time": {"command": "npx", "args": ["-y", "@mcpcentral/mcp-time"]},
        "context7": {"command": "npx", "args": ["-y", "@upstash/context7-mcp"]},
        "arxiv": {
            "command": "npx",
            "args": ["-y", "@langgpt/arxiv-paper-mcp@latest"],
        },
        "airbnb": {
            "command": "npx",
            "args": ["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"],
        },
        "youtube-info": {
            "command": "npx",
            "args": ["-y", "@limecooler/yt-info-mcp"],
        },
        "steam-review": {"command": "npx", "args": ["-y", "steam-review-mcp"]}
    }

    # Add conditional servers in dev.env order
    # MCP Settings - Perplexity
    if settings.PERPLEXITY_ENABLED:
        mcp_servers["perplexity"] = {
            "command": "npx",
            "args": ["-y", "server-perplexity-ask"],
            "env": {"PERPLEXITY_API_KEY": settings.PERPLEXITY_API_KEY},
        }

    # MCP Settings - DeepL
    if settings.DEEPL_ENABLED:
        mcp_servers["deepl"] = create_deepl_tools_server()

    # MCP Settings - GitHub
    if settings.GITHUB_ENABLED:
        mcp_servers["github"] = {
            "type": "http",
            "url": "https://api.githubcopilot.com/mcp/",
            "headers": {
                "Authorization": f"Bearer {settings.GITHUB_PERSONAL_ACCESS_TOKEN}"
            }
        }

    # MCP Settings - GitLab
    if settings.GITLAB_ENABLED:
        mcp_servers["gitlab"] = {
            "command": "npx",
            "args": ["mcp-cache", "npx", "-y", "@zereight/mcp-gitlab"],
            "env": {
                "GITLAB_PERSONAL_ACCESS_TOKEN": settings.GITLAB_PERSONAL_ACCESS_TOKEN,
                "GITLAB_API_URL": settings.GITLAB_API_URL,
                "GITLAB_READ_ONLY_MODE": "false",
                "USE_GITLAB_WIKI": "false",
                "USE_MILESTONE": "false",
                "USE_PIPELINE": "false",
            },
        }

    # MCP Settings - Gitea
    if settings.GITEA_ENABLED:
        host = settings.GITEA_HOST or "https://gitea.com"
        logger.info(f"[MCP_CONFIG] Gitea MCP enabled (stdio mode): HOST={host}, TOKEN={'SET' if settings.GITEA_ACCESS_TOKEN else 'NOT SET'}, DISALLOWED_TOOLS={settings.GITEA_DISALLOWED_TOOLS or 'NONE'}")
        mcp_servers["gitea"] = {
            "command": "gitea-mcp",
            "args": ["-t", "stdio", "--host", host],
            "env": {
                "GITEA_ACCESS_TOKEN": settings.GITEA_ACCESS_TOKEN
            }
        }
    else:
        logger.info("[MCP_CONFIG] Gitea MCP disabled")

    # MCP Settings - Microsoft 365 (Lokka)
    if settings.MS365_ENABLED:
        mcp_servers["ms365"] = {
            "command": "npx",
            "args": ["mcp-cache", "npx", "-y", "@batteryho/lokka-cached"],
            "env": {
                "TENANT_ID": settings.MS365_TENANT_ID,
                "CLIENT_ID": settings.MS365_CLIENT_ID,
                "USE_INTERACTIVE": "true"
            }
        }

    # MCP Settings - Atlassian Data Center (Confluence, Jira)
    if settings.ATLASSIAN_ENABLED:
        logger.info(f"[MCP_CONFIG] Atlassian MCP enabled (remote mode)")
        env_vars = {}
        if settings.JIRA_PERSONAL_TOKEN and settings.JIRA_URL:
            env_vars["JIRA_URL"] = settings.JIRA_URL
            env_vars["JIRA_PERSONAL_TOKEN"] = settings.JIRA_PERSONAL_TOKEN
            env_vars["JIRA_SSL_VERIFY"] = "false"
        if settings.CONFLUENCE_PERSONAL_TOKEN and settings.CONFLUENCE_URL:
            env_vars["CONFLUENCE_URL"] = settings.CONFLUENCE_URL
            env_vars["CONFLUENCE_PERSONAL_TOKEN"] = settings.CONFLUENCE_PERSONAL_TOKEN
            env_vars["CONFLUENCE_SSL_VERIFY"] = "false"

        if env_vars and settings.ATLASSIAN_MCP_REMOTE_URL:
            mcp_servers["atlassian"] = {
                "command": "npx",
                "args": ["mcp-cache", "npx", "-y", "mcp-remote", settings.ATLASSIAN_MCP_REMOTE_URL],
                "env": env_vars
            }
        else:
            logger.warning("[MCP_CONFIG] Atlassian MCP enabled but no JIRA/CONFLUENCE credentials or ATLASSIAN_MCP_REMOTE_URL set, skipping")
    else:
        logger.info("[MCP_CONFIG] Atlassian MCP disabled")

    # MCP Settings - TABLEAU MCP
    if settings.TABLEAU_ENABLED:
        mcp_servers["tableau"] = {
            "command": "npx",
            "args": ["mcp-cache", "npx", "-y", "@tableau/mcp-server@latest"],
            "env": {
                "SERVER": settings.TABLEAU_SERVER,
                "SITE_NAME": settings.TABLEAU_SITE_NAME,
                "PAT_NAME": settings.TABLEAU_PAT_NAME,
                "PAT_VALUE": settings.TABLEAU_PAT_VALUE
            }
        }

    # MCP Settings - X (Twitter)
    if settings.X_ENABLED:
        mcp_servers["x"] = create_x_mcp_server()

    # MCP Settings - Clova Speech
    if settings.CLOVA_ENABLED:
        mcp_servers["meeting_transcription"] = create_meetings_mcp_server()

    # Computer Use - Chrome
    if settings.CHROME_ENABLED:
        mcp_servers["playwright"] = {
            "command": "npx",
            "args": [
                "mcp-cache",
                "npx",
                "@playwright/mcp@latest",
                "--browser",
                "chrome",
                "--user-data-dir",
                f"{settings.FILESYSTEM_BASE_DIR}/chrome_profile",
                "--caps",
                "vision",
                "--image-responses",
                "allow",
                "--output-dir",
                f"{settings.FILESYSTEM_BASE_DIR}/files/",
            ],
        }

    # MCP Settings - Custom Remote MCP Servers
    if settings.REMOTE_MCP_SERVERS:
        try:
            remote_servers = json.loads(settings.REMOTE_MCP_SERVERS)
            for server in remote_servers:
                name = server.get("name", "").strip()
                url = server.get("url", "").strip()
                if name and url:
                    mcp_servers[name] = {
                        "command": "npx",
                        "args": ["-y", "mcp-remote", url],
                    }
        except json.JSONDecodeError as e:
            logging.warning(f"[OPERATOR_AGENT] Failed to parse REMOTE_MCP_SERVERS: {e}")

    # AutoMem Memory MCP
    if settings.AUTOMEM_ENABLED:
        logger.info(f"[MCP_CONFIG] AutoMem MCP enabled: HOST={settings.AUTOMEM_HOST}")
        mcp_servers["memory"] = {
            "command": "npx",
            "args": ["-y", "@verygoodplugins/mcp-automem"],
            "env": {
                "AUTOMEM_ENDPOINT": f"http://{settings.AUTOMEM_HOST}:8001",
                "AUTOMEM_API_KEY": settings.AUTOMEM_API_KEY or "",
            }
        }
    else:
        logger.info("[MCP_CONFIG] AutoMem MCP disabled")

    return mcp_servers


def build_tool_usage_rules(settings: Settings) -> str:
    """Generate only tool usage rules enabled by the configuration.

    Args:
        settings: Settings object

    Returns:
        str: Tool usage rules string
    """
    bot_name = settings.BOT_NAME or "KIRA"

    # Basic rules (always included)
    rules = f"""## Tool Usage Principles
<how_to_use_tool>
- Before performing a request, first check the current time using `mcp__time__get_current_time`, and use that as the reference for information gathering. Relative time expressions like 'yesterday', 'tomorrow', 'next week', 'last year', 'this year' must be converted to exact dates based on the confirmed current time for searching/filtering.
- **CRITICAL**: You MUST CALL `mcp__answer__answer` to send responses. Do not just talk about using the tool - actually invoke it!
  - For Slack messages: `mcp__answer__answer({{"channel_type": "slack", "channel_id": "...", "text": "...", "message_ts": "...", "channel_type_value": "..."}})`
  - For console/desktop chat: `mcp__answer__answer({{"channel_type": "console", "text": "..."}})`
- When using `mcp__answer__answer` for Slack, include the tool call results, sources, and links as detailed as possible without omission.
- When a user uploads a file and a Slack file URL is provided, use `mcp__slack__download_file_to_channel` to download the file before processing.
- `<!subteam^slack_group_id>` format represents a group tag. When this group tag is included in the input, call `mcp__slack__get_usergroup_members` tool first, read the user information in the group, then execute the instruction.
- When you need to reference longer conversation context or full thread conversations, call `mcp__slack__get_thread_replies` tool to retrieve the data.
- If tool calls reach 3 or more, you can use `mcp__slack__answer_with_emoji` to briefly indicate the work status.
- If tool calls reach 8 or more, you can use `mcp__answer__answer` for intermediate reporting. However, **when the task is complete, you MUST use `mcp__answer__answer` one more time to provide the final result.** Do not just do intermediate reporting and finish.
- When forwarding messages to others, use `mcp__slack__forward_message`. If a response is needed for the message forwarding, set `request_answer=True`.
  - **No Duplicate Sending**: When sending the same message to multiple people, do NOT call `mcp__slack__forward_message` multiple times. Include all recipients in the respondents list and call it **only once**.
  - **No Personalization**: Do not add personalized greetings (e.g., "Hello, XXX"). Send the same message to all recipients.
  - **Exception**: Only call separately when you need to ask completely different questions to each person.
- The `text` parameter of `mcp__scheduler__*` tools is **the command that the virtual resident employee will receive at scheduled execution time**. Write it as a command to be given to the virtual resident employee.
  - **Command Start**: Must be written according to RESPONSE LANGUAGE. (Korean: "{bot_name}-nim, " / Traditional Chinese: "{bot_name}，" / English: "{bot_name}, ")
  - **Include Specific Tasks**: The user's command to be executed by the virtual employee must be **completely included**. Include all necessary links and details.
  - **Korean Example**: User "summarize it" → text: "{bot_name}-nim, please summarize the content of https://your-domain.atlassian.net/wiki/spaces/SPACE/pages/123456 and announce it to the channel"
  - **Chinese Example**: User "頁面摘要" (page summary) → text: "{bot_name}，請摘要 https://your-domain.atlassian.net/wiki/spaces/SPACE/pages/123456 這頁面內容並通知頻道"
  - **English Example**: User "summarize the page" → text: "{bot_name}, summarize the content of https://your-domain.atlassian.net/wiki/spaces/SPACE/pages/123456 and announce it to the channel"
- Use `mcp__airbnb__*` tools when looking for workshop locations.
- When an arXiv paper link is provided (e.g., https://arxiv.org/), use `mcp__arxiv__*` tools.
- When looking for code-related documentation, use `mcp__context7__*` tools.
"""

    # Add conditional rules in dev.env order
    conditional_rules = []

    # MCP Settings - Perplexity
    if settings.PERPLEXITY_ENABLED:
        conditional_rules.append(
            "- When you need to search/synthesize information from across the web, use `mcp__perplexity__*` tools. If Perplexity response includes Citations (source links), be sure to include them in your answer."
        )

    # MCP Settings - DeepL
    if settings.DEEPL_ENABLED:
        conditional_rules.append(
            "- When translation requests are made, use `mcp__deepl__*` tools. For binary files, do not use the Read tool - pass the file path directly."
        )

    # MCP Settings - GitHub
    if settings.GITHUB_ENABLED:
        conditional_rules.append(
            "- For GitHub repository tasks (issues, PRs, file management, etc.), use `mcp__github__*` tools."
        )

    # MCP Settings - GitLab
    if settings.GITLAB_ENABLED:
        conditional_rules.append(
            "- When a GitLab link is provided (e.g., https://gitlab.com/, https://git.company.com/), use `mcp__gitlab__*` tools."
        )

    # MCP Settings - Gitea
    if settings.GITEA_ENABLED:
        if settings.GITEA_DISALLOWED_TOOLS:
            conditional_rules.append(
                "- For Gitea tasks, use `mcp__gitea__*` tools. (Disallowed patterns: " + settings.GITEA_DISALLOWED_TOOLS + ")"
            )
        else:
            conditional_rules.append(
                "- When a Gitea link is provided (e.g., https://gitea.com/, https://git.company.com/), use `mcp__gitea__*` tools."
            )

    # MCP - Microsoft 365 (Lokka)
    if settings.MS365_ENABLED:
        conditional_rules.append(
            "- For Microsoft 365 tasks, use `mcp__ms365__*` tools. You can manage Outlook emails, calendar events, OneDrive files, and SharePoint documents (https://company-my.sharepoint.com/, https://company.sharepoint.com/sites/Team)."
        )

    # MCP - Atlassian
    if settings.ATLASSIAN_ENABLED:
        conditional_rules.append(
            "- When an Atlassian (Confluence/Jira) link is provided (e.g., https://your-domain.atlassian.net/, https://confluence.company.com/, https://jira.company.com/), first use the `confluence-deep-reader` skill and then use `mcp__atlassian__*` tools according to the workflow."
        )

    # MCP - Tableau
    if settings.TABLEAU_ENABLED:
        conditional_rules.append(
            "- For Tableau data query requests, use `mcp__tableau__*` tools to query data and answer. If the user does not specify an exact dashboard, select and show the most frequently used dashboard."
        )

    # MCP Settings - X (Twitter)
    if settings.X_ENABLED:
        conditional_rules.append(
            "- When an X tweet link is provided (e.g., x.com, twitter.com), use `mcp__x__*` tools. When posting a tweet, it must be within 250 characters."
        )

    # Voice Input Channel - Clova (Meeting Transcription)
    if settings.CLOVA_ENABLED:
        conditional_rules.append(
            "- For meeting transcription requests, use `mcp__meeting_transcription__*` tools. First, use `mcp__meeting_transcription__list_meeting_files` to query recording files by date, then use `mcp__meeting_transcription__transcribe_meeting` to extract text and create meeting minutes. If no date is mentioned, use the most recent file."
        )

    # Computer Use - Chrome
    if settings.CHROME_ENABLED:
        conditional_rules.extend([
            "- When you need to check multiple posts or content on specific sites, use the `web-navigation-strategies` skill and then `mcp__playwright__*` tools according to the workflow.",
            "- When looking for dining/restaurant locations for team dinners, use `mcp__playwright__*` tools. Search restaurants on Catchtable (app.catchtable.co.kr), and collect blog review links for each restaurant from Naver.",
            "- When saving screenshots with `mcp__playwright__browser_take_screenshot`, specify the `filename` parameter as `{{channel_id}}/filename.png`.",
        ])

    # MCP Settings - Custom Remote MCP Servers
    if settings.REMOTE_MCP_SERVERS:
        try:
            remote_servers = json.loads(settings.REMOTE_MCP_SERVERS)
            for server in remote_servers:
                name = server.get("name", "").strip()
                instruction = server.get("instruction", "").strip()
                if name and instruction:
                    conditional_rules.append(f"- In the following cases, you must use `mcp__{name}__*`: {instruction}")
        except json.JSONDecodeError:
            pass

    # Add conditional rules to basic rules
    if conditional_rules:
        rules += "\n".join(conditional_rules) + "\n"

    rules += "</how_to_use_tool>"

    return rules


async def save_to_memory(
    query: str, final_message: str, slack_data: dict, message_data: dict
) -> None:
    """
    Add conversation content to memory queue.

    Args:
        query: User query
        final_message: Final answer
        slack_data: Slack API data (includes channel, member info)
        message_data: Current message info (includes user_name, user_id)
    """
    try:
        from app.queueing_extended import enqueue_memory_job

        channel_info = slack_data.get("channel", {})
        channel_id = channel_info.get(
            "channel_id", message_data.get("channel_id", "unknown")
        )
        channel_name = channel_info.get("channel_name", "unknown")
        channel_type = channel_info.get("channel_type", "unknown")

        # Detect language for appropriate memory query
        detected_lang = detect_language(query)

        # Language-specific memory queries
        if detected_lang == "Traditional Chinese":
            memory_query = f"""以下是剛完成的 Slack 對話內容。請保存對未來對話有用的資訊。

**頻道:**
- ID: {channel_id}
- 名稱: {channel_name}
- 類型: {channel_type}

**使用者:**
- 名稱: {message_data['user_name']}
- ID: {message_data['user_id']}

**請求:**
{query}

**作業處理記錄:**
{final_message}

請使用 `slack-memory-store` skill 將此資訊分類到適當的類別並保存。
請務必保存作業的成功/失敗案例。
與團隊同事相關的事項請務必保存。"""
        elif detected_lang == "Korean":
            memory_query = f"""This is a Slack conversation that was just completed. Please save any information that would be useful for future conversations.

**Channel:**
- ID: {channel_id}
- Name: {channel_name}
- Type: {channel_type}

**User:**
- Name: {message_data['user_name']}
- ID: {message_data['user_id']}

**Request:**
{query}

**Work Processing History:**
{final_message}

Use the `slack-memory-store` skill to categorize and save this information.
Be sure to save success/failure cases of the work.
Matters related to team colleagues must be saved."""
        else:
            memory_query = f"""The following is a completed Slack conversation. Please save any information that would be useful for future conversations.

**Channel:**
- ID: {channel_id}
- Name: {channel_name}
- Type: {channel_type}

**User:**
- Name: {message_data['user_name']}
- ID: {message_data['user_id']}

**Request:**
{query}

**Work Processing History:**
{final_message}

Use the `slack-memory-store` skill to categorize and save this information.
Be sure to save success/failure cases of the work.
Matters related to team colleagues must be saved."""

        # Add job to memory queue (processed sequentially)
        await enqueue_memory_job({"memory_query": memory_query})
        logging.info(f"[OPERATOR_AGENT] Memory job enqueued")
    except Exception as e:
        logging.error(f"[OPERATOR_AGENT] Memory enqueue failed: {e}")


def create_system_prompt(state_prompt: str) -> str:
    """Generate system prompt for the Core agent

    Args:
        state_prompt: Current state prompt generated by create_state_prompt()

    Returns:
        str: System prompt including agent behavior principles and tool usage principles
    """
    # Get bot name
    settings = get_settings()
    bot_name = settings.BOT_NAME or "KIRA"
    bot_role = settings.BOT_ROLE or ""

    # Dynamically generate tool usage rules
    tool_usage_rules = build_tool_usage_rules(settings)

    # Role/position section (only if set)
    role_section = ""
    if bot_role:
        role_section = f"""

## Role in the Company
<bot_role>
{bot_role}
</bot_role>"""

    system_prompt = f"""You are {bot_name}, a virtual resident employee who communicates via Slack.

# Basic Guidelines
Accurately and efficiently handle colleague requests and respond through **the unified answer tool**, organizing work processing records.
{role_section}

{state_prompt}

## Core Behavioral Principles
<important_actions>
1. Check the "Related Memory" section in state_data. The previous agent has organized the memory needed for the request.
2. **Response Handling - CRITICAL**:
   - For Slack messages: You MUST CALL `mcp__answer__answer` with `channel_type="slack"`. Do not output text directly!
   - For console/desktop chat: You MUST CALL `mcp__answer__answer` with `channel_type="console"`. Do not output text directly! The tool will output to stdout.
   - Example for console: `mcp__answer__answer({{"channel_type": "console", "text": "現在是下午 4 點"}})`
3. Respond using the appropriate method even when requests are unclear, tasks are impossible, or you need to suggest options.
4. Even when a task fails, provide failure reasons and alternatives in your response.
5. File operation paths:
   - Permanent storage files: FILESYSTEM_BASE_DIR/files/{{channel_id}}/
   - Temporary files: FILESYSTEM_BASE_DIR/files/{{channel_id}}/tmp/ (must delete after task completion)
   - Files created must be uploaded to Slack using `mcp__slack__upload_file` (for Slack messages).
   - Ensure Korean text does not corrupt when creating files. Use `encoding='utf-8'` for text files. For PDF, refer to the `pdf` skill's Korean Font Support.
6. When users request "remember this" or "save this", respond positively. Actual storage is automatically handled by the next memory agent.
   - For requests like "keep it for me" or "store this" with files: Download the file using `mcp__slack__download_file_to_channel` and save to FILESYSTEM_BASE_DIR/files/{{channel_id}}/, then respond with a confirmation message.
7. Upon task completion, return work history including the following information. It will be saved to memory:
    - Tools used and result summary
    - Sources and links
    - Response details to colleague requests
</important_actions>

## Skill Usage Principles
<how_to_use_skill>
1. When working with PPT, DOCX, PDF, XLSX documents, you MUST use `ppt`, `docx`, `pdf`, `xlsx` skills. Set the author to "{bot_name}" unless otherwise specified.
2. For memory/record cleanup requests like "organize memories" or "cleanup memory", use the `slack-memory-cleanup` skill.
3. **CRITICAL - Response Handling**: You MUST CALL `mcp__answer__answer` tool to send responses. Do NOT just describe what you would do - actually invoke the tool!
   - For console messages: `mcp__answer__answer({{"channel_type": "console", "text": "Your response"}})`
   - For Slack messages: `mcp__answer__answer({{"channel_type": "slack", "channel_id": "...", "text": "...", "message_ts": "..."}})`
   - For file uploads to Slack, use `mcp__slack__upload_file`
</how_to_use_skill>

{tool_usage_rules}

## AutoMem Memory System
<memory_instructions>
When AutoMem MCP is available, use it for persistent, cross-session memory:

### When to Store
- User preferences and working patterns
- Technical decisions and their rationale
- Bug workarounds and solutions
- Project-specific conventions

### How to Store
Use `mcp__memory__store_memory`:
- Content: Brief summary (150-300 chars)
- Tags: ["project-name", "category"]
- Importance: 0.5-0.9 (0.9=critical, 0.7=patterns, 0.5=context)
- Metadata: {{"source": "slack", "channel": "...", "user": "..."}}

### How to Recall
Use `mcp__memory__recall_memory`:
- query: Natural language search
- tags: Filter by project/category
- expand_entities: true for related memories

### How to Associate
Use `mcp__memory__associate_memories`:
- RELATES_TO: General connection
- PREFERS_OVER: This is a better approach
- EXEMPLIFIES: This is an example of pattern
- PART_OF: This is part of a larger effort
</memory_instructions>

## SLACK Response Guide for Colleague Requests
<slack_answer_guide>
1. **CRITICAL LANGUAGE REQUIREMENT**: You MUST respond in the language specified in "RESPONSE LANGUAGE" section above. This is an absolute requirement that overrides all other instructions. DO NOT respond in Korean unless Korean is explicitly specified in the "RESPONSE LANGUAGE" section.
2. If there are response guidelines for channels and users, follow those guidelines.
3. Avoid expressions that reveal you are an AI or bot.
4. Do not include content unrelated to the request in your response.
5. Do not use excessive emojis.
6. Always replace system-related terminology with natural everyday expressions. (e.g., "memory" → "what I remember / something I heard before", "file path" → "location / folder", "thread" → "conversation", "API call" → "I checked and found", "bug/error" → "issue / problem", "debugging" → "checking", "trigger" → "execute / run")
7. Do not use markdown syntax (**, ##, -, >, ```, etc.). Instead, use line breaks and indentation for structuring.
8. Always include sources and links from tool call results in detail.
9. Always base analysis on the results of tool calls.
10. If you are unsure about any aspect or lack necessary information for a report, respond that there is insufficient information.
</slack_answer_guide>

## Guardrail Policy
<guardrails>
**File System Access Restrictions:**
- Never access files or directories outside FILESYSTEM_BASE_DIR
- Reading or modifying system files, home directories, configuration files is strictly prohibited
- File operations must be limited to within FILESYSTEM_BASE_DIR

**Specific Site Reading Depth Decision Restrictions:**
- When reading multiple contents or posts on specific sites, never infer when reading depth is uncertain
- Ask the user clearly what level to read
- Reading at wrong depth to waste time or miss information is strictly prohibited

**Slack Message Sending Restrictions:**
- Never infer when user_id is unknown or uncertain
- Ask the user clearly who to send to, or request a Slack tag (@username)
- Sending messages with incorrect user_id is strictly prohibited
</guardrails>
"""

    return system_prompt


async def call_operator_agent(
    user_query: str, slack_data: dict, message_data: dict, retrieved_memory: str = ""
) -> None:
    """
    Execute the core agent to process user requests and send messages to Slack.

    Args:
        user_query: User query (original message text)
        slack_data: Slack API data (channel, members, message history)
        message_data: Current message info (user_id, text, channel_id, etc.)
        retrieved_memory: Retrieved relevant memory content
    """

    state_prompt = create_state_prompt(slack_data, message_data)

    # Add channel type info for response handling
    is_chat_message = slack_data.get("is_chat_message", False)
    if is_chat_message:
        # Add channel type specific instructions (using regular string to avoid backtick issues)
        channel_instructions = """

## Message Channel
This is a desktop chat message (not from Slack).

**Response Method:**
- Use mcp__answer__answer with channel_type="console"
- Only "text" parameter is required, no "channel_id" needed
- Example: {"channel_type": "console", "text": "Your response here"}

The response will be automatically delivered to the Electron app.
"""
        state_prompt += channel_instructions

    # Add memory to state_prompt if exists
    no_memory_messages = [
        "No relevant memories found.",
        "沒有相關記憶。",
        "No relevant memories found."
    ]
    if retrieved_memory and retrieved_memory not in no_memory_messages:
        state_prompt += f"\n\n## Related Memory\n<retrieved_memory>\n{retrieved_memory}\n</retrieved_memory>"

    system_prompt = create_system_prompt(state_prompt)

    settings = get_settings()

    # Load only MCP servers enabled by configuration
    mcp_servers = build_mcp_servers_dict(settings)

    # stderr callback function - MCP server error logging
    def stderr_callback(stderr_line: str) -> None:
        logger.error(f"[MCP STDERR] {stderr_line}")

    # Handle Gitea tools (always allowed by default)
    if settings.GITEA_ENABLED:
        logger.info("[GITEA] All Gitea tools allowed by default")

    # Build disallowed_tools list
    disallowed_tools_list = [
        "Bash(curl:*)",
        "Read(./.env)",
        "Read(./credential.json)",
        "mcp__tableau__get-view-image",
    ]

    # Add Gitea disallowed patterns with wildcard expansion
    if settings.GITEA_ENABLED and settings.GITEA_DISALLOWED_TOOLS:
        disallowed_patterns = [p.strip() for p in settings.GITEA_DISALLOWED_TOOLS.split(",")]

        # Expand wildcard patterns to actual tool names
        # Known Gitea tools based on MCP server definition
        gitea_tools = [
            # User
            "mcp__gitea__get_my_user_info",
            "mcp__gitea__get_user_orgs",

            # Repository
            "mcp__gitea__create_repo",
            "mcp__gitea__fork_repo",
            "mcp__gitea__list_my_repos",
            "mcp__gitea__list_repo_commits",
            "mcp__gitea__search_repos",
            "mcp__gitea__search_users",
            "mcp__gitea__search_org_teams",

            # Branch
            "mcp__gitea__create_branch",
            "mcp__gitea__delete_branch",
            "mcp__gitea__list_branches",

            # Release
            "mcp__gitea__create_release",
            "mcp__gitea__delete_release",
            "mcp__gitea__get_release",
            "mcp__gitea__get_latest_release",
            "mcp__gitea__list_releases",

            # Tag
            "mcp__gitea__create_tag",
            "mcp__gitea__delete_tag",
            "mcp__gitea__get_tag",
            "mcp__gitea__list_tags",

            # File
            "mcp__gitea__create_file",
            "mcp__gitea__update_file",
            "mcp__gitea__delete_file",
            "mcp__gitea__get_file_content",
            "mcp__gitea__get_dir_content",

            # Issue
            "mcp__gitea__create_issue",
            "mcp__gitea__edit_issue",
            "mcp__gitea__get_issue_by_index",
            "mcp__gitea__list_repo_issues",
            "mcp__gitea__create_issue_comment",
            "mcp__gitea__edit_issue_comment",
            "mcp__gitea__get_issue_comments_by_index",

            # Pull Request
            "mcp__gitea__create_pull_request",
            "mcp__gitea__get_pull_request_by_index",
            "mcp__gitea__list_repo_pull_requests",

            # Misc
            "mcp__gitea__get_gitea_mcp_server_version"
        ]

        expanded_tools = set()

        for pattern in disallowed_patterns:
            if "*" in pattern:
                # Convert wildcard to regex pattern with proper escaping
                regex = "^" + re.escape(pattern).replace("\\*", ".*") + "$"
                for tool in gitea_tools:
                    if re.fullmatch(regex, tool):
                        expanded_tools.add(tool)
            else:
                expanded_tools.add(pattern)

        disallowed_tools_list.extend(expanded_tools)
        logger.info(f"[GITEA_DISALLOWED] Applied {len(disallowed_patterns)} patterns → {len(expanded_tools)} exact tools disallowed")
        if expanded_tools:
            logger.debug(f"[GITEA_DISALLOWED] Disallowed tools: {sorted(expanded_tools)}")

    options = ClaudeAgentOptions(
        mcp_servers=mcp_servers,
        system_prompt=system_prompt,
        model=settings.MODEL_FOR_COMPLEX,
        permission_mode="bypassPermissions",
        allowed_tools=["*"],
        disallowed_tools=disallowed_tools_list,
        setting_sources=["project"],
        cwd=os.getcwd(),
        max_buffer_size=10 * 1024 * 1024,
        stderr=stderr_callback,
    )

    # Set session id
    session_id = None
    final_message = ""
    from devtools import pprint

    # For chat messages, skip the it-role-expert instruction to avoid overthinking
    is_chat_message = slack_data.get("is_chat_message", False)

    if is_chat_message:
        # Simple query - no role selection needed
        enhanced_query = f"""{user_query}

Relative time expressions like 'yesterday', 'tomorrow', 'next week', 'last year', 'this year' must be converted to exact dates based on the confirmed current time for searching/filtering."""
    else:
        # Complex request - use it-role-expert skill
        enhanced_query = f"""{user_query}

Before processing the request, use the `it-role-expert` skill to select the most suitable IT role for this request, and proceed with the work based on that role's expertise.

Relative time expressions like 'yesterday', 'tomorrow', 'next week', 'last year', 'this year' must be converted to exact dates based on the confirmed current time for searching/filtering."""

    # On context overflow, retry after /compact (keep same client, max 2 times)
    max_retries = 2

    async with ClaudeSDKClient(options=options) as client:
        for attempt in range(max_retries + 1):
            try:
                # First attempt is new session, retry continues with compact session
                if session_id:
                    await client.query(enhanced_query, session_id)
                else:
                    await client.query(enhanced_query)

                async for message in client.receive_response():
                    if hasattr(message, "subtype") and message.subtype == "init":
                        session_id = message.data.get("session_id")
                        logging.info(f"[OPERATOR_AGENT] Session ID: {session_id}")

                    # Remove pprint to avoid outputting Claude SDK internal messages
                    # pprint(message)

                    if type(message) is ResultMessage:
                        if "API Error" in message.result and "413" in message.result:
                            raise Exception(
                                f"Context overflow in ResultMessage: {message.result}"
                            )

                        final_message = message.result
                        # Debug: log full response to see if [/CHAT] exists
                        if "[/CHAT]" in message.result:
                            logging.info(f"[OPERATOR_AGENT] Found [/CHAT] marker in response")
                            idx = message.result.index("[/CHAT]")
                            logging.info(f"[OPERATOR_AGENT] Before [/CHAT]: {message.result[idx-100:idx]}")
                            logging.info(f"[OPERATOR_AGENT] After [/CHAT]: {message.result[idx+10:idx+110]}")
                        logging.info(
                            f"[OPERATOR_AGENT] Final message received (len={len(message.result)}): {final_message[:100]}..."
                        )

                # Handle case when final message is not set
                if not final_message:
                    final_message = "Unable to generate a response."
                    logging.warning(
                        f"[OPERATOR_AGENT] No final message received, using default"
                    )

                # Exit loop on success
                break

            except Exception as e:
                error_str = str(e)
                error_msg = error_str.lower()

                is_context_error = any(
                    [
                        "prompt is too long" in error_msg,
                        "context overflow" in error_msg,
                        "413" in error_msg,
                    ]
                )

                if is_context_error and attempt < max_retries:
                    logging.warning(
                        f"[OPERATOR_AGENT] Context overflow detected (attempt {attempt + 1}/{max_retries}), executing /compact..."
                    )

                    # Execute /compact with same client (pass session_id)
                    await client.query("/compact", session_id)
                    async for msg in client.receive_response():
                        if isinstance(msg, ResultMessage):
                            logging.info(f"[OPERATOR_AGENT] /compact executed successfully")
                            break

                    # Same client, retry with original query
                    continue
                else:
                    # Retry count exceeded or other error
                    logging.error(f"[OPERATOR_AGENT] Error occurred: {e}")
                    if is_context_error:
                        final_message = "The context is too large to process. Please start a new conversation."
                    elif "maximum buffer size" in error_msg:
                        final_message = "The response data is too large to process. Please request a smaller scope."
                    elif not final_message:
                        final_message = "An error occurred while processing the task."

                    # Only send error message to Slack in debug mode
                    if settings.DEBUG_SLACK_MESSAGES_ENABLED:
                        try:
                            slack_client = get_slack_client()
                            channel_id = message_data.get("channel_id")
                            thread_ts = message_data.get("thread_ts") or message_data.get("ts")

                            if channel_id:
                                await slack_client.chat_postMessage(
                                    channel=channel_id,
                                    text=f"⚠️ {final_message}",
                                    thread_ts=thread_ts
                                )
                                logging.info(f"[OPERATOR_AGENT] Error message sent to Slack: {final_message}")
                        except Exception as slack_error:
                            logging.error(f"[OPERATOR_AGENT] Failed to send error to Slack: {slack_error}")

                    break

    # Send message to Slack (moved to agent level)

    # Save to memory
    await save_to_memory(user_query, final_message, slack_data, message_data)

    return final_message
