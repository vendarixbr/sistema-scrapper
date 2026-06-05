"""Lead model representing an individual health professional."""

import re
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class Lead(BaseModel):
    """Represents a health professional lead extracted from Doctoralia."""

    nome: str
    titulo: str = ""
    especialidade: str
    cidade: str
    estado: str = ""
    endereco: Optional[str] = None
    bairro: Optional[str] = None
    telefone_1: Optional[str] = None
    telefone_2: Optional[str] = None
    whatsapp: Optional[str] = None
    email: Optional[str] = None
    crm: Optional[str] = None
    rqe: Optional[str] = None
    avaliacao_nota: float = 0.0
    avaliacao_quantidade: int = 0
    planos_saude: list[str] = Field(default_factory=list)
    servicos: list[str] = Field(default_factory=list)
    tem_site: bool = False
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    doctoralia_url: str
    score_qualidade: int = 0
    score_label: str = ""
    filtro_motivo: str = ""
    data_extracao: datetime = Field(default_factory=datetime.now)
    fonte: str = "doctoralia"

    model_config = {"validate_assignment": True}

    @field_validator("nome")
    @classmethod
    def clean_nome(cls, v: str) -> str:
        """Remove extra whitespace from name."""
        return " ".join(v.strip().split())

    @field_validator("avaliacao_nota", mode="before")
    @classmethod
    def validate_nota(cls, v) -> float:
        """Clamp rating between 0.0 and 5.0."""
        if v is None:
            return 0.0
        try:
            v = float(str(v).replace(",", "."))
        except (ValueError, TypeError):
            return 0.0
        return max(0.0, min(5.0, v))

    @field_validator("telefone_1", "telefone_2", "whatsapp", mode="before")
    @classmethod
    def normalize_telefone(cls, v) -> Optional[str]:
        """Keep only digits and leading + in phone numbers."""
        if not v:
            return None
        cleaned = re.sub(r"[^\d+]", "", str(v))
        return cleaned if len(cleaned) >= 8 else None
