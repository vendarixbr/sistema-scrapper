"""Dashboard — tabela interativa, filtros e gráficos de análise."""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ui.extraction_runner import ExtractionRunner  # noqa: E402
from ui.components import (  # noqa: E402
    render_empty_state,
    render_metric_cards,
    render_score_badge,
    show_toast,
    confirm_dialog,
)

# ── AgGrid (opcional) ─────────────────────────────────────────────────────── #
try:
    from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode
    _HAS_AGGRID = True
except ImportError:
    _HAS_AGGRID = False

# ── Sidebar ───────────────────────────────────────────────────────────────── #
with st.sidebar:
    st.markdown("### 📊 Dashboard")
    st.page_link("app.py", label="← Início")
    st.page_link("pages/1_🔍_Nova_Busca.py", label="🔍 Nova Busca")


def _load_df(runner: ExtractionRunner, filters: dict) -> pd.DataFrame:
    leads = runner.load_leads(filters)
    if not leads:
        return pd.DataFrame()
    df = pd.DataFrame(leads)
    # Ensure all expected columns exist
    for col in ["score_qualidade", "score_label", "nome", "especialidade", "cidade",
                "estado", "crm", "telefone_1", "whatsapp", "avaliacao_nota",
                "avaliacao_quantidade", "planos_saude", "servicos",
                "tem_site", "instagram", "doctoralia_url", "bairro", "id"]:
        if col not in df.columns:
            df[col] = None
    df["planos_count"] = df["planos_saude"].apply(
        lambda x: len(x) if isinstance(x, list) else 0
    )
    df["tem_fone"] = df["telefone_1"].notna() & (df["telefone_1"] != "")
    return df


# ── Main ──────────────────────────────────────────────────────────────────── #
st.header("📊 Dashboard de Leads")

runner = ExtractionRunner()

# ── Filtros ───────────────────────────────────────────────────────────────── #
all_leads_raw = runner.load_leads()
if not all_leads_raw:
    render_empty_state("Nenhum lead no banco. Faça uma busca primeiro!")
    st.stop()

all_df_base = pd.DataFrame(all_leads_raw)
all_especialidades = sorted(all_df_base["especialidade"].dropna().unique().tolist()) if "especialidade" in all_df_base.columns else []
all_cidades = sorted(all_df_base["cidade"].dropna().unique().tolist()) if "cidade" in all_df_base.columns else []

with st.expander("🔧 Filtros", expanded=True):
    fc1, fc2, fc3, fc4, fc5 = st.columns([2, 2, 1, 1, 1])
    with fc1:
        sel_esp = st.multiselect("Especialidade", all_especialidades, placeholder="Todas")
    with fc2:
        sel_cid = st.multiselect("Cidade", all_cidades, placeholder="Todas")
    with fc3:
        sel_score = st.slider("Score mínimo", 0, 100, 0)
    with fc4:
        apenas_sem_site = st.toggle("Só sem site 🌐")
        apenas_com_fone = st.toggle("Só com fone 📞")
    with fc5:
        nome_busca = st.text_input("Buscar por nome", placeholder="Dr. João…")
        if st.button("🗑️ Limpar filtros", use_container_width=True):
            st.rerun()

active_filters = {
    "especialidades": sel_esp or None,
    "cidades": sel_cid or None,
    "score_min": sel_score if sel_score > 0 else None,
    "apenas_sem_site": apenas_sem_site,
    "apenas_com_telefone": apenas_com_fone,
    "nome_busca": nome_busca,
}

df = _load_df(runner, {k: v for k, v in active_filters.items() if v})

if df.empty:
    render_empty_state("Nenhum lead corresponde aos filtros aplicados.")
    st.stop()

# ── Métricas ──────────────────────────────────────────────────────────────── #
total = len(df)
hot = int((df["score_qualidade"] >= 80).sum())
with_phone = int(df["tem_fone"].sum()) if "tem_fone" in df.columns else 0
without_site = int((~df["tem_site"].fillna(False)).sum()) if "tem_site" in df.columns else 0

render_metric_cards(total, hot, with_phone, without_site)

c_avg, c_crm, c_plans = st.columns(3)
avg_score = df["score_qualidade"].mean() if "score_qualidade" in df.columns else 0
c_avg.metric("Score Médio", f"{avg_score:.1f}")
crm_count = df["crm"].notna().sum() if "crm" in df.columns else 0
c_crm.metric("Com CRM Verificado", int(crm_count))
avg_plans = df["planos_count"].mean() if "planos_count" in df.columns else 0
c_plans.metric("Média Planos de Saúde", f"{avg_plans:.1f}")

