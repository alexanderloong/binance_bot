import json
import logging
import urllib.request
from typing import Optional

class Notifier:
    def __init__(self, webhook_url: Optional[str], logger: logging.Logger):
        self.webhook_url = webhook_url
        self.logger = logger
        if not self.webhook_url:
            self.logger.warning("Lark webhook URL not configured. Notifications are disabled.")

    def send_lark_message(self, message: str) -> bool:
        """Sends a text message to a Lark/Feishu webhook."""
        if not self.webhook_url:
            return False

        try:
            payload = {
                "msg_type": "text",
                "content": {
                    "text": message
                }
            }
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                self.webhook_url,
                data=data,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    return True
                else:
                    self.logger.error(f"Failed to send Lark message: Status {response.status}")
                    return False
        except Exception as e:
            self.logger.error(f"Exception sending Lark message: {e}")
            return False
