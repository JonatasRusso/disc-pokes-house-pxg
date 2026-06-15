"""Enums compartilhados (str, Enum) — valores idênticos aos gravados no banco,
então não exigem migração. Centralizam papéis, dificuldades, categorias e status,
dando validação automática no Pydantic e evitando strings cruas espalhadas."""
from enum import Enum


class PartyRole(str, Enum):
    TANK = "TANK"
    DPS  = "DPS"
    SUP  = "SUP"


class Difficulty(str, Enum):
    HARD = "HARD"
    NW   = "NW"


class PokemonCategory(str, Enum):
    A = "A"  # Tank
    B = "B"  # DPS
    C = "C"  # Sup


class ScheduleStatus(str, Enum):
    PENDING     = "pending"
    CONFIRMED   = "confirmed"
    RESCHEDULED = "rescheduled"
    MISSED      = "missed"
    CANCELLED   = "cancelled"


# Conjuntos/listas derivados (valores string), reutilizáveis nas rotas/serviços
ROLE_VALUES        = [r.value for r in PartyRole]
DIFFICULTY_VALUES  = [d.value for d in Difficulty]
CATEGORY_VALUES    = [c.value for c in PokemonCategory]
ACTIVE_STATUSES    = [ScheduleStatus.PENDING.value, ScheduleStatus.CONFIRMED.value, ScheduleStatus.RESCHEDULED.value]

# Composição da PT: 1 tank, 2 dps, 1 suporte
ROLE_CAPACITY = {PartyRole.TANK.value: 1, PartyRole.DPS.value: 2, PartyRole.SUP.value: 1}

# Mapeamentos papel <-> categoria de pokémon
ROLE_TO_CATEGORY = {PartyRole.TANK.value: "A", PartyRole.DPS.value: "B", PartyRole.SUP.value: "C"}
CATEGORY_LABEL   = {"A": "Tank", "B": "DPS", "C": "Sup"}
