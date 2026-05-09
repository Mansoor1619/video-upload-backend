from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, JSON
from database import Base


class GameData(Base):
    __tablename__ = "game_data"

    id = Column(Integer, primary_key=True, index=True)
    location = Column(JSON)
    date = Column(String(64))
    length = Column(Float)
    width = Column(Float)
    video_data = Column(Text)
    payload = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
