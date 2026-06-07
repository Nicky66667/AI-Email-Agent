from typing import Annotated, List # add metadata to types
from typing_extensions import TypedDict # define dicts with fixed name
from langgraph.graph.message import add_messages

class EmailRecord(TypedDict):
    id:str
    sender:str
    subject: str
    body_preview: str
    category: str # spam, promo, important, appointment
    confidence: str
    summary: str
    reason: str
    action_taken: str # deleted, archived, whatsapp-sent, skipped
    whatsapp_message_sid = str

class AgentState(TypedDict):
    messages: Annotated[list, add_messages] # the email currently being processed
    current_email: EmailRecord # list of processed email IDs (to prevent duplicated)
    processed_emails :List[str] # stats for this session(deleted / archived / sent)

