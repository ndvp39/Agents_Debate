"""Standalone HTML debate viewer — markdown rendering + polished visual design."""

import html as _h
import re

_PRO_ID = "Agent_Pro"
_CON_ID = "Agent_Con"

_VERDICT_SECTIONS = [
    ("KEY CLASHES",        "⚔️",  "vc-clashes",    "#38bdf8"),
    ("FEEDBACK ADHERENCE", "📋",  "vc-feedback",   "#c084fc"),
    ("SCORING BREAKDOWN",  "📊",  "vc-scoring",    "#fb923c"),
    ("FINAL CONCLUSION",   "🏆",  "vc-conclusion", "#4ade80"),
]

# ---------------------------------------------------------------------------
# Markdown → HTML helpers
# ---------------------------------------------------------------------------

def _inline(text: str) -> str:
    """Apply bold/italic to already-HTML-escaped text."""
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text, flags=re.DOTALL)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', text, flags=re.DOTALL)
    return text


def _md(raw: str) -> str:
    """Convert basic markdown to HTML (escape → block → inline)."""
    blocks = re.split(r'\n{2,}', raw.strip())
    # Remove horizontal rule blocks
    blocks = [b for b in blocks if b.strip() not in ('---', '***', '___')]
    out = []
    for block in blocks:
        lines = block.split('\n')
        # Heading
        if len(lines) == 1 and re.match(r'^#{1,3} ', lines[0]):
            lvl = len(re.match(r'^(#{1,3}) ', lines[0]).group(1))
            content = _inline(_h.escape(lines[0].lstrip('#').strip()))
            out.append(f'<h{lvl} class="md-h">{content}</h{lvl}>')
            continue
        # List block (all non-empty lines start with `- ` or `* `)
        list_lines = [l for l in lines if l.strip()]
        if list_lines and all(re.match(r'^\s*[*-] ', l) for l in list_lines):
            strip_bullet = lambda l: re.sub(r'^\s*[*-] ', '', l)
            items = ''.join(
                f'<li>{_inline(_h.escape(strip_bullet(l)))}</li>'
                for l in list_lines
            )
            out.append(f'<ul class="md-ul">{items}</ul>')
            continue
        # Paragraph: join lines with <br>, apply inline formatting
        parts = [_inline(_h.escape(l)) for l in lines]
        out.append('<p>' + '<br>'.join(parts) + '</p>')
    return '\n'.join(out)


# ---------------------------------------------------------------------------
# Verdict section parser
# ---------------------------------------------------------------------------

def _parse_verdict(justification: str) -> list[tuple[str, str]]:
    """Split justification into [(section_name, body_text), …]."""
    names = [s[0] for s in _VERDICT_SECTIONS]
    pattern = '(' + '|'.join(re.escape(n) for n in names) + ')'
    parts = re.split(pattern, justification)
    result, i = [], 0
    preamble = parts[0].strip()
    if preamble:
        result.append(("", preamble))
    i = 1
    while i + 1 < len(parts):
        body = re.sub(r'^[\s:\-–—]+', '', parts[i + 1]).strip()
        result.append((parts[i], body))
        i += 2
    return result


# ---------------------------------------------------------------------------
# HTML component builders
# ---------------------------------------------------------------------------

def _round_header(n: int) -> str:
    return (
        f'<div class="round-header">'
        f'<div class="round-badge">Round {n}</div>'
        f'</div>'
    )


def _bubble(msg: dict) -> str:
    agent = msg.get("agent_id", "?")
    rnd   = msg.get("round", "?")
    side  = "pro" if agent == _PRO_ID else "con"
    label = f"Round {rnd} · {'FOR' if agent == _PRO_ID else 'AGAINST'}"
    body  = _md(msg.get("argument", ""))
    cits  = msg.get("citations", [])
    cite_html = ""
    if cits:
        items = "".join(f"<li>{_h.escape(c)}</li>" for c in cits)
        cite_html = f'<div class="citations"><span>Citations</span><ul>{items}</ul></div>'
    return (
        f'<div class="turn {side}">'
        f'<div class="avatar {side}">{agent[6].upper()}</div>'
        f'<div class="bubble {side}">'
        f'<div class="bubble-header">{_h.escape(label)}</div>'
        f'<div class="bubble-body">{body}{cite_html}</div>'
        f'</div></div>'
    )


