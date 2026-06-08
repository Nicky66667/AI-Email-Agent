from agents.nodes import classify_email
from agents.state import AgentState
from langchain_core.messages import HumanMessage


# Test to see if spam classification is accurate
def test_classify_spam():

    state: AgentState = {
        "messages": [HumanMessage(content="test")],
        "current_email": {
            "id": "test001",
            "sender": "lottery@win-prize-now.xyz",
            "subject": "CONGRATULATIONS! You have won $1,000,000!!!",
            "body_preview": "Click here to claim your prize immediately. Send us your bank details.",
            "category": "", "confidence": 0.0, "summary": "", "reason": "",
            "action_taken": "", "whatsapp_message_sid": ""
        },
        "processed_emails": [],
        "session_stats": {}
    }

    result = classify_email(state)
    email = result['current_email']

    print(f"\n[Spam Test] category={email['category']} confidence={email['confidence']:.2f}")
    print(f"  reason: {email['reason']}")
    assert email['category'] == 'spam'
    assert email['confidence'] > 0.8

def test_classify_appointment():
    """Test appointment email classification."""

    state: AgentState = {
        "messages": [HumanMessage(content="test")],
        "current_email": {
            "id": "test002",
            "sender": "hr@techcompany.com",
            "subject": "Interview confirmed: Software Engineer role - Tuesday 10am",
            "body_preview": "We would like to confirm your interview on Tuesday 18th June at 10:00am. The interview will be held at our office at 123 Tech Street, London.",
            "category": "", "confidence": 0.0, "summary": "", "reason": "",
            "action_taken": "", "whatsapp_message_sid": ""
        },
        "processed_emails": [],
        "session_stats": {}
    }

    result = classify_email(state)
    email = result['current_email']

    print(f"\n[Appointment Test] category={email['category']} confidence={email['confidence']:.2f}")
    assert email['category'] == 'appointment'
    assert email['confidence'] > 0.8


def test_low_confidence_defaults_to_important():
    """
    Test edge cases: ambiguous emails should default to important, not promo or spam.
    This test validates the safe fallback logic.
    """

    state: AgentState = {
        "messages": [HumanMessage(content="test")],
        "current_email": {
            "id": "test003",
            "sender": "noreply@bank.co.uk",
            "subject": "Your account summary",
            "body_preview": "Here is your monthly account summary. Total balance: £2,340.00",
            "category": "", "confidence": 0.0, "summary": "", "reason": "",
            "action_taken": "", "whatsapp_message_sid": ""
        },
        "processed_emails": [],
        "session_stats": {}
    }

    result = classify_email(state)
    email = result['current_email']

    # bank account summary should be considered important
    print(f"\n[Bank Email Test] category={email['category']} confidence={email['confidence']:.2f}")
    assert email['category'] in ('important', 'appointment')