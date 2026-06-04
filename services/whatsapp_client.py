from twilio.rest import Client
from config.settings import (
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_WHATSAPP_FROM,
    YOUR_WHATSAPP_NUMBER
)

class WhatsAppClient:

    def __init__(self):
        self.client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        self.from_number = TWILIO_WHATSAPP_FROM
        self.to_number = YOUR_WHATSAPP_NUMBER

    def send_email_alert(self, email_id:str, sender:str, subject:str, summary:str, category:str):
        """
        Sends email summary to WhatsApp.
        Returns Twilio message SID or None on failure.

        Message format:
        - First line states what this is
        - Key info (sender, subject) on separate lines for easy scanning
        - Last line
        """


        body = (
            f"*New {category} email*\n"
            f"─────────────────\n"
            f"*From:* {sender[:50]}\n"
            f"*Subject:* {subject[:60]}\n\n"
            f"{summary}\n\n"
            f"─────────────────\n"
            f"Reply: *ok* · *delete* · *reply [your text]*\n"
            f"ID: `{email_id[:12]}`"
        )

        try:
            message = self.client.messages.create(
                from_ = self.from_number,
                to = self.to_number,
                body = body
            )

            print(f"[WhatsAPP] sent alert for email {email_id[:8]}:{message.sid}")
            return message.sid

        except Exception as e:
            print(f"[WhatsAPP] Failed to send: {e}")

            return None


