"""Configurações persistidas do sistema."""

import io
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ui.extraction_runner import ExtractionRunner  # noqa: E402
from ui.components import show_toast, confirm_dialog  # noqa: E402

with st.sidebar:
    st.markdown("### ⚙️ Configurações")
    st.page_link("app.py", label="← Início")

st.header("⚙️ Configurações")

runner = ExtractionRunner()
settings = runner.load_settings()
changed = False

# ══════════════════════════════════════════════════════════════════════════ #
#  Preferências de Extração                                                  #
# ══════════════════════════════════════════════════════════════════════════ #
with st.expander("🔧 Preferências de Extração", expanded=True):
    c1, c2 = st.columns(2)
    with c1:
        delay_min = st.slider(
            "Delay mínimo entre requests (s)",
            1.0, 10.0, float(settings.get("request_delay_min", 2.0)), 0.5,
        )
        max_pag = st.slider(
            "Máximo de páginas padrão",
            1, 20, int(settings.get("max_pages_default", 10)),
        )
    with c2:
        delay_max = st.slider(
            "Delay máximo entre requests (s)",
            2.0, 15.0, float(settings.get("request_delay_max", 5.0)), 0.5,
        )
        headless_def = st.toggle(
            "Modo headless padrão",
            value=bool(settings.get("headless_default", True)),
        )

    if delay_min > delay_max:
        st.warning("⚠️ Delay mínimo não pode ser maior que o máximo.")

# ══════════════════════════════════════════════════════════════════════════ #
#  Filtros Padrão                                                            #
# ══════════════════════════════════════════════════════════════════════════ #
with st.expander("🔍 Filtros Padrão", expanded=False):
    min_score_def = st.slider(
        "Score mínimo padrão",
        0, 100, int(settings.get("min_score_default", 0)),
    )

    from config import PALAVRAS_CLINICA, TITULOS_PROFISSIONAL  # noqa: E402

    custom_clinica = settings.get("custom_palavras_clinica", [])
    custom_titulos = settings.get("custom_titulos_profissional", [])

    clinica_text = st.text_area(
        "Palavras para filtro de clínica (uma por linha)",
        value="\n".join(custom_clinica) if custom_clinica else "",
        height=120,
        help="Estas palavras são ADICIONADAS às palavras padrão do sistema.",
    )
    titulos_text = st.text_area(
        "Títulos profissionais reconhecidos (um por linha)",
        value="\n".join(custom_titulos) if custom_titulos else "",
        height=80,
        help="Estes títulos são ADICIONADOS aos títulos padrão do sistema.",
    )

    st.caption(
        f"**Palavras padrão de clínica ({len(PALAVRAS_CLINICA)}):** "
        + ", ".join(PALAVRAS_CLINICA[:8]) + "…"
    )
    st.caption(
        f"**Títulos padrão ({len(TITULOS_PROFISSIONAL)}):** "
        + ", ".join(TITULOS_PROFISSIONAL)
    )

# ══════════════════════════════════════════════════════════════════════════ #
#  Exportação                                                                #
# ══════════════════════════════════════════════════════════════════════════ #
with st.expander("📤 Exportação", expanded=False):
    c1, c2 = st.columns(2)
    with c1:
        csv_sep = st.selectbox(
            "Separador CSV",
            [",", ";"],
            index=0 if settings.get("csv_separator", ",") == "," else 1,
        )
    with c2:
        output_dir = st.text_input(
            "Pasta de destino padrão",
            value=settings.get("output_dir", "output"),
        )

# ══════════════════════════════════════════════════════════════════════════ #
#  Banco de Dados                                                            #
# ══════════════════════════════════════════════════════════════════════════ #
with st.expander("🗄️ Banco de Dados", expanded=False):
    db_size = runner.get_db_size_kb()
    leads_all = runner.load_leads()
    stats = runner.get_stats()

    bc1, bc2, bc3 = st.columns(3)
    bc1.metric("Uso do banco", f"{db_size} KB")
    bc2.metric("Total de leads", stats["total_leads"])
    bc3.metric("Total de buscas", stats["total_searches"])

    st.markdown("---")
    ba1, ba2, ba3 = st.columns(3)

    with ba1:
        if confirm_dialog("clear_db", "🗑️ Limpar todos os leads", "⚠️ Sim, apagar tudo"):
            runner.clear_all_leads()
            show_toast("Banco de leads limpo.", "success")
            st.rerun()

    with ba2:
        # Backup — export everything as JSON
        if leads_all:
            backup_json = json.dumps(
                {"leads": leads_all, "history": runner.load_history()},
                ensure_ascii=False, indent=2, default=str
            ).encode("utf-8")
            st.download_button(
                "📤 Fazer Backup (JSON)",
                data=backup_json,
                file_name="health_leads_backup.json",
                mime="application/json",
                use_container_width=True,
            )
        else:
            st.button("📤 Fazer Backup", disabled=True, use_container_width=True)

    with ba3:
        uploaded = st.file_uploader(
            "📥 Importar backup",
            type=["json"],
            key="backup_upload",
            label_visibility="collapsed",
            help="Selecione um arquivo de backup JSON para importar leads.",
        )
        if uploaded is not None:
            try:
                backup_data = json.load(uploaded)
                imported_leads = backup_data.get("leads", [])
                if imported_leads:
                    saved = runner.save_leads(
                        imported_leads,
                        {"especialidade": "importado", "cidade": "backup", "estado": ""},
                    )
                    show_toast(f"{saved} leads importados com sucesso!", "success")
                    st.rerun()
                else:
                    st.error("Nenhum lead encontrado no arquivo.")
            except Exception as exc:
                st.error(f"Erro ao importar: {exc}")

# ══════════════════════════════════════════════════════════════════════════ #
#  Salvar configurações                                                      #
# ══════════════════════════════════════════════════════════════════════════ #
st.divider()
if st.button("💾 Salvar Configurações", type="primary", use_container_width=False):
    new_settings = {
        "request_delay_min": delay_min,
        "request_delay_max": max(delay_min, delay_max),
        "max_pages_default": max_pag,
        "headless_default": headless_def,
        "min_score_default": min_score_def,
        "csv_separator": csv_sep,
        "output_dir": output_dir.strip() or "output",
        "custom_palavras_clinica": [
            w.strip() for w in clinica_text.splitlines() if w.strip()
        ],
        "custom_titulos_profissional": [
            w.strip() for w in titulos_text.splitlines() if w.strip()
        ],
    }
    runner.save_settings(new_settings)
    show_toast("Configurações salvas com sucesso!", "success")

st.caption(
    "ℹ️ As configurações de delay e headless entram em vigor na próxima extração. "
    "Edite o arquivo `.env` para sobrescrever via variável de ambiente."
)
