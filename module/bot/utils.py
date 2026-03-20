import logging
import os
import time
from datetime import datetime
import json
import urllib.request
from typing import Any, Tuple, Optional
import pytz
from resource.config import settings

import sys


def setup_logger() -> logging.Logger:
    """
    Sets up the application logger with timezone-aware formatting.

    Returns:
        logging.Logger: The configured logger instance.
    """
    # Set timezone for logging
    tz = pytz.timezone("Asia/Ho_Chi_Minh")

    def custom_time(*args: Any) -> Tuple[Any, ...]:
        utc_dt = datetime.fromtimestamp(time.time(), pytz.utc)
        return utc_dt.astimezone(tz).timetuple()

    logging.Formatter.converter = custom_time

    # Ensure resource directory exists
    # Use absolute path handling relative to project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_dir = os.path.join(project_root, "resource")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "bot.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
            LarkNotificationHandler(),
        ],
    )
    return logging.getLogger("BinanceBot")


def send_lark_notification(message: str) -> bool:
    """
    Sends a message to a Lark webhook.
    """
    webhook_url = settings.LARK_WEBHOOK_URL
    if not webhook_url:
        return False

    try:
        data = json.dumps({"msg_type": "text", "content": {"text": message}}).encode(
            "utf-8"
        )

        req = urllib.request.Request(
            webhook_url, data=data, headers={"Content-Type": "application/json"}
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            return response.getcode() == 200
    except Exception:
        return False


class LarkNotificationHandler(logging.Handler):
    """
    Custom logging handler that sends ERROR and CRITICAL logs to Lark.
    """

    def __init__(self, level=logging.ERROR):
        super().__init__(level)

    def emit(self, record):
        try:
            msg = self.format(record)
            # Add some context/formatting for Lark
            lark_msg = f"🔴 [BinanceBot ERROR]\n{msg}"
            if record.levelno >= logging.CRITICAL:
                lark_msg = f"🚨 [BinanceBot CRITICAL]\n{msg}"

            send_lark_notification(lark_msg)
        except Exception:
            self.handleError(record)


def parse_timeframe_to_seconds(tf_str: str) -> int:
    """
    Converts a timeframe string (e.g., '15m', '4h') to seconds.

    Args:
        tf_str (str): Timeframe string.

    Returns:
        int: Number of seconds. Defaults to 60 (1m) if parsing fails.
    """
    try:
        val = int("".join(c for c in tf_str if c.isdigit()))
        unit = "".join(c for c in tf_str if c.isalpha()).lower()
        if unit == "m":
            return val * 60
        elif unit == "h":
            return val * 3600
        elif unit == "d":
            return val * 86400
        elif unit == "w":
            return val * 604800
        else:
            return val * 60  # Default to minutes if weird unit
    except Exception:
        return 60  # Default to 1m if parse fails


def get_public_ip() -> str:
    """
    Fetches the public IP address of the current machine using external services.

    Returns:
        str: The public IP address or an error message.
    """
    services = [
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://ident.me",
        "https://api.myip.com",  # Returns JSON, handle differently if used
    ]

    for service in services:
        try:
            with urllib.request.urlopen(service, timeout=5) as response:
                return response.read().decode("utf-8").strip()
        except Exception:
            continue

    return "Unknown (Failed to fetch public IP)"
