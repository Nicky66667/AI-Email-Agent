import sqlite3
from fastapi import FastAPI, Form, Response
from services.gmail_client import GmailClient

app = FastAPI()
gmail = GmailClient()
DB_PATH = "email_agent.db"

def get_pending_email_id(from_number: str):

    """
    Find the most recent email ID in the database that was sent to this user
    and has not yet been replied to.

    Simplified demo: finds the latest record with action=whatsapp_sent.
    In production, use message_sid.
    """

    conn = sqlite3.connect(DB_PATH)
    result = conn.execute("""
           SELECT email_id FROM processed_emails
           WHERE action = 'whatsapp_sent'
           ORDER BY processed_at DESC LIMIT 1
    """).fetchone()

    conn.close()

    return result[0] if result else None

@app.post("/whatsapp")
async def handle_whatsapp_reply(
        Body: str = Form(...),
        From: str = Form(...)
):
    """
    This Webhook is called by Twilio when a user replies via WhatsApp.

    Supported commands:
    - ok / thanks / noted → mark as read only, no action taken
    - delete → move the email to the trash
    - reply [text] → reply to that email with the content [text]

    Returns an empty TwiML response (tells Twilio not to response to the user)
    """
    body = Body.strip()
    body_lower = body.lower()

    print(f"[Webhook] Received from {From}: {body[:100]}")  # e.g., [Webhook] Received from whatsapp:+447911123456: reply please reschedule our meeting

    email_id = get_pending_email_id(From)

    if not email_id:
        print("[Webhook] No pending email found for this user")
        return Response(content="<Response/>", media_type="text/xml")


    if body_lower in ('ok', 'thanks', 'noted', 'got it', 'seen'):
        # no action  needed
        print(f"[Webhook] User acknowledged email {email_id[:8]}")

    elif body_lower == 'delete':
        success = gmail.trash_email(email_id)
        print(f"[Webhook] Deleted email {email_id[:8]}: {success}")
        _update_action(email_id, 'deleted_by_user')

    elif body_lower.startswith('reply '):
        reply_text = body[6:].strip()
        if reply_text:
            success = gmail.send_reply(email_id, reply_text)
            print(f"[Webhook] Replied to email {email_id[:8]}: {success}")
            _update_action(email_id, 'replied_by_user')

    else:
        print(f"[Webhook] Unknown command: {body_lower}")

    # Twilio need to return TwiML format
    return Response(content="<Response/>", media_type="text/xml")

def _update_action(email_id: str, new_action: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE processed_emails SET action = ? WHERE email_id = ?",
        (new_action, email_id)
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

