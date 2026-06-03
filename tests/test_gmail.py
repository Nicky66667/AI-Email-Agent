def test_gmail_connection():
    """
    test connecting gmail API client
    """
    from services.gmail_client import GmailClient

    client = GmailClient()
    emails = client.fetch_unread(max_results=3)

    print(f"\n[Gmail Test] Fetched {len(emails)} unread emails")
    for e in emails:
        print(f"  - [{e['id'][:8]}...] {e['sender'][:30]} | {e['subject'][:40]}")

    assert isinstance(emails, list)