"""
Lazo Agent — Database Models

All SQLAlchemy models re-exported from this package for convenience.
Import from here: `from app.models import Customer, Thread, Message, ...`
"""

from app.models.base import Base
from app.models.channel import Channel, operator_channels
from app.models.customer import Customer
from app.models.escalation import Escalation, EscalationNote
from app.models.inbox import InboxItem
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.models.message import Message
from app.models.operator import Operator, OperatorLog
from app.models.shopify import ShopifyOrder, ShopifyWebhookLog
from app.models.thread import Thread

__all__ = [
    "Base",
    "Channel",
    "Customer",
    "Escalation",
    "EscalationNote",
    "InboxItem",
    "KnowledgeChunk",
    "KnowledgeDocument",
    "Message",
    "Operator",
    "OperatorLog",
    "ShopifyOrder",
    "ShopifyWebhookLog",
    "Thread",
    "operator_channels",
]
