"""Central configuration for health-lead-extractor."""

import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL: str = "https://www.doctoralia.com.br"
SEARCH_URL: str = "{BASE_URL}/{especialidade}/{cidade}"

REQUEST_DELAY_MIN: float = float(os.getenv("REQUEST_DELAY_MIN", "2.0"))
REQUEST_DELAY_MAX: float = float(os.getenv("REQUEST_DELAY_MAX", "5.0"))
MAX_RETRIES: int = 3
TIMEOUT: int = 30000  # milliseconds for Playwright
MAX_PAGES: int = int(os.getenv("MAX_PAGES", "20"))
OUTPUT_DIR: str = "output"
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

PALAVRAS_CLINICA: list[str] = [
    "clínica", "clinica", "centro", "instituto",
    "hospital", "grupo", "saúde", "saude", "unidade", "ltda", "s/a", "eireli",
    "me ", "associação", "associacao", "fundação", "fundacao", "consultório coletivo",
    "policlínica", "policlinica", "núcleo", "nucleo", "espaço", "espaco",
    "life", "medical", "health", "care", "med ", "plus", "prime", "senior",
    "bem estar", "bem-estar", "wellness", "odonto", "ortho", "dental center",
]

TITULOS_PROFISSIONAL: list[str] = [
    "dr.", "dra.", "dr ", "dra ", "prof.", "profa.", "especialista",
]

ESPECIALIDADES_SLUGS: dict[str, str] = {
    "ginecologista": "ginecologista",
    "cardiologista": "cardiologista",
    "dermatologista": "dermatologista",
    "ortopedista": "ortopedista",
    "neurologista": "neurologista",
    "psiquiatra": "psiquiatra",
    "urologista": "urologista",
    "oftalmologista": "oftalmologista",
    "pediatra": "pediatra",
    "endocrinologista": "endocrinologista",
    "otorrinolaringologista": "otorrinolaringologista",
    "gastroenterologista": "gastroenterologista",
    "reumatologista": "reumatologista",
    "dentista": "dentista",
    "psicologo": "psicologo",
    "nutricionista": "nutricionista",
    "fisioterapeuta": "fisioterapeuta",
}
