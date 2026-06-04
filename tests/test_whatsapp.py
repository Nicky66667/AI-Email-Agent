from services.whatsapp_client import WhatsAppClient

def test_send_whatapp():
    client = WhatsAppClient()

    sid = client.send_email_alert(
        email_id="test-sending-email",
        sender = "test@example.com",
        subject="Meeting tomorrow at 10 AM",
        summary= "John wants to confirm the project review meeting tomorrow at 10am in Room 1",
        category="appointment"
    )

    print(f"\n[WhatsApp Test] Message SID:{sid}")
    assert sid is not None, "Failed to send WhatsApp message"