st.divider()

# ── Tabela ────────────────────────────────────────────────────────────────── #
_DISPLAY_COLS = {
    "score_qualidade": "Score",
    "score_label": "Classificação",
    "nome": "Nome",
    "especialidade": "Especialidade",
    "cidade": "Cidade",
    "estado": "UF",
    "crm": "CRM",
    "telefone_1": "Telefone",
    "avaliacao_nota": "Nota",
    "avaliacao_quantidade": "Avaliações",
    "planos_count": "Nº Planos",
    "tem_site": "Tem Site",
    "instagram": "Instagram",
    "doctoralia_url": "URL Doctoralia",
}

available_display = {k: v for k, v in _DISPLAY_COLS.items() if k in df.columns}
df_show = df[list(available_display.keys())].rename(columns=available_display)
df_show["Tem Site"] = df_show["Tem Site"].apply(lambda x: "✅" if x else "❌") if "Tem Site" in df_show.columns else df_show.get("Tem Site", "—")

if _HAS_AGGRID:
    gb = GridOptionsBuilder.from_dataframe(df_show)
    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=25)
    gb.configure_selection("multiple", use_checkbox=True, groupSelectsChildren=False)
    gb.configure_default_column(resizable=True, filterable=True, sortable=True)
    if "Score" in df_show.columns:
        gb.configure_column("Score", width=80)
    if "URL Doctoralia" in df_show.columns:
        gb.configure_column("URL Doctoralia", hide=True)
    grid_opts = gb.build()

    grid_response = AgGrid(
        df_show,
        gridOptions=grid_opts,
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        fit_columns_on_grid_load=False,
        theme="alpine",
        enable_enterprise_modules=False,
        height=420,
        width="100%",
        reload_data=False,
    )
    selected_rows = grid_response.get("selected_rows", [])
    selected_df = pd.DataFrame(selected_rows) if selected_rows else pd.DataFrame()
else:
    st.info("💡 Instale `streamlit-aggrid==0.3.4` para tabela avançada com filtros por coluna e seleção múltipla.")
    st.dataframe(df_show, use_container_width=True, hide_index=True, height=400)
    selected_df = pd.DataFrame()

# ── Ações em lote ─────────────────────────────────────────────────────────── #
if not selected_df.empty:
    st.markdown(f"**{len(selected_df)} lead(s) selecionado(s):**")
    ba1, ba2, ba3 = st.columns(3)
    with ba1:
        csv_sel = selected_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button("⬇️ Exportar selecionados (CSV)", csv_sel, "selecionados.csv", "text/csv")
    with ba2:
        if "Telefone" in selected_df.columns:
            phones = ", ".join(selected_df["Telefone"].dropna().tolist())
            st.text_area("📞 Telefones", phones, height=80)
    with ba3:
        # Delete selected — need IDs from original df
        if confirm_dialog("delete_selected", "🗑️ Deletar selecionados"):
            if "Nome" in selected_df.columns and "id" in df.columns:
                sel_names = set(selected_df["Nome"].tolist())
                ids_to_del = df[df["nome"].isin(sel_names)]["id"].tolist()
                deleted = runner.delete_leads(ids_to_del)
                show_toast(f"{deleted} lead(s) deletado(s).", "success")
                st.rerun()

st.divider()

# ── Exportação global ─────────────────────────────────────────────────────── #
st.markdown("##### 📤 Exportar todos os leads filtrados")
exp1, exp2 = st.columns(2)
with exp1:
    csv_all = df_show.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button("⬇️ CSV completo", csv_all, "leads_filtrados.csv", "text/csv", use_container_width=True)
