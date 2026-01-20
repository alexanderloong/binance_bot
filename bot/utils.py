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
