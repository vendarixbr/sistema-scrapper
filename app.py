"""Streamlit entry point for Health Lead Extractor."""
import subprocess, sys

@st.cache_resource
def instalar_chromium():
    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=True
    )

instalar_chromium()
import json
import sys
from pathlib import Path

import streamlit as st

# ── Page config (must be the very first st call) ─────────────────────────── #
st.set_page_config(
    page_title="Health Lead Extractor",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Ensure project root is importable ────────────────────────────────────── #
_ROOT = Path(__file__).parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ui.extraction_runner import ExtractionRunner  # noqa: E402


# ── CSS ──────────────────────────────────────────────────────────────────── #
def _load_css() -> None:
    css_file = _ROOT / "ui" / "styles.css"
    if css_file.exists():
        st.markdown(f"<style>{css_file.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


# ── Sidebar ──────────────────────────────────────────────────────────────── #
def _sidebar() -> None:
    with st.sidebar:
        st.markdown(
            "<h2 style='color:#00897B;margin-bottom:0'>🏥 Health Lead</h2>"
            "<p style='color:#666;margin-top:0;font-size:13px'>Extractor — Doctoralia Brasil</p>",
            unsafe_allow_html=True,
        )
        st.divider()

        try:
            stats = ExtractionRunner().get_stats()
        except Exception:
            stats = {"total_leads": 0, "total_searches": 0, "hot_leads": 0, "with_phone": 0}

        st.markdown("##### 📊 Estatísticas Rápidas")
        c1, c2 = st.columns(2)
        c1.metric("Leads", stats["total_leads"])
        c1.metric("🔥 Quentes", stats["hot_leads"])
        c2.metric("Buscas", stats["total_searches"])
        c2.metric("📞 C/ Fone", stats.get("with_phone", 0))

        st.divider()
        st.markdown("##### Navegação")
        st.page_link("app.py",                        label="🏠 Início")
        st.page_link("pages/1_🔍_Nova_Busca.py",      label="🔍 Nova Busca")
        st.page_link("pages/2_📊_Dashboard.py",        label="📊 Dashboard")
        st.page_link("pages/3_📋_Histórico.py",        label="📋 Histórico")
        st.page_link("pages/4_⚙️_Configurações.py",   label="⚙️ Configurações")

        st.divider()
        st.caption("v1.0.0 · Health Lead Extractor")


# ── Home page ─────────────────────────────────────────────────────────────── #
def _home() -> None:
    st.title("🏥 Health Lead Extractor")
    st.markdown(
        "Extração automatizada de **profissionais de saúde individuais** do Doctoralia Brasil. "
        "Filtra clínicas, pontua oportunidades comerciais e exporta para CSV / Excel."
    )
    st.divider()

    col1, col2, col3 = st.columns(3)
    with col1:
        with st.container(border=True):
            st.markdown("### 🔍 Extrair Leads")
            st.markdown(
                "Busque por especialidade e cidade. "
                "Resultados filtrados e pontuados automaticamente."
            )
            if st.button("Iniciar Nova Busca", use_container_width=True, type="primary"):
                st.switch_page("pages/1_🔍_Nova_Busca.py")

    with col2:
        with st.container(border=True):
            st.markdown("### 📊 Dashboard")
            st.markdown(
                "Tabela interativa, filtros avançados, gráficos de distribuição e exportação por lote."
            )
            if st.button("Abrir Dashboard", use_container_width=True):
                st.switch_page("pages/2_📊_Dashboard.py")

    with col3:
        with st.container(border=True):
            st.markdown("### 📋 Histórico")
            st.markdown(
                "Todas as buscas realizadas, com opção de recarregar conjuntos anteriores."
            )
            if st.button("Ver Histórico", use_container_width=True):
                st.switch_page("pages/3_📋_Histórico.py")

    st.divider()
    st.subheader("🕐 Últimos Leads Capturados")

    db_path = _ROOT / "data" / "leads_database.json"
    if db_path.exists():
        try:
            data = json.loads(db_path.read_text(encoding="utf-8"))
            leads = data.get("leads", [])
            if leads:
                import pandas as pd
                recent = leads[-5:][::-1]
                df = pd.DataFrame(recent)
                cols_available = [c for c in
                    ["score_label", "nome", "especialidade", "cidade", "telefone_1", "score_qualidade"]
                    if c in df.columns]
                labels = {
                    "score_label": "Classificação", "nome": "Nome",
                    "especialidade": "Especialidade", "cidade": "Cidade",
                    "telefone_1": "Telefone", "score_qualidade": "Score",
                }
                df = df[cols_available].rename(columns=labels)
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum lead ainda. Clique em **Iniciar Nova Busca** para começar! 🚀")
        except Exception as exc:
            st.warning(f"Não foi possível carregar leads recentes: {exc}")
    else:
        st.info("Nenhum lead ainda. Clique em **Iniciar Nova Busca** para começar! 🚀")


_load_css()
_sidebar()
_home()
