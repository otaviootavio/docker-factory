from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from src.utils.logging import setup_logging
from dotenv import load_dotenv
import os

logger = setup_logging(__name__)

# Retrieve the database URL from environment variables
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in the .env file")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Deployment(Base):
    __tablename__ = 'deployments'

    id = Column(Integer, primary_key=True)
    service_name = Column(String, unique=True)
    client_id = Column(String)
    image_tag = Column(String)
    status = Column(String)
    rpc_endpoint = Column(String)
    ws_endpoint = Column(String)
    access_token = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)


def save_deployment(deployment_info, client_id):
    db = SessionLocal()
    try:
        deployment = Deployment(
            service_name=deployment_info['service_name'],
            client_id=client_id,
            image_tag=deployment_info.get('image_tag', ''),
            status='RUNNING',
            rpc_endpoint=deployment_info.get('rpc_endpoint', ''),
            ws_endpoint=deployment_info.get('ws_endpoint', ''),
            access_token=deployment_info.get('access_token', '')
        )
        db.add(deployment)
        db.commit()
        db.refresh(deployment)
        return deployment
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving deployment to the database: {e}")
        raise  # Re-raise exception to propagate error
    finally:
        db.close()


def get_deployment(service_name):
    db = SessionLocal()
    try:
        return db.query(Deployment).filter_by(service_name=service_name).first()
    finally:
        db.close()


def list_deployments(client_id):
    db = SessionLocal()
    try:
        return db.query(Deployment).filter_by(client_id=client_id).all()
    finally:
        db.close()


init_db()
