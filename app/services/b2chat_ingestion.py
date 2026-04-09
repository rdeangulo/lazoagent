"""
Lazo Agent — B2Chat Knowledge Ingestion Pipeline

Pulls historical conversations from B2Chat and transforms them into
structured knowledge documents for the RAG system.

Pipeline:
1. Export chats from B2Chat API (paginated)
2. Filter out low-quality conversations (too short, spam, etc.)
3. Group conversations by detected topic
4. Use LLM to synthesize clean Q&A knowledge articles from raw chats
5. Store as KnowledgeDocuments → chunk → embed → pgvector

This runs as a batch job (script or API-triggered), not real-time.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from app.config import settings
from app.services.b2chat_service import b2chat_service, B2ChatService

logger = logging.getLogger(__name__)

# Minimum messages in a chat to be useful for knowledge extraction
MIN_MESSAGES_PER_CHAT = 4
# Minimum message length to count as meaningful
MIN_MESSAGE_LENGTH = 10
# Max chats to send to LLM in one synthesis batch
SYNTHESIS_BATCH_SIZE = 20
# Max concurrent LLM calls
MAX_CONCURRENT_LLM = 3


class B2ChatIngestionPipeline:
    """Transforms B2Chat conversation history into knowledge base documents."""

    async def run(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        messaging_provider: Optional[str] = None,
        max_chats: int = 5000,
        uploaded_by_id: Optional[UUID] = None,
    ) -> dict:
        """Run the full ingestion pipeline.

        Args:
            date_from: Start date (YYYY-MM-DD), defaults to 6 months ago
            date_to: End date (YYYY-MM-DD), defaults to today
            messaging_provider: Filter by channel
            max_chats: Maximum conversations to process
            uploaded_by_id: Operator ID for audit trail

        Returns:
            Summary dict with counts and status
        """
        if not date_from:
            from datetime import timedelta
            date_from = (datetime.now(timezone.utc) - timedelta(days=180)).strftime("%Y-%m-%d")
        if not date_to:
            date_to = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        logger.info(
            "Starting B2Chat ingestion: %s to %s (max %d chats)",
            date_from, date_to, max_chats,
        )

        # Step 1: Export chats from B2Chat
        raw_chats = await b2chat_service.export_all_chats(
            date_from=date_from,
            date_to=date_to,
            messaging_provider=messaging_provider,
            max_chats=max_chats,
        )
        logger.info("Exported %d chats from B2Chat", len(raw_chats))

        if not raw_chats:
            return {"status": "no_data", "chats_exported": 0, "documents_created": 0}

        # Step 2: Filter quality
        quality_chats = self._filter_quality(raw_chats)
        logger.info("After quality filter: %d chats (dropped %d)", len(quality_chats), len(raw_chats) - len(quality_chats))

        if not quality_chats:
            return {"status": "no_quality_data", "chats_exported": len(raw_chats), "documents_created": 0}

        # Step 3: Group by detected topic
        topic_groups = self._group_by_topic(quality_chats)
        logger.info("Grouped into %d topic clusters", len(topic_groups))

        # Step 4: Synthesize knowledge documents via LLM
        documents = await self._synthesize_knowledge(topic_groups, uploaded_by_id)
        logger.info("Created %d knowledge documents", len(documents))

        return {
            "status": "completed",
            "chats_exported": len(raw_chats),
            "chats_after_filter": len(quality_chats),
            "topic_groups": len(topic_groups),
            "documents_created": len(documents),
            "date_range": f"{date_from} to {date_to}",
        }

    # ── Step 2: Quality Filter ───────────────────────────────────────────

    def _filter_quality(self, chats: list[dict]) -> list[dict]:
        """Filter out low-quality conversations."""
        quality = []
        for chat in chats:
            messages = B2ChatService.extract_messages_from_chat(chat)

            # Need minimum number of messages
            if len(messages) < MIN_MESSAGES_PER_CHAT:
                continue

            # Need both customer and agent messages
            has_customer = any(m["role"] == "customer" for m in messages)
            has_agent = any(m["role"] == "agent" for m in messages)
            if not (has_customer and has_agent):
                continue

            # At least some meaningful content
            meaningful = [m for m in messages if len(m["content"]) >= MIN_MESSAGE_LENGTH]
            if len(meaningful) < 3:
                continue

            quality.append(chat)

        return quality

    # ── Step 3: Topic Grouping ───────────────────────────────────────────

    def _group_by_topic(self, chats: list[dict]) -> dict[str, list[dict]]:
        """Group conversations by detected topic using keyword matching.

        Topics are detected from customer messages using keyword patterns.
        This is a fast heuristic — the LLM refines topics during synthesis.
        """
        topic_keywords = {
            "pedidos_envios": [
                "pedido", "orden", "envío", "envio", "tracking", "rastreo",
                "paquete", "entrega", "llegó", "llego", "cuándo llega",
                "número de guía", "guia", "order", "shipping", "delivery",
                "seguimiento", "domicilio",
            ],
            "productos_disponibilidad": [
                "producto", "precio", "costo", "disponible", "stock",
                "talla", "tamaño", "color", "catálogo", "catalogo",
                "tienen", "venden", "cuánto cuesta", "cuanto cuesta",
                "product", "price", "available", "size",
            ],
            "devoluciones_cambios": [
                "devolución", "devolucion", "cambio", "reembolso", "garantía",
                "garantia", "defecto", "dañado", "roto", "equivocado",
                "return", "refund", "exchange", "warranty", "defective",
            ],
            "pagos_facturacion": [
                "pago", "factura", "cobro", "tarjeta", "transferencia",
                "recibo", "comprobante", "payment", "invoice", "charge",
                "billing", "receipt",
            ],
            "tiendas_horarios": [
                "tienda", "sucursal", "horario", "dirección", "direccion",
                "ubicación", "ubicacion", "abren", "cierran", "store",
                "location", "hours", "address",
            ],
            "promociones_descuentos": [
                "promoción", "promocion", "descuento", "oferta", "cupón",
                "cupon", "sale", "discount", "promo", "código", "codigo",
            ],
            "cuenta_registro": [
                "cuenta", "registro", "contraseña", "password", "login",
                "acceso", "perfil", "account", "register", "sign",
            ],
            "soporte_general": [],  # Catch-all
        }

        groups: dict[str, list[dict]] = defaultdict(list)

        for chat in chats:
            text = B2ChatService.format_chat_as_text(chat).lower()
            assigned = False

            for topic, keywords in topic_keywords.items():
                if not keywords:
                    continue
                matches = sum(1 for kw in keywords if kw in text)
                if matches >= 2:
                    groups[topic].append(chat)
                    assigned = True
                    break

            if not assigned:
                groups["soporte_general"].append(chat)

        return dict(groups)

    # ── Step 4: LLM Synthesis ────────────────────────────────────────────

    async def _synthesize_knowledge(
        self,
        topic_groups: dict[str, list[dict]],
        uploaded_by_id: Optional[UUID] = None,
    ) -> list[dict]:
        """Use LLM to synthesize knowledge documents from conversation groups."""
        from app.services.knowledge_service import knowledge_service

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM)
        documents = []

        async def process_topic(topic: str, chats: list[dict]):
            async with semaphore:
                # Process in batches
                for i in range(0, len(chats), SYNTHESIS_BATCH_SIZE):
                    batch = chats[i:i + SYNTHESIS_BATCH_SIZE]
                    doc = await self._synthesize_batch(topic, batch, uploaded_by_id)
                    if doc:
                        documents.append(doc)

        tasks = [
            process_topic(topic, chats)
            for topic, chats in topic_groups.items()
            if chats
        ]
        await asyncio.gather(*tasks)

        return documents

    async def _synthesize_batch(
        self,
        topic: str,
        chats: list[dict],
        uploaded_by_id: Optional[UUID] = None,
    ) -> Optional[dict]:
        """Synthesize a batch of conversations into one knowledge document."""
        # Format chats as text for the LLM
        chat_texts = []
        for chat in chats:
            text = B2ChatService.format_chat_as_text(chat)
            if text:
                chat_texts.append(text)

        if not chat_texts:
            return None

        combined = "\n\n---\n\n".join(chat_texts[:SYNTHESIS_BATCH_SIZE])

        # Use LLM to synthesize
        synthesized = await self._call_synthesis_llm(topic, combined)

        if not synthesized:
            return None

        # Store as knowledge document
        topic_display = topic.replace("_", " ").title()
        from app.services.knowledge_service import knowledge_service

        result = await knowledge_service.upload_document(
            title=f"B2Chat Knowledge: {topic_display} ({len(chats)} conversations)",
            content=synthesized,
            doc_type=self._topic_to_doc_type(topic),
            description=f"Auto-generated from {len(chats)} B2Chat conversations on topic: {topic_display}",
            uploaded_by_id=uploaded_by_id,
        )

        logger.info(
            "Created knowledge document for topic '%s' from %d chats",
            topic, len(chats),
        )

        return result

    async def _call_synthesis_llm(self, topic: str, conversations: str) -> Optional[str]:
        """Call LLM to synthesize conversations into structured knowledge."""
        if not settings.ANTHROPIC_API_KEY and not settings.OPENAI_API_KEY:
            logger.warning("No LLM API key configured — storing raw conversations")
            return conversations

        prompt = f"""You are analyzing real customer service conversations from Lazo (a retail and e-commerce brand).
