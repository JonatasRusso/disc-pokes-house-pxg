import os
from datetime import datetime, timedelta, timezone

# Fuso da comunidade. O Brasil não tem horário de verão desde 2019,
# então um offset fixo é correto e evita depender da base de fusos (tzdata).
# Configurável via APP_UTC_OFFSET (em horas), padrão -3 (Brasília).
_OFFSET_HOURS = float(os.getenv("APP_UTC_OFFSET", "-3"))
LOCAL_TZ = timezone(timedelta(hours=_OFFSET_HOURS))


def now_local() -> datetime:
    """Hora local (naive) da comunidade — mesmo fuso em que os horários de PT são salvos."""
    return datetime.now(LOCAL_TZ).replace(tzinfo=None)