def _judge_card(msg: dict, is_reprimand: bool = False) -> str:
    target = _h.escape(msg.get("target_agent", "?"))
    extra  = " reprimand" if is_reprimand else ""
    if is_reprimand:
        label = f"⚠ Reprimand → {target}"
        body  = _md(msg.get("prompt_for_next", ""))
    else:
        label    = f"Judge → {target}"
        feedback = _md(msg.get("judge_feedback", ""))
        prompt   = _md(msg.get("prompt_for_next", ""))
        body     = f'{feedback}<div class="j-prompt">{prompt}</div>'
    return (
        f'<div class="judge-wrap">'
        f'<div class="judge-card{extra}">'
        f'<div class="j-label">{label}</div>'
        f'<div class="j-feedback">{body}</div>'
        f'</div></div>'
    )


def _score_section(scores: dict) -> str:
    pro = scores.get(_PRO_ID, 0)
    con = scores.get(_CON_ID, 0)
    return (
        '<div class="scores-section">'
        '<div class="section-title">Final Scores</div>'
        '<div class="score-display">'
        f'<div class="score-num pro"><div class="num">{pro}</div><div class="label">Agent Pro</div></div>'
        '<div class="score-vs">vs</div>'
        f'<div class="score-num con"><div class="num">{con}</div><div class="label">Agent Con</div></div>'
        '</div>'
        '<div class="bar-area">'
        f'<div class="bar-row"><div class="bar-label">Agent Pro</div>'
        f'<div class="bar-track"><div class="bar-fill pro" style="width:{pro}%">{pro}%</div></div></div>'
        f'<div class="bar-row"><div class="bar-label">Agent Con</div>'
        f'<div class="bar-track"><div class="bar-fill con" style="width:{con}%">{con}%</div></div></div>'
        '</div></div>'
    )


def _verdict_block(verdict: dict) -> str:
    winner    = _h.escape(verdict.get("winner", "?"))
    just      = verdict.get("justification", "")
    sections  = _parse_verdict(just)
    sec_map   = {s[0]: s for s in _VERDICT_SECTIONS}

    cards = []
    for name, body in sections:
        if not name:
            cards.append(f'<div class="vc-preamble">{_md(body)}</div>')
            continue
        meta = sec_map.get(name)
        if not meta:
            continue
        _, icon, css_cls, color = meta
        cards.append(
            f'<div class="verdict-card {css_cls}">'
            f'<div class="vc-header" style="color:{color}">{icon} {_h.escape(name)}</div>'
            f'<div class="vc-body">{_md(body)}</div>'
            f'</div>'
        )

    return (
        '<div class="verdict-wrapper">'
        '<div class="verdict-header">'
        '<div class="v-title">Final Verdict</div>'
        f'<div class="v-winner">🏆 {winner}</div>'
        '</div>'
        + '\n'.join(cards) +
        '</div>'
    )


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

_CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}

:root{
  --pro:#2563eb;--pro-bg:#1e3a8a;
  --con:#dc2626;--con-bg:#7f1d1d;
  --surface:#111827;--surface2:#1a2535;
  --border:rgba(255,255,255,0.08);
  --text:#f1f5f9;--muted:#94a3b8;
  --gold:#f59e0b;
}

body{
  font-family:'Segoe UI',system-ui,-apple-system,sans-serif;
  background:#080d1a;
  background-image:
    radial-gradient(ellipse 60% 40% at 20% 60%,rgba(37,99,235,.06) 0%,transparent 100%),
    radial-gradient(ellipse 60% 40% at 80% 20%,rgba(220,38,38,.05) 0%,transparent 100%);
  color:var(--text);min-height:100vh;
}

