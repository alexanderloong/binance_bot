import logging
import os
import time
from datetime import datetime
from typing import Any, Tuple
import pytz

def setup_logger() -> logging.Logger:
    """
    Sets up the application logger with timezone-aware formatting.
    
    Returns:
        logging.Logger: The configured logger instance.
    """
    # Set timezone for logging
    tz = pytz.timezone('Asia/Ho_Chi_Minh')
    
    def custom_time(*args: Any) -> Tuple[Any, ...]:
        utc_dt = datetime.fromtimestamp(time.time(), pytz.utc)
        return utc_dt.astimezone(tz).timetuple()

    logging.Formatter.converter = custom_time
    
    # Ensure resource directory exists
    # Use absolute path handling relative to project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_dir = os.path.join(project_root, 'resource')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "bot.log")

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("BinanceBot")

def parse_timeframe_to_seconds(tf_str: str) -> int:
    """
    Converts a timeframe string (e.g., '15m', '4h') to seconds.
    
    Args:
        tf_str (str): Timeframe string.
        
    Returns:
        int: Number of seconds. Defaults to 60 (1m) if parsing fails.
    """
    try:
        val = int(''.join(c for c in tf_str if c.isdigit()))
        unit = ''.join(c for c in tf_str if c.isalpha()).lower()
        if unit == 'm': return val * 60
        elif unit == 'h': return val * 3600
        elif unit == 'd': return val * 86400
        elif unit == 'w': return val * 604800
        else: return val * 60  # Default to minutes if weird unit
    except Exception:
        return 60 # Default to 1m if parse fails
