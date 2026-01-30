import logging
import time
from datetime import datetime
import pytz

def setup_logger():
    # Set timezone for logging
    tz = pytz.timezone('Asia/Ho_Chi_Minh')
    
    def custom_time(*args):
        utc_dt = datetime.fromtimestamp(time.time(), pytz.utc)
        return utc_dt.astimezone(tz).timetuple()

    logging.Formatter.converter = custom_time
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("bot.log"),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("BinanceBot")

def parse_timeframe_to_seconds(tf_str):
    try:
        val = int(''.join(c for c in tf_str if c.isdigit()))
        unit = ''.join(c for c in tf_str if c.isalpha()).lower()
        if unit == 'm': return val * 60
        elif unit == 'h': return val * 3600
        elif unit == 'd': return val * 86400
        else: return val * 60  # Default to minutes if weird unit
    except:
        return 60 # Default to 1m if parse fails