/* ─── Hero ─── */
.hero{
  background:linear-gradient(160deg,#0f2040 0%,#130d2e 45%,#0a1628 100%);
  border-bottom:1px solid var(--border);
  padding:3.5rem 2rem 2.5rem;text-align:center;position:relative;overflow:hidden;
}
.hero::before{
  content:'';position:absolute;inset:0;pointer-events:none;
  background:radial-gradient(ellipse 80% 60% at 50% 0%,rgba(56,189,248,.13),transparent);
}
.hero-eyebrow{
  font-size:.7rem;letter-spacing:.2em;text-transform:uppercase;
  color:#38bdf8;font-weight:700;margin-bottom:.8rem;
}
.hero-topic{
  font-size:clamp(1.4rem,3vw,2.1rem);font-weight:800;
  color:#f8fafc;line-height:1.3;max-width:700px;margin:0 auto 1rem;
}
.hero-meta{font-size:.85rem;color:var(--muted);margin-bottom:1.2rem;}
.winner-badge{
  display:inline-flex;align-items:center;gap:.5rem;
  background:linear-gradient(135deg,#78350f,#92400e);
  border:1px solid var(--gold);color:#fef3c7;
  padding:.5rem 1.5rem;border-radius:999px;
  font-weight:700;font-size:.95rem;
  box-shadow:0 0 24px rgba(245,158,11,.35);
}

/* ─── Layout ─── */
.container{max-width:860px;margin:0 auto;padding:2rem 1.5rem 4rem;}

/* ─── Legend ─── */
.legend{
  display:flex;justify-content:center;gap:2rem;
  margin:1.5rem 0 2.5rem;font-size:.8rem;color:var(--muted);
}
.legend-item{display:flex;align-items:center;gap:.5rem;}
.legend-dot{width:10px;height:10px;border-radius:50%;}

/* ─── Round header ─── */
.round-header{
  display:flex;align-items:center;gap:.8rem;margin:2rem 0 1rem;
}
.round-header::before,.round-header::after{
  content:'';flex:1;height:1px;background:var(--border);
}
.round-badge{
  background:var(--surface2);border:1px solid var(--border);
  color:var(--muted);font-size:.7rem;font-weight:700;
  letter-spacing:.12em;text-transform:uppercase;
  padding:.3rem .9rem;border-radius:999px;white-space:nowrap;
}

/* ─── Bubbles ─── */
.turn{
  display:flex;align-items:flex-start;gap:.75rem;
  margin:.9rem 0;animation:fadeUp .3s ease both;
}
.turn.pro{flex-direction:row-reverse;}

.avatar{
  width:36px;height:36px;border-radius:50%;
  display:flex;align-items:center;justify-content:center;
  font-weight:800;font-size:.85rem;flex-shrink:0;margin-top:3px;
}
.avatar.pro{background:linear-gradient(135deg,#1d4ed8,#3b82f6);color:#fff;}
.avatar.con{background:linear-gradient(135deg,#b91c1c,#ef4444);color:#fff;}

.bubble{
  max-width:76%;padding:1rem 1.25rem;border-radius:1rem;
  line-height:1.7;word-break:break-word;
}
.bubble.pro{
  background:linear-gradient(140deg,#1e3a8a,#1e40af);
  border:1px solid rgba(59,130,246,.3);
  border-top-right-radius:.25rem;
  box-shadow:0 4px 18px rgba(37,99,235,.2);
}
.bubble.con{
  background:linear-gradient(140deg,#7f1d1d,#991b1b);
  border:1px solid rgba(239,68,68,.3);
  border-top-left-radius:.25rem;
  box-shadow:0 4px 18px rgba(220,38,38,.2);
}
.bubble-header{
  font-size:.68rem;font-weight:700;letter-spacing:.09em;
  text-transform:uppercase;opacity:.6;margin-bottom:.5rem;
}
.bubble-body{font-size:.92rem;}
.bubble-body p{margin-bottom:.45rem;}
.bubble-body p:last-child{margin-bottom:0;}
.bubble-body .md-h{
  font-size:.82rem;text-transform:uppercase;letter-spacing:.07em;
  margin:.8rem 0 .3rem;opacity:.75;font-weight:700;
}
.bubble-body .md-ul{padding-left:1.3rem;margin:.4rem 0;}
.bubble-body li{margin:.2rem 0;font-size:.88rem;}
.bubble-body strong{font-weight:700;}
.bubble-body em{font-style:italic;opacity:.9;}
.citations{
  margin-top:.7rem;padding-top:.7rem;
  border-top:1px solid rgba(255,255,255,.1);
  font-size:.75rem;opacity:.6;
}
.citations span{font-weight:700;display:block;margin-bottom:.2rem;}
.citations ul{padding-left:1rem;}

/* ─── Judge cards ─── */
.judge-wrap{margin:.9rem auto;max-width:78%;animation:fadeUp .3s ease both;}
.judge-card{
  background:var(--surface);border:1px solid var(--border);
  border-radius:.875rem;padding:.9rem 1.15rem;font-size:.84rem;
  position:relative;
}
.judge-card::before{
  content:'⚖️';position:absolute;top:-11px;left:50%;
  transform:translateX(-50%);background:var(--surface);
  padding:0 .4rem;font-size:.85rem;
}
.j-label{
  font-size:.67rem;font-weight:700;color:var(--muted);
  text-transform:uppercase;letter-spacing:.11em;
  margin-bottom:.45rem;text-align:center;
}
.j-feedback{color:#cbd5e1;}
.j-feedback p{margin-bottom:.35rem;}
.j-feedback p:last-child{margin-bottom:0;}
.j-feedback strong{color:#e2e8f0;}
.j-prompt{
  margin-top:.55rem;padding-top:.55rem;
  border-top:1px solid var(--border);
  color:#7dd3fc;font-style:italic;font-size:.78rem;
}
.judge-card.reprimand{background:#1f0505;border-color:rgba(239,68,68,.4);}
.judge-card.reprimand::before{content:'⚠️';}
.judge-card.reprimand .j-label{color:#fca5a5;}
.judge-card.reprimand .j-feedback{color:#fecaca;}

/* ─── Scores ─── */
.scores-section{
  background:var(--surface);border:1px solid var(--border);
  border-radius:1rem;padding:1.8rem;margin:2.5rem 0;
}
.section-title{
  font-size:.72rem;font-weight:700;letter-spacing:.17em;
  text-transform:uppercase;color:var(--muted);
  text-align:center;margin-bottom:1.5rem;
}
.score-display{
  display:flex;justify-content:center;align-items:center;
  gap:3rem;margin-bottom:1.6rem;
}
.score-num .num{font-size:3rem;font-weight:800;line-height:1;}
.score-num .label{font-size:.72rem;color:var(--muted);margin-top:.35rem;text-transform:uppercase;letter-spacing:.1em;}
.score-num.pro .num{color:#60a5fa;}
.score-num.con .num{color:#f87171;}
.score-vs{font-size:1.4rem;color:var(--muted);}
.bar-row{display:flex;align-items:center;gap:.75rem;margin:.5rem 0;}
.bar-label{width:88px;font-size:.8rem;font-weight:600;flex-shrink:0;}
.bar-track{flex:1;background:rgba(255,255,255,.05);border-radius:999px;height:18px;overflow:hidden;}
.bar-fill{
  height:100%;border-radius:999px;
  display:flex;align-items:center;padding-left:.55rem;
  font-size:.73rem;font-weight:700;color:rgba(255,255,255,.9);
  transition:width 1s cubic-bezier(.4,0,.2,1);
}
.bar-fill.pro{background:linear-gradient(90deg,#1d4ed8,#3b82f6);}
.bar-fill.con{background:linear-gradient(90deg,#b91c1c,#ef4444);}

/* ─── Verdict ─── */
.verdict-wrapper{margin:2rem 0;}
.verdict-header{text-align:center;margin-bottom:1.6rem;}
.v-title{
  font-size:.72rem;letter-spacing:.2em;text-transform:uppercase;
  color:var(--gold);font-weight:700;
}
.v-winner{
  font-size:1.9rem;font-weight:800;color:#fef08a;margin-top:.4rem;
  text-shadow:0 0 32px rgba(245,158,11,.5);
}
.verdict-card{
  border-radius:.875rem;padding:1.3rem 1.5rem;margin:.75rem 0;
  border:1px solid rgba(255,255,255,.07);
}
.vc-header{
  display:flex;align-items:center;gap:.5rem;
  font-size:.7rem;font-weight:700;letter-spacing:.13em;
  text-transform:uppercase;margin-bottom:.75rem;
}
.vc-body{font-size:.89rem;line-height:1.8;color:#e2e8f0;}
.vc-body p{margin-bottom:.4rem;}
.vc-body p:last-child{margin-bottom:0;}
.vc-body strong{font-weight:700;}
.vc-body .md-ul{padding-left:1.3rem;margin:.4rem 0;}
.vc-body li{margin:.25rem 0;}
.vc-preamble{color:var(--muted);font-size:.85rem;margin-bottom:.5rem;}

.vc-clashes{background:rgba(8,47,73,.65);}
.vc-clashes .vc-header{color:#38bdf8;}
.vc-feedback{background:rgba(46,16,101,.55);}
.vc-feedback .vc-header{color:#c084fc;}
.vc-scoring{background:rgba(67,20,7,.55);}
.vc-scoring .vc-header{color:#fb923c;}
.vc-conclusion{background:rgba(6,78,59,.55);}
.vc-conclusion .vc-header{color:#4ade80;}

/* ─── Animations ─── */
@keyframes fadeUp{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
"""


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_html(transcript: list[dict], verdict: dict, topic: str, date_str: str) -> str:
    winner = verdict.get("winner", "?")
    scores = verdict.get("scores", {})

    parts, prev_round = [], 0
    for msg in transcript:
        mt  = msg.get("message_type", "")
        rnd = msg.get("round", 0)
        if mt == "argument" and rnd != prev_round:
            parts.append(_round_header(rnd))
            prev_round = rnd
        if mt == "argument":
            parts.append(_bubble(msg))
        elif mt == "routing":
            parts.append(_judge_card(msg))
        elif mt == "reprimand":
            parts.append(_judge_card(msg, is_reprimand=True))

    parts.append(_score_section(scores))
    parts.append(_verdict_block(verdict))

    body = "\n".join(parts)
    esc_topic  = _h.escape(topic)
    esc_date   = _h.escape(date_str)
    esc_winner = _h.escape(winner)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Debate: {esc_topic}</title>
<style>{_CSS}</style>
</head>
<body>
<div class="hero">
  <div class="hero-eyebrow">AI Agent Debate System</div>
  <div class="hero-topic">{esc_topic}</div>
  <div class="hero-meta">{esc_date}</div>
  <div class="winner-badge">🏆 Winner: {esc_winner}</div>
</div>
<div class="container">
  <div class="legend">
    <div class="legend-item"><div class="legend-dot" style="background:#3b82f6"></div>Agent Pro (For)</div>
    <div class="legend-item"><div class="legend-dot" style="background:#ef4444"></div>Agent Con (Against)</div>
    <div class="legend-item"><div class="legend-dot" style="background:#475569"></div>Judge Feedback</div>
  </div>
{body}
</div>
</body>
</html>"""
