from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float
from sqlalchemy.sql import func
from db.database import Base

class Subreddit(Base):
    __tablename__ = "subreddits"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(Text, nullable=True)
    subscribers = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    reddit_id = Column(String, unique=True, index=True)
    title = Column(String, nullable=False)
    body = Column(Text, nullable=True)
    author = Column(String, nullable=True)
    score = Column(Integer, default=0)
    subreddit_id = Column(Integer, ForeignKey("subreddits.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # chromadb ID reference
    embedding_id = Column(String, nullable=True)

class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    reddit_id = Column(String, unique=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"))
    body = Column(Text, nullable=False)
    author = Column(String, nullable=True)
    score = Column(Integer, default=0)
    parent_id = Column(String, nullable=True)

class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True, index=True)
    agent_name = Column(String, index=True)
    task = Column(Text, nullable=False)
    result = Column(Text, nullable=True)
    latency = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
