import os
import base64 # encode email message

from email.mime.text import MIMEText # HTML email body
from email.mime.multipart import MIMEMultipart # Multi-part email container(text + attachments)

from google.auth.transport.requests import Request # HTTP request handler
from google.oauth2.credentials import Credentials # stores and manages OAuth2 tokens
from google_auth_oauthlib.flow import InstalledAppFlow # login flow for desktop apps
from googleapiclient.discovery import build # builds the Gmail API service client

from config.settings import GMAIL_CREDENTIALS_FILE, GMAIL_TOKEN_FILE # App-specific gmail auth file paths

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
]

def get_gmail_service():
    """
    Returns an authorized Gmail API Service instance.

    Ob first run, opens a browser for authorization; afterward auto-refreshes from tokrn.json
    token.json expires for over 7 days that needs re-auth
    """

    creds = None

    if os.path.exists(GMAIL_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(GMAIL_TOKEN_FILE, SCOPES)  # Load saved token if it exists

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token: # token expired but refreshable
            creds.refresh(Request())

        else:
            # first time auth: open browser to login
            flow = InstalledAppFlow.from_client_secrets_file(
                GMAIL_CREDENTIALS_FILE, SCOPES
            )

            creds = flow.run_local_server(port=0)

            with open(GMAIL_TOKEN_FILE,'w') as f:
                f.write(creds.to_json()) # save cred to skip auth next time

    return build('gmail','v1',credentials=creds) # return gmail API client

class GmailClient:
    def __init__(self):
        self.service = get_gmail_service() # get a gmail API client

    def fetch_unread(self,max_results:int=20) -> list[dict]:
        """
        Fetches a list of unread emails
        returns fields:id, subject, sender, snippet, body_preview
        """

        result = self.service.users().messages().list( # .user:scope to user's data, messages:scope to the messages resource
            userId = 'me',
            q = 'is:unread',
            maxResults = max_results
        ).execute() # send the request

        messages = result.get('messages',[]) # List of message(id + threadId)
        emails = []

        for msg in messages:
            detail = self.service.users().messages().get(
                userId = 'me',
                id = msg['id'],
                format = 'full' #'full' fetches entire message; 'metadata' fetches headers only
            ).execute()

            headers = {
                h['name']: h['value']
                for h in detail['payload']['headers'] # playload is email itself, convert header list to a lookup dict
            }

            body = self._extract_body(detail['payload']) # extract plain-text body from payload

            emails.append({
                'id': msg['id'],
                'subject': headers.get('Subject','(no subject)'),
                'sender':headers.get('From','unknown'),
                'date':headers.get('Date',''),
                'body_preview':body[:800] if body else detail.get('snippet',''), # cap at 800 chars to save LLM tokens
            })

        return emails

    def _extract_body(self, payload:dict) -> str:
        """Extracts plain-text body from a Gmail payload."""

        if payload.get('mimeType','').startswith('multipart'):
            for part in payload.get('parts',[]):
                if part['mimeType'] == 'text/plain':  # Prefer plain text over HTML
                    data = part.get('body', {}).get('data', '')
                    if data:
                        return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                if payload.get('parts'):
                    return self._extract_body(payload['parts'][0])  # No plain text found — recurse into first part

        # single-part email
        data = payload.get('body',{}).get('data','')

        if data:
            return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')

        return '' # no body content


    def trash_email(self, email_id:str) -> bool:
        """Moves email to trash (recoverable)."""

        try:
            self.service.users().messages().trash(
                userId = 'me', id=email_id
            ).execute()

            return True

        except Exception as e:
            print(f"[GmailClient] Failed to trash {email_id}:{e}")

            return False

    def archieve_email(self, email_id:str, label:str = 'CATEGORY_PROMOTIONS') -> bool:
        """
        removes it from inbox and applies a category label.
        label options: PROMOTIONS / UPDATES / FORUMS / SOCIAL
        """

        try:
            self.service.users().messages().modify(
                userId='me',
                id=email_id,
                body={
                    'removeLabelIds': ['INBOX', 'UNREAD'],  # Remove from inbox and mark as read
                    'addLabelIds': [label]  # Move to the specified category
                }
            ).execute()
            return True
        except Exception as e:
            print(f"[GmailClient] Failed to archive {email_id}: {e}")
            return False

    def mark_read(self, email_id: str) -> bool:
        """Marks an email as read by removing the UNREAD label."""
        try:
            self.service.users().messages().modify(
                userId='me',
                id=email_id,
                body={'removeLabelIds': ['UNREAD']}  # Gmail uses labels — removing UNREAD = marking read
            ).execute()
            return True
        except Exception as e:
            print(f"[GmailClient] Failed to mark read {email_id}: {e}")
            return False

    def send_reply(self, original_id: str, reply_text: str) -> bool:
        """
        Replies to an email.
        Fetches original headers to build a properly threaded reply.
        """
        try:
            original = self.service.users().messages().get(
                userId='me', id=original_id, format='metadata'  # Only need headers, not full body
            ).execute()

            headers = {}
            for h in original['payload']['headers']:
                headers[h['name']] = h['value']

            msg = MIMEText(reply_text)
            msg['To'] = headers.get('From', '')  # Reply to original sender
            msg['Subject'] = 'Re: ' + headers.get('Subject', '')  # Prefix subject with Re:
            msg['In-Reply-To'] = headers.get('Message-ID', '')  # Link to original message
            msg['References'] = headers.get('Message-ID', '')  # Keeps email clients threading correctly

            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()  # Gmail API requires base64-encoded raw message

            self.service.users().messages().send(
                userId='me',
                body={'raw': raw, 'threadId': original['threadId']}  # threadId keeps reply in same conversation
            ).execute()
            return True
        except Exception as e:
            print(f"[GmailClient] Failed to send reply: {e}")
            return False




