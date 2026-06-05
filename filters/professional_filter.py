"""Filter to distinguish individual health professionals from clinics / businesses."""

import logging
from typing import Optional
from models.lead import Lead
from config import BASE_URL, PALAVRAS_CLINICA, TITULOS_PROFISSIONAL

logger = logging.getLogger(__name__)


class ProfessionalFilter:
    """Classifies leads as individual professionals or institutional entities."""

    def is_professional(self, lead: Lead) -> tuple[bool, str]:
        """
        Decide if a lead is an individual professional.

        Returns (is_professional, reason_code).
        """
        nome_lower = lead.nome.lower()
        url_lower = lead.doctoralia_url.lower()

        # Layer 1 — verified CRM always means an individual professional
        if lead.crm:
            return True, "has_crm"

        # Layer 2a — name contains clinic / business keywords → discard
        for palavra in PALAVRAS_CLINICA:
            if palavra.lower() in nome_lower:
                return False, f"name_contains:{palavra.strip()}"

        # Layer 2b — name starts with a professional title → keep
        for titulo in TITULOS_PROFISSIONAL:
            if nome_lower.startswith(titulo.lower().rstrip()):
                return True, "has_professional_title"

        # Layer 2c — name looks like "Nome Sobrenome" (2–4 capitalised words)
        words = [w for w in lead.nome.strip().split() if w]
        if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words):
            return True, "name_format_person"

        # Layer 3a — URL explicitly contains /clinica/ or /hospital/
        if "/clinica/" in url_lower or "/hospital/" in url_lower:
            return False, "url_contains_institution"

        # Layer 3b — URL follows /name-slug/specialty/city pattern
        path = url_lower.replace(BASE_URL.lower(), "").lstrip("/")
        parts = [p for p in path.split("/") if p]
        if parts:
            name_parts = parts[0].split("-")
            if 2 <= len(name_parts) <= 5:
                return True, "url_name_pattern"

        # Layer 4 — fallback: include but mark as uncertain
        return True, "uncertain"

    def filter_list(
        self, leads: list[Lead]
    ) -> tuple[list[Lead], list[Lead]]:
        """
        Split a list into (approved, discarded).
        Logs counts and reason breakdown.
        """
        approved: list[Lead] = []
        discarded: list[Lead] = []
        reason_counts: dict[str, int] = {}

        for lead in leads:
            is_prof, reason = self.is_professional(lead)
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
            lead.filtro_motivo = reason

            if is_prof:
                approved.append(lead)
            else:
                discarded.append(lead)

        logger.info(
            "Filter: %d approved, %d discarded (from %d total).",
            len(approved),
            len(discarded),
            len(leads),
        )
        for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
            logger.debug("  %-35s %d", reason, count)

        return approved, discarded
