"""Main Doctoralia scraper — searches and extracts individual professional profiles."""

import asyncio
import logging
import re
import unicodedata
from typing import Optional
from bs4 import BeautifulSoup

from models.lead import Lead
from .browser_manager import BrowserManager
from .pagination_handler import PaginationHandler
from utils.rate_limiter import RateLimiter
from config import BASE_URL, ESPECIALIDADES_SLUGS, MAX_PAGES, TITULOS_PROFISSIONAL

logger = logging.getLogger(__name__)


def normalize_city_name(city: str) -> str:
    """Convert a city name to a URL-safe ASCII slug.

    Example: "Nova Serrana" → "nova-serrana"
    """
    nfd = unicodedata.normalize("NFD", city)
    ascii_str = "".join(c for c in nfd if not unicodedata.combining(c))
    slug = ascii_str.lower().strip().replace(" ", "-")
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    slug = re.sub(r"-{2,}", "-", slug)
    return slug.strip("-")


class DoctoraliaScraper:
    """Scrapes professional listings and individual profiles from Doctoralia Brasil."""

    def __init__(self, browser_manager: BrowserManager, max_pages: int = MAX_PAGES) -> None:
        self._browser = browser_manager
        self._max_pages = max_pages
        self._rate = RateLimiter()
        self._visited_urls: set[str] = set()
        self._block_count: int = 0
        self._leads_collected: list[Lead] = []  # partial-save support

    @property
    def page(self):
        return self._browser.page

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    async def search(self, especialidade: str, cidade: str) -> list[Lead]:
        """Search Doctoralia for professionals and return enriched Lead objects."""
        esp_slug = ESPECIALIDADES_SLUGS.get(especialidade.lower(), normalize_city_name(especialidade))
        city_slug = normalize_city_name(cidade)
        search_url = f"{BASE_URL}/{esp_slug}/{city_slug}"

        logger.info("Starting search: %s", search_url)

        try:
            await self.page.goto(search_url, wait_until="domcontentloaded", timeout=30_000)
        except Exception as exc:
            logger.error("Navigation to %s failed: %s", search_url, exc)
            return []

        await self._post_nav_cleanup()

        if await self._is_no_results():
            logger.info("No results page detected — returning empty list.")
            return []

        if await self._is_captcha_or_blocked():
            logger.warning("Captcha / block detected on search page.")
            return []

        pagination = PaginationHandler(self.page, self._max_pages)
        base_leads: list[Lead] = []

        # ---- Collect listing cards across all pages ----
        while True:
            try:
                await self.page.wait_for_load_state("networkidle", timeout=12_000)
            except Exception:
                pass

            page_leads = await self._extract_page_results(especialidade, cidade)
            base_leads.extend(page_leads)
            logger.info(
                "Page %d: +%d leads (running total %d).",
                pagination.current_page,
                len(page_leads),
                len(base_leads),
            )

            if not await pagination.has_next_page():
                break

            await self._rate.sleep_between_pages()

            if not await pagination.go_to_next_page():
                break

            await self._post_nav_cleanup()

            if pagination.block_count >= 1:
                await self._handle_block(pagination.block_count)

        # ---- Fetch profile details for each unique listing ----
        unique_leads = self._deduplicate(base_leads)
        logger.info("Fetching details for %d unique profiles…", len(unique_leads))

        for i, lead in enumerate(unique_leads, 1):
            logger.info("Profile %d/%d — %s", i, len(unique_leads), lead.nome)
            detailed = await self._safe_get_profile(lead)
            self._leads_collected.append(detailed)
            await self._rate.sleep_between_profiles()

        return self._leads_collected

    # ------------------------------------------------------------------ #
    #  Listing-page helpers                                                #
    # ------------------------------------------------------------------ #

    async def _extract_page_results(self, especialidade: str, cidade: str) -> list[Lead]:
        """Parse all doctor cards on the current results page."""
        content = await self.page.content()
        soup = BeautifulSoup(content, "lxml")
        leads: list[Lead] = []

        cards = self._find_cards(soup)

        if not cards:
            logger.warning("No cards found — falling back to href scan.")
            return self._fallback_href_leads(soup, especialidade, cidade)

        for card in cards:
            lead = self._parse_card(card, especialidade, cidade)
            if lead and lead.doctoralia_url not in self._visited_urls:
                leads.append(lead)

        return leads

    def _find_cards(self, soup: BeautifulSoup) -> list:
        """Try multiple selectors to locate doctor listing cards."""
        attempts = [
            lambda: soup.find_all(attrs={"data-testid": "doctor-card"}),
            lambda: soup.select("article.doctor-card"),
            lambda: soup.select(".search-doctor-card"),
            lambda: soup.select("div[class*='DoctorCard']"),
            lambda: soup.select("div[class*='doctor-card']"),
            lambda: soup.select("li[class*='doctor']"),
            lambda: soup.select("[class*='SearchResult']"),
            lambda: soup.select("ul.search-results > li"),
        ]
        for attempt in attempts:
            result = attempt()
            if result:
                return result
        return []

    def _parse_card(self, card, especialidade: str, cidade: str) -> Optional[Lead]:
        """Extract a minimal Lead from a listing card element."""
        link = card.find("a", href=re.compile(r"/[a-z]"))
        if not link:
            return None

        href = link.get("href", "")
        profile_url = href if href.startswith("http") else f"{BASE_URL}{href}"

        # Skip institution-type URLs
        if any(skip in profile_url for skip in ["/clinica/", "/hospital/", "/busca/", "/search"]):
            return None

        nome = self._extract_text_multi(card, [
            {"data-id": "doctor-name"},
            {"itemprop": "name"},
            {"class": re.compile(r"doctor.?name", re.I)},
            {"class": re.compile(r"name", re.I)},
        ]) or self._first_heading_text(card) or link.get_text(strip=True)

        if not nome or len(nome) < 3:
            return None

        nota, qtd = self._extract_card_rating(card)

        endereco = self._extract_text_multi(card, [
            {"class": re.compile(r"address|location|addr", re.I)},
            {"itemprop": "streetAddress"},
        ])

        return Lead(
            nome=nome,
            especialidade=especialidade,
            cidade=cidade,
            endereco=endereco or None,
            avaliacao_nota=nota,
            avaliacao_quantidade=qtd,
            doctoralia_url=profile_url,
        )

    def _fallback_href_leads(self, soup: BeautifulSoup, especialidade: str, cidade: str) -> list[Lead]:
        """Create minimal leads from profile links when card selectors fail."""
        leads: list[Lead] = []
        seen: set[str] = set()
        for link in soup.find_all("a", href=re.compile(r"^/[a-z]")):
            href = link.get("href", "")
            if any(skip in href for skip in ["/clinica/", "/hospital/", "/busca/", "#"]):
                continue
            full_url = f"{BASE_URL}{href}"
            if full_url in seen:
                continue
            seen.add(full_url)
            nome = link.get_text(strip=True) or "Desconhecido"
            leads.append(Lead(nome=nome, especialidade=especialidade, cidade=cidade, doctoralia_url=full_url))
            if len(leads) >= 30:
                break
        return leads

    # ------------------------------------------------------------------ #
    #  Profile-page extraction                                             #
    # ------------------------------------------------------------------ #

    async def extract_profile_details(self, url: str, lead_base: Lead) -> Lead:
        """Navigate to a profile page and extract all available data."""
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        except Exception as exc:
            logger.warning("Could not load profile %s: %s", url, exc)
            return lead_base

        await asyncio.sleep(1.5)
        await self._post_nav_cleanup()

        try:
            await self.page.wait_for_load_state("networkidle", timeout=12_000)
        except Exception:
            pass

        content = await self.page.content()
        soup = BeautifulSoup(content, "lxml")

        crm, rqe = self._extract_crm_rqe(soup)
        telefone_1, telefone_2 = await self._extract_phones()
        endereco, bairro, cidade, estado = self._extract_address(soup)
        planos = self._extract_planos_saude(soup)
        servicos = self._extract_servicos(soup)
        instagram, facebook, tem_site = self._extract_social(soup)
        titulo = self._extract_titulo(lead_base.nome, soup)
        nota, qtd = self._extract_rating(soup)

        return lead_base.model_copy(update={
            "titulo": titulo or lead_base.titulo,
            "crm": crm,
            "rqe": rqe,
            "telefone_1": telefone_1,
            "telefone_2": telefone_2,
            "endereco": endereco or lead_base.endereco,
            "bairro": bairro,
            "cidade": cidade or lead_base.cidade,
            "estado": estado or lead_base.estado,
            "planos_saude": planos if planos else lead_base.planos_saude,
            "servicos": servicos if servicos else lead_base.servicos,
            "instagram": instagram,
            "facebook": facebook,
            "tem_site": tem_site,
            "avaliacao_nota": nota if nota > 0 else lead_base.avaliacao_nota,
            "avaliacao_quantidade": qtd if qtd > 0 else lead_base.avaliacao_quantidade,
        })

    async def _safe_get_profile(self, lead: Lead) -> Lead:
        """Attempt profile extraction up to 3 times; return base lead on failure."""
        self._visited_urls.add(lead.doctoralia_url)
        for attempt in range(3):
            try:
                return await self.extract_profile_details(lead.doctoralia_url, lead)
            except Exception as exc:
                logger.warning(
                    "Profile attempt %d/3 failed for %s: %s",
                    attempt + 1,
                    lead.doctoralia_url,
                    exc,
                )
                if attempt < 2:
                    await self._rate.sleep_on_error()
        logger.error("Returning base lead for: %s", lead.doctoralia_url)
        return lead

    def _extract_crm_rqe(self, soup: BeautifulSoup) -> tuple[Optional[str], Optional[str]]:
        text = soup.get_text(" ", strip=True)
        crm_match = re.search(r"CRM[:\s/-]*([A-Z]{0,2}[\s-]?\d{4,8})", text, re.I)
        rqe_match = re.search(r"RQE[:\s/#-]*(\d{3,8})", text, re.I)
        return (
            crm_match.group(1).strip() if crm_match else None,
            rqe_match.group(1).strip() if rqe_match else None,
        )

    async def _extract_phones(self) -> tuple[Optional[str], Optional[str]]:
        """Click 'Mostrar número' and capture revealed phone numbers."""
        show_selectors = [
            "button:has-text('Mostrar número')",
            "button:has-text('Ver número')",
            "button:has-text('Ligar')",
            "[data-action='show-phone']",
            "button[data-testid*='phone']",
            "a[data-phone]",
        ]

        phones: list[str] = []

        for sel in show_selectors:
            try:
                buttons = await self.page.query_selector_all(sel)
                for btn in buttons[:2]:
                    try:
                        await btn.scroll_into_view_if_needed()
                        await asyncio.sleep(0.4)
                        await btn.click()
                        await asyncio.sleep(2)
                    except Exception:
                        pass

                if buttons:
                    break
            except Exception:
                continue

        # Scrape revealed phone numbers from updated page
        content = await self.page.content()
        soup = BeautifulSoup(content, "lxml")

        for elem in soup.find_all(attrs={"class": re.compile(r"phone|tel|contact|numero", re.I)}):
            for match in re.finditer(r"[\+\d][\d\s()\-]{7,}", elem.get_text()):
                phone = re.sub(r"\s+", "", match.group())
                if phone not in phones and len(phone) >= 8:
                    phones.append(phone)

        # Fallback: scan all tel: links
        if not phones:
            for link in soup.find_all("a", href=re.compile(r"^tel:")):
                phone = re.sub(r"[^\d+]", "", link.get("href", ""))
                if phone and phone not in phones:
                    phones.append(phone)

        return (phones[0] if phones else None, phones[1] if len(phones) > 1 else None)

    def _extract_address(
        self, soup: BeautifulSoup
    ) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        endereco = bairro = cidade = estado = None

        # Schema.org structured data — most reliable
        postal = soup.find(attrs={"itemtype": "http://schema.org/PostalAddress"})
        if postal:
            def _itemprop(prop: str) -> Optional[str]:
                el = postal.find(attrs={"itemprop": prop})
                return el.get_text(strip=True) if el else None

            endereco = _itemprop("streetAddress")
            bairro = _itemprop("addressRegion") or _itemprop("addressLocality")
            cidade = _itemprop("addressLocality")
            estado = _itemprop("addressRegion")

        # CSS class fallback
        if not endereco:
            for sel in [
                {"class": re.compile(r"address|location|endereco", re.I)},
                {"data-testid": "address"},
            ]:
                el = soup.find(attrs=sel)
                if el:
                    endereco = el.get_text(strip=True)
                    parts = [p.strip() for p in endereco.split(",") if p.strip()]
                    if len(parts) >= 2:
                        bairro = parts[1]
                    break

        return endereco, bairro, cidade, estado

    def _extract_planos_saude(self, soup: BeautifulSoup) -> list[str]:
        planos: list[str] = []
        section = None

        for sel in [
            {"class": re.compile(r"insurance|plano|health.?plan|convenio", re.I)},
            {"data-testid": "insurance-list"},
        ]:
            section = soup.find(attrs=sel)
            if section:
                break

        if not section:
            for h in soup.find_all(["h2", "h3", "h4", "h5"]):
                text = h.get_text().lower()
                if "plano" in text or "convênio" in text or "convenio" in text:
                    section = h.find_next_sibling()
                    break

        if section:
            for item in section.find_all(["li", "span", "p", "div"]):
                text = item.get_text(strip=True)
                if text and 3 <= len(text) <= 80:
                    planos.append(text)

        return list(dict.fromkeys(planos))[:20]  # deduplicate, cap at 20

    def _extract_servicos(self, soup: BeautifulSoup) -> list[str]:
        servicos: list[str] = []
        section = None

        for sel in [
            {"class": re.compile(r"service|procedure|tratamento|procedimento", re.I)},
            {"data-testid": "services-list"},
        ]:
            section = soup.find(attrs=sel)
            if section:
                break

        if not section:
            for h in soup.find_all(["h2", "h3", "h4", "h5"]):
                text = h.get_text().lower()
                if any(w in text for w in ["serviço", "servico", "procedimento", "tratamento"]):
                    section = h.find_next_sibling()
                    break

        if section:
            for item in section.find_all(["li", "span"]):
                text = item.get_text(strip=True)
                if text and 3 <= len(text) <= 100:
                    servicos.append(text)

        return list(dict.fromkeys(servicos))[:10]

    def _extract_social(
        self, soup: BeautifulSoup
    ) -> tuple[Optional[str], Optional[str], bool]:
        instagram = facebook = None
        tem_site = False

        for link in soup.find_all("a", href=True):
            href: str = link["href"]
            if "instagram.com" in href:
                instagram = href
            elif "facebook.com" in href:
                facebook = href
            elif (
                href.startswith("http")
                and not any(
                    domain in href
                    for domain in ["doctoralia", "facebook", "instagram", "whatsapp", "google", "apple"]
                )
            ):
                tem_site = True

        return instagram, facebook, tem_site

    def _extract_titulo(self, nome: str, soup: BeautifulSoup) -> str:
        nome_lower = nome.lower()
        for titulo in TITULOS_PROFISSIONAL:
            if nome_lower.startswith(titulo.lower().rstrip()):
                return titulo.strip().rstrip(".")  + "."

        h1 = soup.find("h1")
        if h1:
            h1_lower = h1.get_text(strip=True).lower()
            for titulo in TITULOS_PROFISSIONAL:
                if h1_lower.startswith(titulo.lower().rstrip()):
                    return titulo.strip()

        return ""

    def _extract_rating(self, soup: BeautifulSoup) -> tuple[float, int]:
        nota, qtd = 0.0, 0

        agg = soup.find(attrs={"itemtype": "http://schema.org/AggregateRating"})
        if agg:
            val_el = agg.find(attrs={"itemprop": "ratingValue"})
            cnt_el = agg.find(attrs={"itemprop": ["reviewCount", "ratingCount"]})
            if val_el:
                try:
                    nota = float(val_el.get_text(strip=True).replace(",", "."))
                except ValueError:
                    pass
            if cnt_el:
                digits = re.sub(r"\D", "", cnt_el.get_text())
                qtd = int(digits) if digits else 0

        return nota, qtd

    def _extract_card_rating(self, card) -> tuple[float, int]:
        nota, qtd = 0.0, 0
        for elem in card.find_all(attrs={"class": re.compile(r"rating|score|star|nota", re.I)}):
            m = re.search(r"(\d+[.,]\d+)", elem.get_text())
            if m:
                try:
                    nota = float(m.group(1).replace(",", "."))
                    break
                except ValueError:
                    pass
        for elem in card.find_all(attrs={"class": re.compile(r"review|opinion|avaliaç|rating.?count", re.I)}):
            m = re.search(r"(\d+)", elem.get_text())
            if m:
                qtd = int(m.group(1))
                break
        return nota, qtd

    # ------------------------------------------------------------------ #
    #  Utility helpers                                                     #
    # ------------------------------------------------------------------ #

    async def _post_nav_cleanup(self) -> None:
        await asyncio.sleep(0.8)
        await self._browser.close_modals()
        await self._browser.accept_cookies()

    async def _is_no_results(self) -> bool:
        content = (await self.page.content()).lower()
        return any(
            phrase in content
            for phrase in [
                "nenhum resultado",
                "não encontramos",
                "nao encontramos",
                "no results",
                "0 profissionais",
                "0 resultados",
            ]
        )

    async def _is_captcha_or_blocked(self) -> bool:
        url = self.page.url
        if any(p in url for p in ["/login", "/captcha", "/bloqueado", "/blocked", "/verify"]):
            return True
        try:
            title = (await self.page.title()).lower()
            return any(p in title for p in ["captcha", "access denied", "bot detected"])
        except Exception:
            return False

    async def _handle_block(self, block_count: int) -> None:
        if block_count >= 3:
            logger.warning("3 blocks in a row — pausing 5 minutes.")
            await self._rate.sleep_extended_block()
        else:
            logger.warning("Block #%d — pausing 60 seconds.", block_count)
            await self._rate.sleep_on_block()

    def _deduplicate(self, leads: list[Lead]) -> list[Lead]:
        seen: set[str] = set()
        unique: list[Lead] = []
        for lead in leads:
            if lead.doctoralia_url not in seen:
                seen.add(lead.doctoralia_url)
                unique.append(lead)
        dupes = len(leads) - len(unique)
        if dupes:
            logger.info("Removed %d duplicate listings.", dupes)
        return unique

    @staticmethod
    def _extract_text_multi(elem, selectors: list) -> Optional[str]:
        """Try multiple attribute-dict selectors; return first non-empty text found."""
        for sel in selectors:
            found = elem.find(attrs=sel)
            if found:
                text = found.get_text(strip=True)
                if text:
                    return text
        return None

    @staticmethod
    def _first_heading_text(elem) -> Optional[str]:
        for tag in ["h1", "h2", "h3"]:
            found = elem.find(tag)
            if found:
                text = found.get_text(strip=True)
                if text:
                    return text
        return None
