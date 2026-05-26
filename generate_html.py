"""Standalone HTML debate viewer generator — no external dependencies."""

import html as _h
from datetime import datetime

_PRO_ID = "Agent_Pro"
_CON_ID = "Agent_Con"

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0f172a; color: #e2e8f0; }
a { color: #93c5fd; }

/* ── Header ── */
.header { background: linear-gradient(135deg, #1e3a5f 0%, #0f172a 100%);
  padding: 2rem; text-align: center; border-bottom: 2px solid #334155; }
.header h1 { font-size: 1.4rem; color: #94a3b8; letter-spacing: .15em; text-transform: uppercase; }
.header .topic { font-size: 1.8rem; font-weight: 700; margin: .6rem 0; color: #f1f5f9; }
.header .meta { font-size: .9rem; color: #64748b; }
.winner-badge { display: inline-block; margin-top: .8rem; padding: .4rem 1.2rem;
  background: #ca8a04; color: #fef9c3; border-radius: 999px;
  font-weight: 700; font-size: 1rem; letter-spacing: .05em; }

/* ── Layout ── */
.container { max-width: 900px; margin: 0 auto; padding: 2rem 1rem; }

/* ── Bubbles ── */
.bubble { max-width: 72%; margin: 1rem 0; padding: 1rem 1.2rem;
  border-radius: 1rem; line-height: 1.6; word-break: break-word; }
.bubble .round-label { font-size: .75rem; font-weight: 700;
  letter-spacing: .08em; text-transform: uppercase; margin-bottom: .4rem; opacity: .75; }
.bubble .text { font-size: .95rem; white-space: pre-wrap; }
.bubble .citations { margin-top: .6rem; font-size: .8rem; opacity: .7; font-style: italic; }

.pro { background: #1e40af; margin-left: auto; border-bottom-right-radius: .2rem; }
.con { background: #9a3412; margin-right: auto; border-bottom-left-radius: .2rem; }

/* ── Judge panels ── */
.judge-card { background: #1e293b; border: 1px solid #334155;
  border-radius: .75rem; padding: .9rem 1.1rem; margin: .6rem auto;
  max-width: 85%; font-size: .88rem; }
.judge-card .j-label { font-size: .72rem; font-weight: 700; color: #94a3b8;
  text-transform: uppercase; letter-spacing: .1em; margin-bottom: .35rem; }
.judge-card .j-feedback { color: #cbd5e1; white-space: pre-wrap; }
.judge-card .j-prompt { margin-top: .4rem; color: #7dd3fc; font-style: italic; font-size: .83rem; }

.reprimand { background: #450a0a; border: 1px solid #dc2626; }
.reprimand .j-label { color: #fca5a5; }
.reprimand .j-feedback { color: #fecaca; }

/* ── Score bars ── */
.scores-section { margin: 2.5rem 0; background: #1e293b;
  border-radius: 1rem; padding: 1.5rem; border: 1px solid #334155; }
.scores-section h2 { font-size: 1.1rem; color: #94a3b8; margin-bottom: 1rem;
  text-transform: uppercase; letter-spacing: .1em; }
.score-row { display: flex; align-items: center; gap: 1rem; margin: .6rem 0; }
.score-row .agent-name { width: 100px; font-size: .9rem; font-weight: 600; flex-shrink: 0; }
.score-row .bar-wrap { flex: 1; background: #0f172a; border-radius: 999px; height: 22px; overflow: hidden; }
.score-row .bar { height: 100%; border-radius: 999px;
  display: flex; align-items: center; padding-left: .6rem;
  font-size: .8rem; font-weight: 700; color: #fff; transition: width .4s ease; }
.bar.pro-bar { background: #2563eb; }
.bar.con-bar { background: #ea580c; }
.score-row .pct { width: 40px; text-align: right; font-weight: 700; font-size: .95rem; }

/* ── Verdict panel ── */
.verdict-panel { background: linear-gradient(135deg, #78350f, #451a03);
  border: 2px solid #ca8a04; border-radius: 1rem; padding: 1.8rem;
  margin: 2rem 0; }
.verdict-panel h2 { color: #fde68a; font-size: 1.3rem; margin-bottom: 1rem; }
.verdict-panel .v-winner { font-size: 1.5rem; font-weight: 800;
  color: #fef08a; margin-bottom: 1rem; }
.verdict-panel .v-justification { color: #fef3c7; line-height: 1.8;
  white-space: pre-wrap; font-size: .93rem; }
.verdict-panel .v-section-title { color: #fde68a; font-weight: 700;
  text-transform: uppercase; letter-spacing: .08em; }
.round-divider { text-align: center; color: #475569; font-size: .75rem;
  margin: 1.2rem 0; letter-spacing: .15em; }
"""


def _bubble(msg: dict) -> str:
    agent = msg.get("agent_id", "?")
    rnd = msg.get("round", "?")
    argument = _h.escape(msg.get("argument", ""))
    citations = msg.get("citations", [])
    side = "pro" if agent == _PRO_ID else "con"
    label = f"Round {rnd} · {agent} ({'FOR' if agent == _PRO_ID else 'AGAINST'})"
    cite_html = ""
    if citations:
        items = "".join(f"<li>{_h.escape(c)}</li>" for c in citations)
        cite_html = f'<div class="citations"><strong>Citations:</strong><ul>{items}</ul></div>'
    return (
        f'<div class="bubble {side}">'
        f'<div class="round-label">{_h.escape(label)}</div>'
        f'<div class="text">{argument}</div>'
        f'{cite_html}</div>'
    )


def _judge_card(msg: dict, is_reprimand: bool = False) -> str:
    extra = " reprimand" if is_reprimand else ""
    if is_reprimand:
        target = msg.get("target_agent", "?")
        prompt = _h.escape(msg.get("prompt_for_next", ""))
        label = f"⚠ Judge REPRIMAND → {target}"
        return (
            f'<div class="judge-card{extra}">'
            f'<div class="j-label">{_h.escape(label)}</div>'
            f'<div class="j-feedback">{prompt}</div></div>'
        )
    target = msg.get("target_agent", "?")
    feedback = _h.escape(msg.get("judge_feedback", ""))
    prompt = _h.escape(msg.get("prompt_for_next", ""))
    label = f"Judge → {target}"
    return (
        f'<div class="judge-card">'
        f'<div class="j-label">{_h.escape(label)}</div>'
        f'<div class="j-feedback">{feedback}</div>'
        f'<div class="j-prompt">{prompt}</div></div>'
    )


def _score_bars(scores: dict) -> str:
    pro = scores.get(_PRO_ID, 0)
    con = scores.get(_CON_ID, 0)
    return (
        '<div class="scores-section"><h2>Final Scores</h2>'
        f'<div class="score-row"><div class="agent-name">{_PRO_ID}</div>'
        f'<div class="bar-wrap"><div class="bar pro-bar" style="width:{pro}%">{pro}%</div></div>'
        f'<div class="pct">{pro}%</div></div>'
        f'<div class="score-row"><div class="agent-name">{_CON_ID}</div>'
        f'<div class="bar-wrap"><div class="bar con-bar" style="width:{con}%">{con}%</div></div>'
        f'<div class="pct">{con}%</div></div></div>'
    )


def _verdict_block(verdict: dict) -> str:
    winner = _h.escape(verdict.get("winner", "?"))
    scores = verdict.get("scores", {})
    raw = verdict.get("justification", "")
    for section in ("KEY CLASHES", "FEEDBACK ADHERENCE", "SCORING BREAKDOWN", "FINAL CONCLUSION"):
        raw = raw.replace(section, f'<span class="v-section-title">{section}</span>')
    return (
        '<div class="verdict-panel">'
        '<h2>🏆 Final Verdict</h2>'
        f'<div class="v-winner">Winner: {winner}</div>'
        f'<div class="v-justification">{raw}</div>'
        '</div>'
    )


def generate_html(transcript: list[dict], verdict: dict, topic: str, date_str: str) -> str:
    winner = verdict.get("winner", "?")
    scores = verdict.get("scores", {})

    body_parts = []
    prev_round = 0
    for msg in transcript:
        mt = msg.get("message_type", "")
        rnd = msg.get("round", 0)
        if mt == "argument" and rnd != prev_round:
            if prev_round:
                body_parts.append(f'<div class="round-divider">── Round {prev_round} complete ──</div>')
            prev_round = rnd
        if mt == "argument":
            body_parts.append(_bubble(msg))
        elif mt == "routing":
            body_parts.append(_judge_card(msg))
        elif mt == "reprimand":
            body_parts.append(_judge_card(msg, is_reprimand=True))

    body_parts.append(_score_bars(scores))
    body_parts.append(_verdict_block(verdict))

    body_html = "\n".join(body_parts)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Debate: {_h.escape(topic)}</title>
<style>{_CSS}</style>
</head>
<body>
<div class="header">
  <h1>AI Agent Debate System</h1>
  <div class="topic">{_h.escape(topic)}</div>
  <div class="meta">{_h.escape(date_str)}</div>
  <div class="winner-badge">🏆 Winner: {_h.escape(winner)}</div>
</div>
<div class="container">
{body_html}
</div>
</body>
</html>"""