These conversations are from the topic area: {topic.replace("_", " ")}.

Your task: Synthesize these conversations into a clean, structured knowledge base article that an AI customer service agent can use to answer similar questions in the future.

Rules:
1. Extract the key questions customers ask and the correct answers agents give
2. Write in clear Q&A format with headers
3. Include specific details (policies, procedures, timeframes, etc.)
4. Write in Spanish (this is the primary customer language)
5. Remove personal information (names, phone numbers, order numbers)
6. If agents gave inconsistent answers, note the most common/correct one
7. Include any relevant procedures or steps the agent follows

Format the output as a structured knowledge article with:
- A title summarizing the topic
- Key Q&A pairs
- Important policies or procedures mentioned
- Common customer concerns and how to address them

Here are the conversations:

{conversations}

---

Synthesized knowledge article:"""

        try:
            if settings.ANTHROPIC_API_KEY:
                import anthropic
                client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
                response = await client.messages.create(
                    model=settings.ANTHROPIC_MODEL,
                    max_tokens=4096,
                    messages=[{"role": "user", "content": prompt}],
                )
                return response.content[0].text

            elif settings.OPENAI_API_KEY:
                import openai
                client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                response = await client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    max_tokens=4096,
                    messages=[{"role": "user", "content": prompt}],
                )
                return response.choices[0].message.content

        except Exception as e:
            logger.error("LLM synthesis failed for topic '%s': %s", topic, e)
            # Fallback: store raw conversations
            return conversations

        return None

    @staticmethod
    def _topic_to_doc_type(topic: str) -> str:
        """Map topic name to KnowledgeDocument.doc_type."""
        mapping = {
            "pedidos_envios": "faq",
            "productos_disponibilidad": "product",
            "devoluciones_cambios": "policy",
            "pagos_facturacion": "policy",
            "tiendas_horarios": "guide",
            "promociones_descuentos": "product",
            "cuenta_registro": "guide",
            "soporte_general": "general",
        }
        return mapping.get(topic, "general")


# Singleton
ingestion_pipeline = B2ChatIngestionPipeline()
