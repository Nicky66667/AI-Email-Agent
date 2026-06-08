from apscheduler.schedulers.blocking import BlockingScheduler
from config.settings import POLL_INTERVAL_SECONDS
from langchain_core.messages import HumanMessage
from agents import agents_graph
from agents.nodes import is_processed
from services.gmail_client import GmailClient

gmail = GmailClient()


def process_one_email(email:dict) -> dict:
    """process single email and return final state"""

    config = {"configurable":{"thread_id":email['id']}}

    result = agents_graph.invoke(
        {
            "messages": [HumanMessage(content=f"Process email: {email['subject']}")],
            "current_email":{
                "id": email['id'],
                "sender": email['sender'],
                "subject": email['subject'],
                "body_preview": email['body_preview'],
                "category": "",
                "confidence": 0.0,
                "summary": "",
                "reason": "",
                "action_taken": "",
                "whatsapp_message_sid": "",
            },
            "processed_emails": [],
            "session_stats": {"deleted": 0, "archived": 0, "notified": 0},
        },
        config = config
    )
    return result

def run_batch(max_emails:int=5):
    "batch processing recent unread emails"
    print(f"\n{'=' * 60}")
    print(f"Fetching up to {max_emails} unread emails...")

    emails = gmail.fetch_unread(max_results=max_emails)

    if not emails:
        print("No unread emails found.")
        return

    print(f"Found {len(emails)} unread emails.\n")

    processed = 0
    skipped = 0

    for email in emails:
        if is_processed(email['id']):
            print(f"  [SKIP] Already processed: {email['subject'][:40]}")
            skipped += 1
            continue

        print(f"\n  [PROCESS] {email['sender'][:30]} | {email['subject'][:40]}")
        result = process_one_email(email)

        final_email = result.get('current_email', {})
        print(f"  → {final_email.get('category', '?')} "
              f"({final_email.get('confidence', 0):.2f}) "
              f"→ {final_email.get('action_taken', '?')}")
        processed += 1

    print(f"\n{'=' * 60}")
    print(f"Done. Processed: {processed}, Skipped (already done): {skipped}")

def scheduled_run():
    """Scheduled task: fetch and process unread emails every N seconds."""
    print(f"\n[Scheduler] Running at interval...")
    run_batch(max_emails=20)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--watch":

        print(f"Starting email watcher (interval: {POLL_INTERVAL_SECONDS}s)")
        print("Press Ctrl+C to stop.\n")

        scheduler = BlockingScheduler()
        scheduler.add_job(
            scheduled_run,
            'interval',
            seconds=POLL_INTERVAL_SECONDS,
            id='email_poll'
        )

        # Run once at startup, don't need to wait for the first interval
        scheduled_run()
        scheduler.start()
    else:
        # single processing mode
        run_batch(max_emails=5)