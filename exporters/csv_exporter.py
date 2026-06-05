"""CSV exporter for lead data with UTF-8 BOM encoding for Excel compatibility."""

import csv
import logging
from datetime import datetime
from pathlib import Path
from models.lead import Lead
from config import OUTPUT_DIR

logger = logging.getLogger(__name__)

# Maps Lead field names to Portuguese column headers
HEADERS_PT: dict[str, str] = {
    "nome": "Nome",
    "titulo": "Título",
    "especialidade": "Especialidade",
    "cidade": "Cidade",
    "estado": "Estado",
    "endereco": "Endereço",
    "bairro": "Bairro",
    "telefone_1": "Telefone 1",
    "telefone_2": "Telefone 2",
    "whatsapp": "WhatsApp",
    "email": "E-mail",
    "crm": "CRM",
    "rqe": "RQE",
    "avaliacao_nota": "Nota Avaliação",
    "avaliacao_quantidade": "Qtd. Avaliações",
    "planos_saude": "Planos de Saúde",
    "servicos": "Serviços",
    "tem_site": "Tem Site",
    "instagram": "Instagram",
    "facebook": "Facebook",
    "doctoralia_url": "URL Doctoralia",
    "score_qualidade": "Score",
    "score_label": "Classificação",
    "data_extracao": "Data Extração",
}


def _format_value(value) -> str:
    """Convert a Lead field value to a plain string."""
    if value is None:
        return ""
    if isinstance(value, list):
        return " | ".join(str(v) for v in value)
    if isinstance(value, bool):
        return "Sim" if value else "Não"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value)


class CSVExporter:
    """Exports a list of Lead objects to a UTF-8 BOM CSV file."""

    def save(self, leads: list[Lead], filename: str = "leads") -> str:
        """Save leads to output/{filename}_{timestamp}.csv and return the path."""
        Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = Path(OUTPUT_DIR) / f"{filename}_{timestamp}.csv"

        fields = list(HEADERS_PT.keys())
        headers = list(HEADERS_PT.values())

        with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for lead in leads:
                row = [_format_value(getattr(lead, field, "")) for field in fields]
                writer.writerow(row)

        logger.info("CSV saved: %s (%d leads)", filepath, len(leads))
        return str(filepath)
