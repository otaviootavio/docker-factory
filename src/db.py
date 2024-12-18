from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from contextlib import contextmanager
import os

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in the .env file")

# Configure engine with connection pool settings to handle SSL EOF errors
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Key setting to detect stale connections
    pool_size=5,  # Adjust based on your needs
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=3600,  # Recycle connections after 1 hour
    connect_args={"keepalives": 1, "keepalives_idle": 30, "keepalives_interval": 5, "keepalives_count": 5},
)

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Deployment(Base):
    __tablename__ = "deployments"

    id = Column(Integer, primary_key=True)
    service_name = Column(String, unique=True)
    client_id = Column(String)
    image_tag = Column(String)
    status = Column(String)
    rpc_endpoint = Column(String)
    ws_endpoint = Column(String)
    access_token = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def save_deployment(deployment_info, client_id):
    with get_db() as db:
        try:
            deployment = Deployment(
                service_name=deployment_info["service_name"],
                client_id=client_id,
                image_tag=deployment_info.get("image_tag", ""),
                status="RUNNING",
                rpc_endpoint=deployment_info.get("rpc_endpoint", ""),
                ws_endpoint=deployment_info.get("ws_endpoint", ""),
                access_token=deployment_info.get("access_token", ""),
            )
            db.add(deployment)
            db.commit()
            db.refresh(deployment)
            return deployment
        except Exception as e:
            db.rollback()
            raise


def get_deployment(service_name):
    with get_db() as db:
        return db.query(Deployment).filter_by(service_name=service_name).first()


def list_deployments(client_id):
    with get_db() as db:
        return db.query(Deployment).filter_by(client_id=client_id).all()


def init_db():
    Base.metadata.create_all(bind=engine)


init_db()
