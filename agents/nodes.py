import json
import sqlite3
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from .state import AgentState, EmailRecord
from config.prompts import CLASSIFY_PROMPT
from config.settings import LLM_MODEL, CONFIDENCE_THRESHOLD
from services.gmail_client import GmailClient
from services.whatsapp_client import WhatsAppClient

llm = ChatOpenAI(model=LLM_MODEL, temperature=0)
gmail = GmailClient()
whatsapp = WhatsAppClient()

DB_PATH = "email_agent.db"

def init_db():
    """
    Initialize the SQLite database to store processed email IDs to prevent duplication.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS processed_emails(
            email_id TEXT PRIMARY KEY,
            category TEXT,
            action TEXT,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def is_processed(email_id:str) -> bool:
    """check if the email has been processed"""

    conn = sqlite3.connect(DB_PATH)
    result = conn.execute(
        "SELECT 1 FROM processed_emails WHERE email_id = ?", (email_id,)
    ).fetchone()

    conn.close()
    return result is not None

def mark_processed(email_id:str, category:str, action: str):
    """mark email as processed"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR IGNORE INTO processed_emails (email_id, category, action) VALUES (?, ?, ?)",
        (email_id, category, action)
    )
    conn.commit()
    conn.close()

def classify_email(state: AgentState) -> dict:
    """
    Node 1: LLM Classification

    Input: state['current_email'] (already has id / sender / subject / body_preview)
    Output: fills in category / confidence / summary / reason

    Design decisions:
    - Only passes body_preview (first 800 chars)
      Reason: classification doesn't need the full email, and to saves tokens, keeps cost ~$0.001/email
    - temperature=0 ensures stable and reproducible results
    - Structured output by JSON, with a fallback if parsing fails
    """

    email = state['current_email']

    prompt = f"""Email to classify:
            From: {email['sender']}
            Subject: {email['subject']}
            Body preview: {email['body_preview']}
    """

    response = llm.invoke([
        SystemMessage(content=CLASSIFY_PROMPT),
        HumanMessage(content=prompt)
    ])

    try:
        result = json.loads(response.content)
        category = result.get('category','important')
        confidence = float(result.get('confidence', 0.5))

        if confidence < CONFIDENCE_THRESHOLD and category in ('spam', 'promo'):
            print(f"[classify] Low confidence ({confidence:.2f}) for {category}, downgrading to important")
            category = 'important'

        updated_email = {
            **email,
            'category': category,
            'confidence': confidence,
            'summary': result.get('summary', ''),
            'reason': result.get('reason', ''),
        }

    except (json.JSONDecodeError, KeyError) as e:
        print(f"[classify] JSON parse failed: {e}, defaulting to important")
        updated_email = {
            **email,
            'category': 'important',
            'confidence': 0.5,
            'summary': f"Subject: {email['subject']}",
            'reason': 'Classification failed, defaulting to important for safety',
        }

    print(f"[classify] {email['id'][:8]}... → {updated_email['category']} ({updated_email['confidence']:.2f})")

    return {
        'current_email': updated_email,
        'messages': [HumanMessage(content=f"Classified as {updated_email['category']}")]
    }

def execute_action(state:AgentState) -> dict:
    """
        Node 2: Execute action based on classification result

        spam        → move to trash (recoverable)
        promo       → archive (remove from inbox)
        important   → send WhatsApp notification, wait for user instruction
        appointment → send WhatsApp notification (high priority), wait for user instruction
    """

    email = state['current_email']
    category = email['category']
    email_id = email['id']
    action_taken = 'skipped'

    if category == 'spam':
        # only auto-delete if confidence is high enough
        if email['confidence'] >= CONFIDENCE_THRESHOLD:
            success = gmail.trash_email(email_id)
            action_taken = 'deleted' if success else 'delete_failed'
        else:
            action_taken = 'skipped_low_confidence'

    elif category == 'promo':
        success = gmail.archieve_email(email_id, label='CATEGORY_PROMOTIONS')
        action_taken = 'archived' if success else 'archive_failed'

    elif category in ('important', 'appointment'):
        sid = whatsapp.send_email_alert(
            email_id=email_id,
            sender=email['sender'],
            subject=email['subject'],
            summary=email['summary'],
            category=category
        )
        action_taken = 'whatsapp_sent' if sid else 'whatsapp_failed'
        # mark as read after notification to prevent re-picking on next poll
        gmail.mark_read(email_id)

        # store message_sid in state so the webhook can match user replies later
        email = {**email, 'whatsapp_message_sid': sid or ''}

    # save to database to prevent duplicate processing
    mark_processed(email_id, category, action_taken)

    print(f"[action] {email_id[:8]}... → {action_taken}")

    # update session stats
    stats = state.get('session_stats', {'deleted': 0, 'archived': 0, 'notified': 0})
    if action_taken == 'deleted':
        stats['deleted'] += 1
    elif action_taken == 'archived':
        stats['archived'] += 1
    elif action_taken == 'whatsapp_sent':
        stats['notified'] += 1

    return {
        'current_email': {**email, 'action_taken': action_taken},
        'session_stats': stats
    }

def route_by_category(state: AgentState) -> str:
    """
    Conditional edge: determines which path to take based on classification.
    Return value maps to the keys in add_conditional_edges in graph.py.
    """
    category = state['current_email'].get('category', 'important')
    return category  # "spam" / "promo" / "important" / "appointment"
