"""Página de Nova Busca — formulário, extração em tempo real e resultados."""

import queue
import sys
import threading
import time
from pathlib import Path

import streamlit as st

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config import ESPECIALIDADES_SLUGS  # noqa: E402
from ui.extraction_runner import ExtractionRunner  # noqa: E402
from ui.components import render_score_badge, show_toast  # noqa: E402

# ── Constantes ────────────────────────────────────────────────────────────── #
_ESTADOS = [
    "AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG","PA",
    "PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO",
]
_ESPECIALIDADES = sorted(ESPECIALIDADES_SLUGS.keys())

# ── Inicialização do session_state ────────────────────────────────────────── #
_DEFAULTS = {
    "extraction_state": "idle",    # idle | running | done | error
    "extraction_thread": None,
    "progress_queue": None,
    "result_queue": None,
    "stop_event": None,
    "extraction_runner": None,
    "extraction_result": None,
    "extraction_params": {},
    "leads_found": 0,
    "discarded_found": 0,
    "last_message": "",
    "extraction_start": 0.0,
    "leads_saved": 0,
    "balloons_shown": False,
    "error_message": "",
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── Sidebar ───────────────────────────────────────────────────────────────── #
with st.sidebar:
    st.markdown("### 🔍 Nova Busca")
    st.page_link("app.py", label="← Voltar ao Início")

# ═══════════════════════════════════════════════════════════════════════════ #
#  ESTADO: idle — exibe formulário                                            #
# ═══════════════════════════════════════════════════════════════════════════ #
if st.session_state.extraction_state == "idle":
    st.header("🔍 Nova Extração de Leads")

    col_form, col_tips = st.columns([1, 1])

    with col_form:
        with st.form("extraction_form", border=True):
            especialidade = st.selectbox(
                "Especialidade *",
                options=_ESPECIALIDADES,
                index=0,
            )
            cidade = st.text_input(
                "Cidade *",
                placeholder="Ex: Nova Serrana",
            )
            estado = st.selectbox("Estado", options=_ESTADOS, index=_ESTADOS.index("MG"))
            max_paginas = st.slider("Máximo de páginas", 1, 20, 5)
            min_score = st.slider("Score mínimo", 0, 100, 0)

            st.markdown("##### Filtros adicionais")
            apenas_fone = st.checkbox("Apenas leads com telefone")
            apenas_aval = st.checkbox("Apenas profissionais com avaliações")
            debug_mode = st.checkbox("Modo debug (browser visível)", value=False)

            submitted = st.form_submit_button(
                "🚀 Iniciar Extração",
                use_container_width=True,
                type="primary",
            )

        if submitted:
            if not cidade.strip():
                st.error("Por favor, informe a cidade.")
            else:
                pq: queue.Queue = queue.Queue()
                rq: queue.Queue = queue.Queue()
                stop = threading.Event()
                runner = ExtractionRunner()

                thread = runner.run_extraction(
                    especialidade=especialidade,
                    cidade=cidade.strip(),
                    estado=estado,
                    max_paginas=max_paginas,
                    min_score=min_score,
                    progress_queue=pq,
                    result_queue=rq,
                    stop_event=stop,
                    headless=not debug_mode,
                )

                st.session_state.extraction_state = "running"
                st.session_state.extraction_thread = thread
                st.session_state.progress_queue = pq
                st.session_state.result_queue = rq
                st.session_state.stop_event = stop
                st.session_state.extraction_runner = runner
                st.session_state.leads_found = 0
                st.session_state.discarded_found = 0
                st.session_state.last_message = "Iniciando…"
                st.session_state.extraction_start = time.time()
                st.session_state.balloons_shown = False
                st.session_state.extraction_params = {
                    "especialidade": especialidade,
                    "cidade": cidade.strip(),
                    "estado": estado,
                    "apenas_fone": apenas_fone,
                    "apenas_aval": apenas_aval,
                }
                st.rerun()

    with col_tips:
        st.markdown("### 💡 Dicas de Uso")
        with st.container(border=True):
            st.markdown("""
**Comece com cidades menores** para testar e calibrar os filtros antes de buscas maiores.

**Score de qualidade** varia de 0 a 100:
- 🔥 **Quente (80+)** — tem fone + sem site + CRM verificado
- ⭐ **Qualificado (60–79)** — perfil completo
- 👀 **Morno (40–59)** — dados parciais
- ❄️ **Frio (<40)** — pouco dados

**Estimativa de tempo:**
| Páginas | Leads estimados | Tempo |
|---------|----------------|-------|
| 1–2 | 5–20 | ~1 min |
| 5 | 30–60 | ~3 min |
| 10 | 60–120 | ~6 min |
| 20 | 120–200 | ~12 min |

**Dica:** Use **Modo debug** para ver o browser em ação e diagnosticar captchas.
            """)

# ═══════════════════════════════════════════════════════════════════════════ #
#  ESTADO: running — mostra progresso em tempo real                           #
# ═══════════════════════════════════════════════════════════════════════════ #
elif st.session_state.extraction_state == "running":
    st.header("⏳ Extração em Andamento…")

    pq: queue.Queue = st.session_state.progress_queue
    rq: queue.Queue = st.session_state.result_queue
    thread: threading.Thread = st.session_state.extraction_thread

    # Drain progress queue
    while not pq.empty():
        try:
            msg = pq.get_nowait()
            mtype = msg.get("type")
            if mtype == "progress":
                st.session_state.leads_found = msg.get("leads_found", st.session_state.leads_found)
                st.session_state.last_message = msg.get("message", st.session_state.last_message)
            elif mtype == "status":
                st.session_state.last_message = msg.get("message", st.session_state.last_message)
            elif mtype == "error":
                st.session_state.extraction_state = "error"
                st.session_state.error_message = msg.get("message", "Erro desconhecido.")
        except queue.Empty:
            break

    # Check for result
    if not rq.empty():
        try:
            result = rq.get_nowait()
            if result.get("error"):
                st.session_state.extraction_state = "error"
                st.session_state.error_message = result["error"]
            else:
                # Save to database
                runner: ExtractionRunner = st.session_state.extraction_runner
                saved = runner.save_leads(
                    result["leads"],
                    {
                        **st.session_state.extraction_params,
                        "elapsed": result.get("elapsed", 0),
                        "total_discarded": len(result.get("discarded", [])),
                    },
                )
                st.session_state.leads_saved = saved
                st.session_state.extraction_result = result
                st.session_state.extraction_state = "done"
        except queue.Empty:
            pass

    # Thread died without sending result
    if (
        st.session_state.extraction_state == "running"
        and thread is not None
        and not thread.is_alive()
        and rq.empty()
    ):
        st.session_state.extraction_state = "error"
        st.session_state.error_message = (
            "A thread de extração encerrou inesperadamente. "
            "Verifique o log em output/scraper.log."
        )

    if st.session_state.extraction_state in ("done", "error"):
        st.rerun()

    # ── Progress UI ─────────────────────────────────────────────────────── #
    elapsed = time.time() - st.session_state.extraction_start
    params = st.session_state.extraction_params

    st.markdown(
        f"**Buscando:** {params.get('especialidade','?')} em "
        f"{params.get('cidade','?')} — {params.get('estado','?')}"
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Leads Encontrados", st.session_state.leads_found)
    c2.metric("Tempo Decorrido", f"{elapsed:.0f}s")
    c3.metric("Status", "🟢 Ativo")

    st.progress(0.5, text="Extração em progresso…")

    st.markdown(f"**Última ação:** `{st.session_state.last_message}`")

    if st.button("⏹ Parar Extração", type="primary"):
        st.session_state.stop_event.set()
        show_toast("Aguardando parada segura…", "warning")
        st.session_state.extraction_state = "idle"
        st.rerun()

    # Auto-refresh every 0.6 s while running
    time.sleep(0.6)
    st.rerun()

# ═══════════════════════════════════════════════════════════════════════════ #
#  ESTADO: done — mostra resultados                                           #
# ═══════════════════════════════════════════════════════════════════════════ #
elif st.session_state.extraction_state == "done":
    result = st.session_state.extraction_result or {}
    leads = result.get("leads", [])
    discarded = result.get("discarded", [])
    elapsed = result.get("elapsed", 0)

    if not st.session_state.balloons_shown:
        st.balloons()
        st.session_state.balloons_shown = True

    mins, secs = divmod(int(elapsed), 60)
    time_str = f"{mins}m {secs}s" if mins else f"{secs}s"

    st.success(
        f"✅ Extração concluída! "
        f"**{len(leads)}** leads aprovados em **{time_str}** "
        f"({st.session_state.leads_saved} novos no banco)"
    )

    hot = sum(1 for l in leads if l.get("score_qualidade", 0) >= 80)
    qualified = sum(1 for l in leads if 60 <= l.get("score_qualidade", 0) < 80)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total encontrado", len(leads) + len(discarded))
    c2.metric("Profissionais", len(leads), f"+{st.session_state.leads_saved} novos")
    c3.metric("Clínicas descartadas", len(discarded))
    c4.metric("🔥 Leads Quentes", hot)
    c5.metric("⭐ Qualificados", qualified)

    st.divider()
    col_a, col_b, col_c, col_d = st.columns(4)

    with col_a:
        if st.button("📊 Ver no Dashboard", type="primary", use_container_width=True):
            st.switch_page("pages/2_📊_Dashboard.py")
    with col_b:
        if st.button("🔄 Nova Busca", use_container_width=True):
            for k in _DEFAULTS:
                st.session_state[k] = _DEFAULTS[k]
            st.rerun()
    with col_c:
        if leads:
            import pandas as pd
            df = pd.DataFrame(leads)
            esp = result.get("especialidade", "leads")
            cidade_slug = result.get("cidade", "resultado").replace(" ", "_").lower()
            csv_bytes = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
            st.download_button(
                "⬇️ CSV",
                data=csv_bytes,
                file_name=f"{esp}_{cidade_slug}.csv",
                mime="text/csv",
                use_container_width=True,
            )
    with col_d:
        if leads:
            from exporters.excel_exporter import ExcelExporter
            from exporters.csv_exporter import HEADERS_PT, _format_value
            from models.lead import Lead as _Lead
            import io, openpyxl
            # Quick in-memory preview of top leads
            top = sorted(leads, key=lambda x: x.get("score_qualidade", 0), reverse=True)[:5]
            if top:
                st.markdown("**Top 5 leads desta busca:**")
                for lead in top:
                    score = lead.get("score_qualidade", 0)
                    st.markdown(
                        f"- {render_score_badge(score)} **{lead.get('nome','?')}** — "
                        f"{lead.get('cidade','?')} — 📞 {lead.get('telefone_1') or '—'}",
                        unsafe_allow_html=True,
                    )

# ═══════════════════════════════════════════════════════════════════════════ #
#  ESTADO: error                                                              #
# ═══════════════════════════════════════════════════════════════════════════ #
elif st.session_state.extraction_state == "error":
    st.header("❌ Erro na Extração")
    st.error(st.session_state.error_message)
    st.markdown("""
**Possíveis causas e soluções:**
- 🌐 **Sem conexão** — verifique a internet
- 🔒 **Captcha / bloqueio** — aguarde alguns minutos e tente novamente
- 🏙️ **Cidade não encontrada** — verifique a grafia (ex: "Belo Horizonte", não "BH")
- 🔧 **Playwright não instalado** — rode `playwright install chromium`

Verifique o log completo em `output/scraper.log`.
    """)
    if st.button("↩️ Tentar Novamente", type="primary"):
        for k in _DEFAULTS:
            st.session_state[k] = _DEFAULTS[k]
        st.rerun()
