from datetime import datetime, timedelta
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Text, CheckConstraint
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    discord_id = Column(String, primary_key=True)
    username   = Column(String, nullable=False)   # username global do Discord
    nick       = Column(String)                    # apelido no servidor (sincronizado pelo bot)
    avatar_url = Column(String)
    is_admin   = Column(Boolean, nullable=False, default=False)

    characters   = relationship("Character", back_populates="user", cascade="all, delete-orphan")
    memberships  = relationship("PartyMember", back_populates="user", cascade="all, delete-orphan")
    confirmations = relationship("ScheduleConfirmation", back_populates="user", cascade="all, delete-orphan")
    pokemon_use  = relationship("Pokemon", back_populates="assigned_user")
    history      = relationship("History", back_populates="actor")


class Character(Base):
    __tablename__ = "characters"

    id      = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.discord_id", ondelete="CASCADE"), nullable=False)
    name    = Column(String, nullable=False)

    user      = relationship("User", back_populates="characters")
    schedules = relationship("Schedule", back_populates="character")


class Party(Base):
    __tablename__ = "parties"

    id   = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)

    members   = relationship("PartyMember", back_populates="party", cascade="all, delete-orphan")
    schedules = relationship("Schedule", back_populates="party")


class PartyMember(Base):
    __tablename__ = "party_members"
    __table_args__ = (
        CheckConstraint("role IN ('DPS','SUP','TANK')", name="ck_party_role"),
    )

    party_id     = Column(Integer, ForeignKey("parties.id", ondelete="CASCADE"), primary_key=True)
    user_id      = Column(String, ForeignKey("users.discord_id", ondelete="CASCADE"), primary_key=True)
    role         = Column(String, nullable=False)
    character_id = Column(Integer, ForeignKey("characters.id", ondelete="SET NULL"))  # NULL = convidado sem personagem ainda

    party     = relationship("Party", back_populates="members")
    user      = relationship("User", back_populates="memberships")
    character = relationship("Character")


class Schedule(Base):
    __tablename__ = "schedules"
    __table_args__ = (
        CheckConstraint("difficulty IN ('HARD','NW')", name="ck_schedule_difficulty"),
        CheckConstraint("status IN ('pending','confirmed','rescheduled','missed','cancelled')", name="ck_schedule_status"),
    )

    id           = Column(Integer, primary_key=True, autoincrement=True)
    party_id     = Column(Integer, ForeignKey("parties.id", ondelete="CASCADE"), nullable=False)
    character_id = Column(Integer, ForeignKey("characters.id", ondelete="SET NULL"))  # NULL = PT organizada por admin sem se incluir
    organizer_id = Column(String, ForeignKey("users.discord_id", ondelete="SET NULL"))  # quem criou a PT
    difficulty   = Column(String, nullable=False)
    start_time   = Column(DateTime, nullable=False)
    end_time     = Column(DateTime, nullable=False)
    status       = Column(String, nullable=False, default="pending")

    party         = relationship("Party", back_populates="schedules")
    character     = relationship("Character", back_populates="schedules")
    confirmations = relationship("ScheduleConfirmation", back_populates="schedule", cascade="all, delete-orphan")

    @staticmethod
    def calc_end(start: datetime) -> datetime:
        return start + timedelta(hours=3)


class ScheduleConfirmation(Base):
    __tablename__ = "schedule_confirmations"

    schedule_id = Column(Integer, ForeignKey("schedules.id", ondelete="CASCADE"), primary_key=True)
    user_id     = Column(String, ForeignKey("users.discord_id", ondelete="CASCADE"), primary_key=True)
    confirmed   = Column(Boolean, nullable=False, default=False)
    last_ping   = Column(DateTime)

    schedule = relationship("Schedule", back_populates="confirmations")
    user     = relationship("User", back_populates="confirmations")


class Pokemon(Base):
    __tablename__ = "pokemon"
    __table_args__ = (
        CheckConstraint("category IN ('A','B','C')", name="ck_pokemon_category"),
    )

    id          = Column(Integer, primary_key=True, autoincrement=True)
    name        = Column(String, nullable=False)
    image_url   = Column(String)
    category    = Column(String, nullable=False)
    assigned_to = Column(String, ForeignKey("users.discord_id", ondelete="SET NULL"))
    assigned_at = Column(DateTime)

    assigned_user = relationship("User", back_populates="pokemon_use")


class History(Base):
    __tablename__ = "history"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    actor_id    = Column(String, ForeignKey("users.discord_id", ondelete="SET NULL"))
    entity_type = Column(String, nullable=False)
    entity_id   = Column(Integer)
    action      = Column(String, nullable=False)
    detail      = Column(Text)
    happened_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    actor = relationship("User", back_populates="history")


class Outbox(Base):
    """Fila de mensagens da API para o bot enviar no Discord (processos separados)."""
    __tablename__ = "outbox"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    kind           = Column(String, nullable=False)   # ex: 'party_invite'
    target_user_id = Column(String, nullable=False)   # discord_id do destinatário
    payload        = Column(Text)                      # JSON com contexto
    created_at     = Column(DateTime, nullable=False, default=datetime.utcnow)
    sent_at        = Column(DateTime)                  # NULL = ainda não enviado
