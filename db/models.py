from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float
from sqlalchemy.sql import func
from db.database import Base

class TopicCategory(Base):
    __tablename__ = "topic_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Topic(Base):
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(Text, nullable=True)
    category_id = Column(Integer, ForeignKey("topic_categories.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    reddit_id = Column(String, unique=True, index=True)
    title = Column(String, nullable=False)
    body = Column(Text, nullable=True)
    author = Column(String, nullable=True)
    score = Column(Integer, default=0)
    topic_id = Column(Integer, ForeignKey("topics.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class BrightDataPost(Base):
    __tablename__ = "brightdata_posts"

    id = Column(Integer, primary_key=True, index=True)
    reddit_id = Column(String, unique=True, index=True)
    title = Column(String, nullable=False)
    body = Column(Text, nullable=True)
    author = Column(String, nullable=True)
    score = Column(Integer, default=0)
    topic_id = Column(Integer, ForeignKey("topics.id"))
    snapshot_id = Column(String, nullable=True) # BrightData Job ID Tracking
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    reddit_id = Column(String, unique=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"))
    body = Column(Text, nullable=False)
    author = Column(String, nullable=True)
    score = Column(Integer, default=0)
    
class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True, index=True)
    agent_name = Column(String, index=True)
    task = Column(Text, nullable=False)
    result = Column(Text, nullable=True)
    evaluation_result = Column(Text, nullable=True) # Ranking/judgment from Critic
    latency = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
