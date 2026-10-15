
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict


class TransacaoBase(BaseModel):
    descricao: str = Field(min_length=1, max_length=150)
    valor: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    tipo: Literal["receita", "despesa"]
    data_transacao: date
    categoria_id: int = Field(gt=0)
    observacao: str | None = None


class TransacaoCriar(TransacaoBase):
    pass


class TransacaoAtualizar(TransacaoBase):
    pass


class TransacaoResposta(TransacaoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int




# Modelos para contas fixas

class ContaFixaBase(BaseModel):
    descricao: str = Field(min_length=1, max_length=150)
    valor: Decimal = Field(
        gt=0, max_digits=12, decimal_places=2
    )
    dia_vencimento: int = Field(ge=1, le=31)
    categoria_id: int = Field(gt=0)
    ativa: bool = True


class ContaFixaCriar(ContaFixaBase):
    pass


class ContaFixaAtualizar(ContaFixaBase):
    pass


class ContaFixaResposta(ContaFixaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
