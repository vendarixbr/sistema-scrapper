"""Calculates a commercial quality score (0–100) for each lead."""

import logging
from models.lead import Lead

logger = logging.getLogger(__name__)


class QualityScorer:
    """Assigns a quality score and label to health professional leads."""

    def score(self, lead: Lead) -> Lead:
        """Calculate score, assign label, return updated lead copy."""
        pts = 0

        if lead.telefone_1:
            pts += 20

        nota = lead.avaliacao_nota or 0.0
        qtd = lead.avaliacao_quantidade or 0
        if nota >= 4.5 and qtd > 10:
            pts += 20
        elif nota >= 4.0 and qtd > 5:
            pts += 10

        if lead.crm:
            pts += 15

        # No personal website = opportunity to sell one
        if not lead.tem_site:
            pts += 15

        if lead.instagram:
            pts += 5

        if lead.planos_saude and len(lead.planos_saude) > 3:
            pts += 5

        if lead.servicos and len(lead.servicos) > 5:
            pts += 5

        if lead.whatsapp:
            pts += 10

        if lead.bairro and lead.endereco:
            pts += 5

        pts = max(0, min(100, pts))

        match True:
            case _ if pts >= 80:
                label = "🔥 Lead Quente"
            case _ if pts >= 60:
                label = "⭐ Lead Qualificado"
            case _ if pts >= 40:
                label = "👀 Lead Morno"
            case _:
                label = "❄️ Lead Frio"

        return lead.model_copy(update={"score_qualidade": pts, "score_label": label})

    def score_all(self, leads: list[Lead]) -> list[Lead]:
        """Score every lead in the list and return the updated list."""
        scored = [self.score(lead) for lead in leads]
        hot = sum(1 for l in scored if l.score_qualidade >= 80)
        warm = sum(1 for l in scored if 60 <= l.score_qualidade < 80)
        logger.info("Scored %d leads — 🔥 %d quentes, ⭐ %d qualificados.", len(scored), hot, warm)
        return scored
