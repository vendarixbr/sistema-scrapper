"""Histórico de buscas realizadas."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ui.extraction_runner import ExtractionRunner  # noqa: E402
from ui.components import render_empty_state, show_toast, confirm_dialog  # noqa: E402

with st.sidebar:
    st.markdown("### 📋 Histórico")
    st.page_link("app.py", label="← Início")
    st.page_link("pages/1_🔍_Nova_Busca.py", label="🔍 Nova Busca")

st.header("📋 Histórico de Buscas")

runner = ExtractionRunner()
history = runner.load_history()

if not history:
    render_empty_state("Nenhuma busca realizada ainda.")
    if st.button("🔍 Fazer Primeira Busca", type="primary"):
        st.switch_page("pages/1_🔍_Nova_Busca.py")
    st.stop()

# ── Filtros ───────────────────────────────────────────────────────────────── #
all_esp = sorted({s.get("especialidade", "") for s in history if s.get("especialidade")})
fc1, fc2, fc3 = st.columns([2, 2, 2])
with fc1:
    filter_esp = st.multiselect("Filtrar por especialidade", all_esp, placeholder="Todas")
with fc2:
    period = st.selectbox("Período", ["Todos", "Hoje", "Últimos 7 dias", "Últimos 30 dias"])
with fc3:
    st.markdown(" ")  # spacing

# ── Aplicar filtros ───────────────────────────────────────────────────────── #
now = datetime.now()
_PERIOD_DELTA = {
    "Hoje": timedelta(days=1),
    "Últimos 7 dias": timedelta(days=7),
    "Últimos 30 dias": timedelta(days=30),
}
filtered = list(reversed(history))  # Most recent first

if filter_esp:
    filtered = [s for s in filtered if s.get("especialidade") in filter_esp]

if period != "Todos":
    cutoff = now - _PERIOD_DELTA[period]
    filtered = [
        s for s in filtered
        if datetime.fromisoformat(s["timestamp"]) >= cutoff
    ]

# ── Estatísticas do histórico ─────────────────────────────────────────────── #
if history:
    total_leads_all = sum(s.get("total_leads", 0) for s in history)
    esp_counts: dict[str, int] = {}
    city_leads: dict[str, int] = {}
    for s in history:
        esp = s.get("especialidade", "?")
        esp_counts[esp] = esp_counts.get(esp, 0) + 1
        city = s.get("cidade", "?")
        city_leads[city] = city_leads.get(city, 0) + s.get("total_leads", 0)

    top_esp = max(esp_counts, key=esp_counts.get, default="—")
    top_city = max(city_leads, key=city_leads.get, default="—")

    sc1, sc2, sc3, sc4 = st.columns(4)
    sc1.metric("Total de Buscas", len(history))
    sc2.metric("Total de Leads (acum.)", total_leads_all)
    sc3.metric("Especialidade mais buscada", top_esp)
    sc4.metric("Cidade com mais leads", top_city)
    st.divider()

# ── Lista de buscas ───────────────────────────────────────────────────────── #
if not filtered:
    render_empty_state("Nenhuma busca encontrada para os filtros selecionados.")
    st.stop()

st.markdown(f"**{len(filtered)} busca(s) encontrada(s)**")

for search in filtered:
    sid = search.get("id", "")
    ts_str = search.get("timestamp", "")
    try:
        ts = datetime.fromisoformat(ts_str)
        ts_display = ts.strftime("%d/%m/%Y às %H:%M")
    except Exception:
        ts_display = ts_str

    esp = search.get("especialidade", "—")
    cidade = search.get("cidade", "—")
    estado = search.get("estado", "—")
    total = search.get("total_leads", 0)
    discarded = search.get("total_discarded", 0)
    elapsed = search.get("elapsed_seconds", 0)
    mins, secs = divmod(int(elapsed), 60)
    elapsed_str = f"{mins}m {secs}s" if mins else f"{secs}s"

    with st.container(border=True):
        hc1, hc2, hc3 = st.columns([3, 2, 2])
        with hc1:
            st.markdown(
                f"**{esp.capitalize()}** em **{cidade} — {estado}**  \n"
                f"🕐 {ts_display} · ⏱ {elapsed_str}"
            )
        with hc2:
            st.metric("Leads aprovados", total, f"-{discarded} clínicas")
        with hc3:
            ba, bb, bc = st.columns(3)
            with ba:
                if st.button("📂", key=f"load_{sid}", help="Carregar no Dashboard"):
                    st.switch_page("pages/2_📊_Dashboard.py")
            with bb:
                # Export leads from this search by timestamp
                leads = runner.load_leads()
                search_leads = [
                    l for l in leads
                    if l.get("especialidade") == esp and l.get("cidade") == cidade
                ]
                if search_leads:
                    df_exp = pd.DataFrame(search_leads)
                    csv_bytes = df_exp.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
                    st.download_button(
                        "⬇️",
                        data=csv_bytes,
                        file_name=f"{esp}_{cidade}.csv",
                        mime="text/csv",
                        key=f"dl_{sid}",
                        help="Exportar esta busca",
                    )
            with bc:
                if confirm_dialog(f"del_{sid}", "🗑️", "⚠️ Sim, deletar"):
                    runner.delete_search(sid)
                    show_toast("Busca removida do histórico.", "success")
                    st.rerun()
