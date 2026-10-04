"""B.O.S. SQL Conversation Memory Provider v1.0

`conversation_memory` provider. Uses its own database (SQLite by default,
PostgreSQL via MEMORY_DATABASE_URL) so memory never mixes with business records.

Actions:
    append              {conversation_id, role, content, channel?, actor?, title?, meta?}
    history             {conversation_id, limit?}
    list_conversations  {limit?, channel?}
    get_conversation    {conversation_id}
"""

import time
from typing import Any, Dict, Optional

from sqlalchemy import JSON, Float, Integer, String, Text, create_engine, func, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from ..base.base_provider import BaseProvider
from ..base.provider_context import ProviderContext
from ..base.provider_metadata import ProviderMetadata

CONVERSATION_MEMORY = "conversation_memory"


class _MemoryBase(DeclarativeBase):
    pass


class _Conversation(_MemoryBase):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    channel: Mapped[str] = mapped_column(String(40), default="")
    actor: Mapped[str] = mapped_column(String(40), default="")
    title: Mapped[str] = mapped_column(String(200), default="")
    contact_ref: Mapped[str] = mapped_column(String(200), default="")
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    last_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    updated_at: Mapped[float] = mapped_column(Float, default=time.time, index=True)


class _Message(_MemoryBase):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(String(160), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    meta: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)


class SqlMemoryProvider(BaseProvider):
    """Persistent conversation memory."""

    def __init__(self, database_url: str, priority: int = 10, schema: str = ""):
        super().__init__(
            ProviderMetadata(
                name="sql_memory",
                capability=CONVERSATION_MEMORY,
                priority=priority,
                description="Conversation memory stored in a dedicated SQL database.",
            )
        )
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self._schema = schema if not database_url.startswith("sqlite") else ""
        engine = create_engine(database_url, connect_args=connect_args, pool_pre_ping=True)
        if self._schema:
            # Keeps memory in its own schema when it shares a Postgres server with business data.
            engine = engine.execution_options(schema_translate_map={None: self._schema})
        self._engine = engine
        self._sessions = sessionmaker(bind=self._engine, expire_on_commit=False)

    def _on_initialize(self, context: ProviderContext) -> None:
        if self._schema:
            with self._engine.begin() as conn:
                conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{self._schema}"'))
        _MemoryBase.metadata.create_all(self._engine)

    def _on_shutdown(self) -> None:
        self._engine.dispose()

    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        handler = {
            "append": self._append,
            "history": self._history,
            "list_conversations": self._list,
            "get_conversation": self._get,
        }.get(action)
        if handler is None:
            return {"success": False, "error": f"Unsupported memory action '{action}'."}
        return handler(params)

    def _append(self, p: Dict[str, Any]) -> Dict[str, Any]:
        cid = str(p.get("conversation_id") or "")
        content = str(p.get("content") or "")
        if not cid or not content:
            return {"success": False, "error": "conversation_id and content are required."}
        now = time.time()
        with self._sessions.begin() as db:
            conv = db.get(_Conversation, cid)
            if conv is None:
                conv = _Conversation(
                    id=cid,
                    channel=str(p.get("channel") or ""),
                    actor=str(p.get("actor") or ""),
                    title=str(p.get("title") or "")[:200],
                    contact_ref=str(p.get("contact_ref") or ""),
                    created_at=now,
                )
                db.add(conv)
            elif p.get("title") and not conv.title:
                conv.title = str(p["title"])[:200]
            if p.get("contact_ref"):
                conv.contact_ref = str(p["contact_ref"])
            conv.message_count = (conv.message_count or 0) + 1
            conv.last_message = content[:500]
            conv.updated_at = now
            db.add(_Message(conversation_id=cid, role=str(p.get("role") or "user"), content=content, meta=p.get("meta") or {}, created_at=now))
        return {"success": True, "conversation_id": cid}

    def _history(self, p: Dict[str, Any]) -> Dict[str, Any]:
        cid = str(p.get("conversation_id") or "")
        limit = int(p.get("limit") or 30)
        with self._sessions() as db:
            rows = db.scalars(
                select(_Message).where(_Message.conversation_id == cid).order_by(_Message.id.desc()).limit(limit)
            ).all()
        messages = [
            {"role": m.role, "content": m.content, "meta": m.meta or {}, "created_at": m.created_at} for m in reversed(rows)
        ]
        return {"success": True, "conversation_id": cid, "messages": messages}

    def _list(self, p: Dict[str, Any]) -> Dict[str, Any]:
        limit = int(p.get("limit") or 50)
        with self._sessions() as db:
            filters = []
            if p.get("channel"):
                filters.append(_Conversation.channel == p["channel"])
            if p.get("actor"):
                filters.append(_Conversation.actor.in_(p["actor"]) if isinstance(p["actor"], list) else _Conversation.actor == p["actor"])
            rows = db.scalars(select(_Conversation).where(*filters).order_by(_Conversation.updated_at.desc()).limit(limit)).all()
            total = db.scalar(select(func.count()).select_from(_Conversation).where(*filters)) or 0
        return {"success": True, "total": total, "conversations": [self._conv_dict(c) for c in rows]}

    def _get(self, p: Dict[str, Any]) -> Dict[str, Any]:
        with self._sessions() as db:
            conv: Optional[_Conversation] = db.get(_Conversation, str(p.get("conversation_id") or ""))
        if conv is None:
            return {"success": False, "error": "Conversation not found."}
        return {"success": True, "conversation": self._conv_dict(conv)}

    @staticmethod
    def _conv_dict(c: _Conversation) -> Dict[str, Any]:
        return {
            "id": c.id,
            "channel": c.channel,
            "actor": c.actor,
            "title": c.title,
            "contact_ref": c.contact_ref,
            "message_count": c.message_count,
            "last_message": c.last_message,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
        }
