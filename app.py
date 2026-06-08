import sqlite3
import streamlit as st
from services.gmail_client import GmailClient
from agents import agents_graph
from agents.nodes import is_processed, init_db
from main import process_one_email

# --- Page config ---
st.set_page_config(
    page_title = "AI Email Agent",
    layout = 'wide'
)

# --- Init DB and Gmail client ---
init_db()
gmail = GmailClient()

st.title("AI Email Management Agent")

# --- Sidebar: settings and session stats ---
with st.sidebar:
    st.header("⚙️ Settings")
    max_emails = st.slider("Emails per run", 1, 50, 10)
    dry_run = st.toggle("Dry run (no actual deletes)", value=True)

    if dry_run:
        st.warning("Dry run mode: categories will be shown but no emails will be deleted or archived.")

    st.divider()
    st.header("📊 Session Stats")

    # Fetch action counts from DB and display as metrics
    conn = sqlite3.connect("email_agent.db")
    stats = conn.execute(
        """SELECT action, COUNT(*) as cnt
            FROM processed_emails
            GROUP BY action"""
    ).fetchall()
    conn.close()

    for action, count in stats:
        st.metric(action, count)

# -------------- main console -------------------------------

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📥 Unread Emails")

    # --- Fetch button ---
    if st.button("🔄 Fetch & Process", type="primary"):
        with st.spinner("Fetching emails..."):
            emails = gmail.fetch_unread(max_results=max_emails)

        if not emails:
            st.info("No unread emails.")
        else:
            st.session_state['emails'] = emails
            st.success(f"Fetched {len(emails)} emails")

    # --- Batch process button (only show if emails are loaded) ---
    if 'emails' in st.session_state and not dry_run:
        unprocessed = [
            e for e in st.session_state['emails']
            if not is_processed(e['id'])
        ]

        if unprocessed:
            if st.button(f"⚡ Batch Process All ({len(unprocessed)} emails)", type="secondary"):
                progress = st.progress(0, text="Starting batch processing...")
                total = len(unprocessed)

                for i, email in enumerate(unprocessed):
                    progress.progress(
                        (i) / total,
                        text=f"Processing {i+1}/{total}: {email['subject'][:40]}"
                    )
                    result = process_one_email(email)
                    fe = result.get('current_email', {})
                    st.toast(f"✅ {email['subject'][:30]} → {fe.get('category')} · {fe.get('action_taken')}")

                progress.progress(1.0, text="✅ Batch processing complete!")
                st.rerun()  # refresh log after batch

    # --- Display each email as expandable card ---
    if 'emails' in st.session_state:
        for email in st.session_state['emails']:
            already = is_processed(email['id'])
            label = "✅" if already else "📬"

            with st.expander(f"{label} {email['subject'][:35]}..."):
                st.text(f"From: {email['sender'][:40]}")
                st.text(f"Preview: {email['body_preview'][:120]}...")

                # Only show process button if not yet processed and not in dry run
                if not already and not dry_run:
                    if st.button(f"Process", key=f"proc_{email['id']}"):
                        with st.spinner("Classifying..."):
                            result = process_one_email(email)
                        fe = result.get('current_email', {})
                        st.success(f"→ {fe.get('category')} · {fe.get('action_taken')}")
                        st.rerun()  # 👈 refresh log in real time after each process

with col2:
    st.subheader("📋 Processing Log")

    # Fetch last 50 processed emails from DB
    conn = sqlite3.connect("email_agent.db")
    log = conn.execute(
        """SELECT email_id, category, action, processed_at
           FROM processed_emails
           ORDER BY processed_at DESC
           LIMIT 50"""
    ).fetchall()
    conn.close()

    if log:
        # Color-coded icons per category
        category_color = {
            'spam': '🔴',
            'promo': '🟡',
            'important': '🟠',
            'appointment': '🟢',
        }

        for email_id, category, action, ts in log:
            icon = category_color.get(category, '⚪')
            st.text(f"{icon} [{email_id[:8]}] {category:<12} → {action:<20} {ts[:16]}")
    else:
        st.info("No emails processed yet. Click 'Fetch & Process' to start.")