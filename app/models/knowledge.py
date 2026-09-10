from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Text
from app.core.database import Base


class KnowledgeDoc(Base):
    __tablename__ = "knowledge_docs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    external_id = Column(String(100), nullable=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    category = Column(String(100), nullable=True, index=True)
    content = Column(Text, nullable=False)
    embedding_json = Column(Text, nullable=True) # Serialized list of floats for fast in-process cosine search
    tags = Column(String(255), nullable=True)
    
    # Access Group Scoping: JSON array of group IDs e.g. [1, 2]. Empty [] =
    # available to every agent. Mirrors CatalogItem's model — the primary
    # way the dashboard scopes a doc. The group IDs are also mirrored into
    # access_tags_json (as strings) so filter_items_by_access_tags / the RAG
    # retrieval path match them without a second query.
    access_group_ids_json = Column(Text, default="[]")

    # Access Tagging: JSON array of strings e.g. ["support", "billing"]. Empty [] = public to all agents.
    access_tags_json = Column(Text, default="[]")
    
    metadata_json = Column(Text, default="{}")
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
