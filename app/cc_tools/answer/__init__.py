"""
Unified Answer Tool for KIRA

Agent calls mcp__answer__answer to send responses.
Based on channel_type parameter, it determines the output method:
- channel_type="slack" → Send to Slack
- channel_type="console" → Output to stdout (for Electron)
"""

import json
import logging
from typing import Any, Dict, Literal, Optional

from claude_agent_sdk import create_sdk_mcp_server, tool
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

from app.config.settings import get_settings

logger = logging.getLogger(__name__)

# Prefix for console output (used by Electron to identify responses from answer tool)
ANSWER_TOOL_PREFIX = "__ANSWER_TOOL__:"


def get_slack_client() -> AsyncWebClient:
    """Return Slack AsyncWebClient instance"""
    settings = get_settings()
    token = settings.SLACK_BOT_TOKEN
    if not token:
        raise ValueError("SLACK_BOT_TOKEN is not set in settings")
    return AsyncWebClient(token=token)


def _clean_response_for_console(response: str) -> str:
    """Clean response for console output - remove thinking markers"""
    cleaned = response.strip()

    # Remove [/CHAT] marker and everything before it
    if "[/CHAT]" in cleaned:
        parts = cleaned.split("[/CHAT]", 1)
        cleaned = parts[-1].strip()

    # Remove Claude thinking markers (various formats)
    if "[/think]" in cleaned:
        cleaned = cleaned.split("[/think]", 1)[-1].strip()

    if "<thinking>" in cleaned:
        cleaned = cleaned.split("</thinking>")[-1].strip()

    return cleaned


@tool(
    "answer",
    "Sends a text response to the user. channel_type='slack' → Slack message, 'console' → desktop chat.",
    {
        "type": "object",
        "properties": {
            "channel_type": {
                "type": "string",
                "enum": ["slack", "console"],
                "description": "'slack' for Slack messages, 'console' for desktop chat"
            },
            "channel_id": {
                "type": "string",
                "description": "Required when channel_type='slack'. Slack channel ID (e.g., C1234567890)"
            },
            "text": {
                "type": "string",
                "description": "Response text to send"
            },
            "message_ts": {
                "type": "string",
                "description": "Slack message timestamp (for thread replies). Used when channel_type='slack'"
            },
            "thread_ts": {
                "type": "string",
                "description": "Thread timestamp. If not provided, uses message_ts. Used when channel_type='slack'"
            }
        },
        "required": ["channel_type", "text"]
    }
)
async def answer(args: Dict[str, Any]) -> Dict[str, Any]:
    """Send a response to user via the appropriate channel"""
    logger.info(f"[ANSWER_TOOL] Called with args: {args}")

    channel_type: Literal["slack", "console"] = args.get("channel_type", "console")
    text = args.get("text", "")

    # Console output for Electron
    if channel_type == "console":
        cleaned_text = _clean_response_for_console(text)
        logger.info(f"[ANSWER_TOOL] Sending to console: {cleaned_text[:100]}...")

        # Use start and end markers for reliable multi-line detection
        import sys
        sys.stdout.write(f"{ANSWER_TOOL_PREFIX}{cleaned_text}{ANSWER_TOOL_PREFIX}\n")
        sys.stdout.flush()
        logger.info(f"[ANSWER_TOOL] Response printed to stdout with start/end markers")

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": True,
                    "message": "Response sent to console",
                    "channel_type": "console"
                }, ensure_ascii=False, indent=2)
            }]
        }

    # Slack message
    channel_id = args.get("channel_id")
    message_ts = args.get("message_ts")
    thread_ts = args.get("thread_ts") or message_ts

    if not channel_id:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": True,
                    "message": "channel_id is required when channel_type='slack'"
                }, ensure_ascii=False, indent=2)
            }],
            "error": True
        }

    try:
        client = get_slack_client()

        # Determine thread_ts based on context
        # For DM, only use thread_ts if explicitly provided
        # For channels, use message_ts as thread_ts
        channel_info = args.get("channel_type_value", "")
        final_thread_ts = None

        if channel_info in ["public_channel", "private_channel", "group_dm"]:
            final_thread_ts = thread_ts
        elif channel_info in ["dm"]:
            final_thread_ts = thread_ts if thread_ts else None
        else:
            final_thread_ts = thread_ts

        # Prepare message parameters
        post_params: Dict[str, Any] = {
            "channel": channel_id,
            "text": text
        }

        if final_thread_ts:
            post_params["thread_ts"] = final_thread_ts

        response = await client.chat_postMessage(**post_params)

        if response and response.get("ok"):
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "success": True,
                        "message": "Response sent to Slack",
                        "channel": channel_id,
                        "ts": response.get("ts"),
                        "thread_ts": final_thread_ts,
                        "channel_type": "slack"
                    }, ensure_ascii=False, indent=2)
                }]
            }
        else:
            error_msg = response.get("error", "Unknown error") if response else "Unknown error"
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "success": False,
                        "error": True,
                        "message": f"Failed to send Slack message: {error_msg}"
                    }, ensure_ascii=False, indent=2)
                }],
                "error": True
            }

    except SlackApiError as e:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": True,
                    "message": f"Slack API error: {e.response.get('error', 'Unknown error')}"
                }, ensure_ascii=False, indent=2)
            }],
            "error": True
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": True,
                    "message": f"Error: {str(e)}"
                }, ensure_ascii=False, indent=2)
            }],
            "error": True
        }


# Tool list for MCP server
answer_tools = [
    answer,
]


def create_answer_mcp_server():
    """Answer MCP server for unified response handling"""
    return create_sdk_mcp_server(
        name="answer",
        version="1.0.0",
        tools=answer_tools
    )