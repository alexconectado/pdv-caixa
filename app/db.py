import os

from sqlmodel import Session, SQLModel, create_engine, select

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./pdv.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def get_session():
    with Session(engine) as session:
        yield session


def init_db():
    from app import models  # noqa: F401
    SQLModel.metadata.create_all(engine)


def create_default_admin():
    from passlib.hash import pbkdf2_sha256

    from app.models import RoleEnum, User
    with Session(engine) as session:
        admin = session.exec(select(User).where(User.username == "admin")).first()
        if not admin:
            admin = User(
                username="admin",
                full_name="Administrador",
                password_hash=pbkdf2_sha256.hash("admin123"),
                role=RoleEnum.admin,
                active=True,
            )
            session.add(admin)
            session.commit()
