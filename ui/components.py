"""Reusable Streamlit UI components for Health Lead Extractor."""

from typing import Optional
import streamlit as st


# ── Score helpers ────────────────────────────────────────────────────────── #

def score_class(score: int) -> str:
    """Return a CSS class name for the given score."""
    if score >= 80:
        return "hot"
    if score >= 60:
        return "qualified"
    if score >= 40:
        return "warm"
    return "cold"


def render_score_badge(score: int) -> str:
    """Return an HTML badge string for the given score value."""
    _cfg = {
        "hot":       ("#FF6B35", "white",  "🔥"),
        "qualified": ("#FFC107", "black",  "⭐"),
        "warm":      ("#64B5F6", "white",  "👀"),
        "cold":      ("#90A4AE", "white",  "❄️"),
    }
    bg, color, icon = _cfg[score_class(score)]
    return (
        f'<span style="background:{bg};color:{color};border-radius:12px;'
        f'padding:2px 10px;font-size:12px;font-weight:bold;white-space:nowrap">'
        f"{icon} {score}</span>"
    )


# ── Lead display ─────────────────────────────────────────────────────────── #

def render_lead_card(lead: dict) -> None:
    """Render a card for a single lead using st.markdown."""
    score = lead.get("score_qualidade", 0)
    badge = render_score_badge(score)
    crm_row = (
        f'<p style="margin:2px 0;font-size:13px">🏥 CRM: {lead["crm"]}</p>'
        if lead.get("crm") else ""
    )
    phone = lead.get("telefone_1") or "Não disponível"
    st.markdown(
        f"""
        <div style="border:1px solid #e0e0e0;border-radius:8px;
                    padding:14px 16px;margin:6px 0;background:white">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <h4 style="margin:0;font-size:15px">{lead.get("nome","—")}</h4>
            {badge}
          </div>
          <p style="color:#666;margin:4px 0;font-size:13px">
              {lead.get("especialidade","—")} · {lead.get("cidade","—")}/{lead.get("estado","—")}
          </p>
          <p style="margin:2px 0;font-size:13px">📞 {phone}</p>
          {crm_row}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Metric row ───────────────────────────────────────────────────────────── #

def render_metric_cards(
    total: int,
    hot: int,
    with_phone: int,
    without_site: int,
) -> None:
    """Display four key metrics in a single row."""
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total de Leads", total)
    c2.metric("🔥 Leads Quentes", hot)
    pct_phone = f"{with_phone / max(total, 1) * 100:.0f}%"
    c3.metric("📞 Com Telefone", with_phone, pct_phone)
    pct_site = f"{without_site / max(total, 1) * 100:.0f}%"
    c4.metric("🌐 Sem Site (oport.)", without_site, pct_site)


# ── Empty state ──────────────────────────────────────────────────────────── #

def render_empty_state(message: str = "Nenhum dado disponível ainda.") -> None:
    """Show a centred empty-state illustration."""
    st.markdown(
        f"""
        <div style="text-align:center;padding:60px 20px;color:#9e9e9e">
          <div style="font-size:52px">📭</div>
          <h3 style="color:#9e9e9e">{message}</h3>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Phone copy button ────────────────────────────────────────────────────── #

def render_phone_button(phone: Optional[str]) -> None:
    """Show a phone number with a JavaScript clipboard-copy button."""
    if not phone:
        st.markdown("—")
        return
    safe = phone.replace("'", "")
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:8px">
          <span style="font-family:monospace">{phone}</span>
          <button
            onclick="navigator.clipboard.writeText('{safe}')
                     .then(()=>{{this.innerText='✅ Copiado!';
                                setTimeout(()=>this.innerText='📋 Copiar',1500)}})
                     .catch(()=>{{}})"
            style="border:1px solid #ccc;background:#f5f5f5;border-radius:4px;
                   padding:2px 8px;cursor:pointer;font-size:12px">
            📋 Copiar
          </button>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Toast notification ───────────────────────────────────────────────────── #

def show_toast(message: str, kind: str = "success") -> None:
    """Show a brief Streamlit toast (1.29+) or fall back to st.info/success/error."""
    icons = {"success": "✅", "error": "❌", "warning": "⚠️", "info": "ℹ️"}
    try:
        st.toast(message, icon=icons.get(kind, "ℹ️"))
    except AttributeError:
        getattr(st, kind, st.info)(message)


# ── Two-step confirm dialog ──────────────────────────────────────────────── #

def confirm_dialog(key: str, label: str, danger_label: str = "✅ Confirmar") -> bool:
    """
    Two-click confirmation widget.
    Returns True only after the user confirms on the second click.
    """
    flag_key = f"_confirm_pending_{key}"

    if st.session_state.get(flag_key):
        col_yes, col_no, _ = st.columns([1, 1, 3])
        with col_yes:
            confirmed = st.button(danger_label, key=f"_confirm_yes_{key}", type="primary")
        with col_no:
            if st.button("Cancelar", key=f"_confirm_no_{key}"):
                st.session_state[flag_key] = False
                st.rerun()
        if confirmed:
            st.session_state[flag_key] = False
            return True
    else:
        if st.button(label, key=f"_confirm_start_{key}"):
            st.session_state[flag_key] = True
            st.rerun()

    return False
