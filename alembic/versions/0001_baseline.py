"""baseline — esquema atual a partir dos modelos

Cria todas as tabelas via metadata (idempotente: pula tabelas existentes). Em um banco
de produção que já tem as tabelas, `alembic upgrade head` aqui é no-op e só registra a
versão; em banco novo, cria tudo. Migrações FUTURAS devem ser explícitas (op.add_column,
etc.) — gere com `alembic revision --autogenerate`.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-06-14
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from api.models import Base
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    from api.models import Base
    Base.metadata.drop_all(bind=op.get_bind())