with exp2:
    try:
        import io, openpyxl
        from exporters.excel_exporter import ExcelExporter
        from pathlib import Path as _P
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = tmp.name
        ExcelExporter().save(
            [type("L", (), lead)() for lead in runner.load_leads({k: v for k, v in active_filters.items() if v})],
            filename=tmp_path.replace(".xlsx", ""),
        )
        if _P(tmp_path).exists():
            xlsx_bytes = _P(tmp_path).read_bytes()
            os.unlink(tmp_path)
            st.download_button("⬇️ Excel (.xlsx)", xlsx_bytes, "leads_filtrados.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               use_container_width=True)
    except Exception:
        # Simpler fallback: export the displayed dataframe directly via openpyxl
        import io, openpyxl
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df_show.to_excel(writer, index=False, sheet_name="Leads")
        st.download_button("⬇️ Excel (.xlsx)", buf.getvalue(), "leads_filtrados.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)

st.divider()

# ── Gráficos ──────────────────────────────────────────────────────────────── #
import plotly.express as px
import plotly.graph_objects as go

st.markdown("### 📈 Análises")
tab_dist, tab_cidades, tab_qualidade = st.tabs(
    ["📊 Distribuição", "🏙️ Cidades", "🎯 Qualidade"]
)

with tab_dist:
    gc1, gc2 = st.columns(2)
    with gc1:
        if "especialidade" in df.columns:
            esp_counts = df["especialidade"].value_counts().reset_index()
            esp_counts.columns = ["Especialidade", "Quantidade"]
            fig = px.pie(esp_counts, names="Especialidade", values="Quantidade",
                         title="Leads por Especialidade", color_discrete_sequence=px.colors.sequential.Teal)
            st.plotly_chart(fig, use_container_width=True)
    with gc2:
        label_map = {
            "🔥 Lead Quente": "Quente (80+)",
            "⭐ Lead Qualificado": "Qualificado (60–79)",
            "👀 Lead Morno": "Morno (40–59)",
            "❄️ Lead Frio": "Frio (<40)",
        }
        if "score_label" in df.columns:
            score_dist = df["score_label"].value_counts().reset_index()
            score_dist.columns = ["Categoria", "Quantidade"]
            score_dist["Categoria"] = score_dist["Categoria"].map(label_map).fillna(score_dist["Categoria"])
            colors = ["#FF6B35", "#FFC107", "#64B5F6", "#90A4AE"]
            fig2 = px.pie(score_dist, names="Categoria", values="Quantidade",
                          title="Distribuição por Score",
                          color_discrete_sequence=colors)
            st.plotly_chart(fig2, use_container_width=True)

with tab_cidades:
    gc3, gc4 = st.columns(2)
    with gc3:
        if "cidade" in df.columns:
            top_cities = df["cidade"].value_counts().head(10).reset_index()
            top_cities.columns = ["Cidade", "Total"]
            fig3 = px.bar(top_cities, x="Total", y="Cidade", orientation="h",
                          title="Top 10 Cidades — Total de Leads",
                          color="Total", color_continuous_scale="Teal")
            fig3.update_layout(yaxis={"autorange": "reversed"})
            st.plotly_chart(fig3, use_container_width=True)
    with gc4:
        if "cidade" in df.columns and "score_qualidade" in df.columns:
            hot_df = df[df["score_qualidade"] >= 80]
            if not hot_df.empty:
                top_hot = hot_df["cidade"].value_counts().head(10).reset_index()
                top_hot.columns = ["Cidade", "Leads Quentes"]
                fig4 = px.bar(top_hot, x="Leads Quentes", y="Cidade", orientation="h",
                              title="Top 10 Cidades — 🔥 Leads Quentes",
                              color="Leads Quentes", color_continuous_scale="Oranges")
                fig4.update_layout(yaxis={"autorange": "reversed"})
                st.plotly_chart(fig4, use_container_width=True)
            else:
                st.info("Nenhum lead quente nos filtros atuais.")

with tab_qualidade:
    gc5, gc6 = st.columns(2)
    with gc5:
        if "score_qualidade" in df.columns:
            fig5 = px.histogram(df, x="score_qualidade", nbins=20,
                                title="Histograma de Scores",
                                color_discrete_sequence=["#00897B"],
                                labels={"score_qualidade": "Score de Qualidade"})
            fig5.add_vline(x=60, line_dash="dash", line_color="#FFC107", annotation_text="Qualificado")
            fig5.add_vline(x=80, line_dash="dash", line_color="#FF6B35", annotation_text="Quente")
            st.plotly_chart(fig5, use_container_width=True)
    with gc6:
        if "avaliacao_nota" in df.columns and "score_qualidade" in df.columns:
            df_scatter = df[df["avaliacao_nota"] > 0].copy()
            if not df_scatter.empty:
                fig6 = px.scatter(
                    df_scatter,
                    x="avaliacao_nota",
                    y="score_qualidade",
                    color="score_qualidade",
                    color_continuous_scale="RdYlGn",
                    title="Nota Avaliação × Score de Qualidade",
                    labels={"avaliacao_nota": "Nota (Doctoralia)", "score_qualidade": "Score Qualidade"},
                    hover_data=["nome"] if "nome" in df_scatter.columns else None,
                )
                st.plotly_chart(fig6, use_container_width=True)
            else:
                st.info("Sem leads com avaliação nos filtros atuais.")
