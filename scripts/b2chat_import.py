#!/usr/bin/env python3
"""
Lazo Agent — B2Chat Historical Import Script

Standalone script to pull conversations from B2Chat and build
the initial knowledge base. Run this once (or periodically) to
train the AI from real customer interactions.

Usage:
    # Import last 6 months (default)
    python scripts/b2chat_import.py

    # Import specific date range
    python scripts/b2chat_import.py --from 2025-01-01 --to 2025-12-31

    # Import only WhatsApp conversations
    python scripts/b2chat_import.py --channel whatsapp

    # Preview without importing
    python scripts/b2chat_import.py --preview --limit 5

    # Limit total chats processed
    python scripts/b2chat_import.py --max-chats 1000
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("b2chat_import")


async def preview(args):
    """Preview chats without importing."""
    from app.services.b2chat_service import b2chat_service, B2ChatService

    logger.info("Previewing B2Chat chats...")

    chats = await b2chat_service.export_chats(
        date_from=args.date_from,
        date_to=args.date_to,
        messaging_provider=args.channel,
        limit=args.limit,
    )

    logger.info("Got %d chats", len(chats))

    for i, chat in enumerate(chats, 1):
        messages = B2ChatService.extract_messages_from_chat(chat)
        text = B2ChatService.format_chat_as_text(chat)
        channel = chat.get("messaging_provider") or chat.get("channel") or "?"
        contact = chat.get("contact", {}).get("fullname") or "Unknown"

        print(f"\n{'='*60}")
        print(f"Chat {i} | Channel: {channel} | Contact: {contact} | Messages: {len(messages)}")
        print(f"{'='*60}")
        print(text[:800] if text else "(empty)")

    print(f"\n--- Total: {len(chats)} chats previewed ---")


async def run_import(args):
    """Run the full import pipeline."""
    from app.services.b2chat_ingestion import ingestion_pipeline

    logger.info("Starting B2Chat knowledge import...")
    logger.info("  Date range: %s to %s", args.date_from or "6 months ago", args.date_to or "today")
    logger.info("  Channel: %s", args.channel or "all")
    logger.info("  Max chats: %d", args.max_chats)

    result = await ingestion_pipeline.run(
        date_from=args.date_from,
        date_to=args.date_to,
        messaging_provider=args.channel,
        max_chats=args.max_chats,
    )

    print(f"\n{'='*60}")
    print("B2Chat Import Results")
    print(f"{'='*60}")
    for key, value in result.items():
        print(f"  {key}: {value}")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(
        description="Import B2Chat conversations into Lazo Agent knowledge base",
    )
    parser.add_argument("--from", dest="date_from", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--to", dest="date_to", help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--channel",
        choices=["whatsapp", "facebook", "telegram", "livechat", "b2cbotapi"],
        help="Filter by messaging provider",
    )
    parser.add_argument("--max-chats", type=int, default=5000, help="Max chats to process (default: 5000)")
    parser.add_argument("--preview", action="store_true", help="Preview chats without importing")
    parser.add_argument("--limit", type=int, default=10, help="Number of chats to preview (with --preview)")

    args = parser.parse_args()

    if args.preview:
        asyncio.run(preview(args))
    else:
        asyncio.run(run_import(args))


if __name__ == "__main__":
    main()
