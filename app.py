
import json, re
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Any
import streamlit as st
from groq import Groq

st.set_page_config(
    page_title="AI Customer Support Coach",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------- Styling ----------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}
.stApp {
    background: #f7f9fc;
}
.block-container {
    max-width: 1500px;
    padding: 0.7rem 1.25rem 2rem;
}
header[data-testid="stHeader"] {
    background: transparent;
}
.topbar {
    background: linear-gradient(90deg,#071b49,#0c2b67);
    color: white;
    border-radius: 14px;
    padding: 15px 22px;
    margin: 0 0 16px 0;
    display:flex;
    align-items:center;
    justify-content:space-between;
    box-shadow:0 6px 18px rgba(10,35,80,.12);
}
.brand {
    font-size: 25px;
    font-weight: 800;
    letter-spacing: .2px;
}
.live {
    color:#9cf3bb;
    font-weight:700;
    margin-left:15px;
    font-size:14px;
}
.dot {
    display:inline-block;width:9px;height:9px;border-radius:50%;
    background:#38d979;margin-right:7px;
}
.card {
    background:#fff;
    border:1px solid #e3e8f0;
    border-radius:12px;
    padding:16px;
    box-shadow:0 2px 8px rgba(15,35,70,.04);
    height:100%;
}
.card-title {
    color:#10245a;
    font-size:14px;
    font-weight:800;
    text-transform:uppercase;
    letter-spacing:.3px;
    margin-bottom:12px;
}
.chatbox {
    border:1px solid #e3e8f0;
    background:#fff;
    border-radius:12px;
    padding:12px;
    height:475px;
    overflow-y:auto;
}
.msg {
    padding:11px 13px;
    border-radius:11px;
    margin:8px 0;
    font-size:13px;
    line-height:1.45;
}
.customer {
    background:#fff0f1;
    border-left:4px solid #ff6b78;
}
.agent {
    background:#edf5ff;
    border-left:4px solid #4d90fe;
}
.small {
    font-size:11px;color:#75809a;
}
.metric {
    text-align:center;
    background:#fff;
    border:1px solid #e3e8f0;
    border-radius:12px;
    padding:14px 8px;
}
.metric h2 { margin:3px 0; color:#172342; }
.metric p { margin:0; font-size:11px; color:#7a849b; }
.badge {
    display:inline-block;padding:5px 10px;border-radius:7px;
    font-size:11px;font-weight:800;
}
.red {background:#fff0f1;color:#e33445;}
.green {background:#eaf9ef;color:#16864b;}
.orange {background:#fff5e8;color:#db7900;}
.blue {background:#edf4ff;color:#1f62cc;}
.reply {
    background:#eefaf0;
    border:1px solid #c9ebcf;
    border-radius:9px;
    padding:14px;
    color:#263b2d;
    font-size:13px;
    line-height:1.5;
}
.tip {
    background:#eefbf1;
    border:1px solid #cfead5;
    border-radius:9px;
    padding:13px;
    font-size:12px;
    line-height:1.5;
}
.section-gap { margin-top:14px; }
div[data-testid="stTextArea"] textarea {
    border-radius:9px !important;
}
div.stButton > button {
    border-radius:8px;
    font-weight:700;
}
[data-testid="stMetricValue"] { font-size: 25px; }
hr { border-color:#e5e9f0; }
</style>
""", unsafe_allow_html=True)

# ---------- State ----------
@dataclass
class Promise:
    description: str
    deadline: str
    promised_at: str
    status: str = "Pending"
    fulfilled_at: str = "-"

@dataclass
class State:
    history: List[Dict[str,str]] = field(default_factory=list)
    sentiment: str = "—"
    emotion: str = "—"
    intent: str = "—"
    urgency: str = "—"
    escalation_risk: int = 0
    key_issue: str = "No customer message yet"
    main_concern: str = "—"
    suggested_reply: str = ""
    coaching_tip: str = "Analyze an agent response to receive coaching."
    tone: int = 0
    empathy: int = 0
    clarity: int = 0
    accuracy: int = 0
    actionability: int = 0
    patience: int = 100
    trust: int = 100
    patience_history: List[int] = field(default_factory=lambda:[100])
    trust_history: List[int] = field(default_factory=lambda:[100])
    promises: List[Promise] = field(default_factory=list)

if "state" not in st.session_state:
    st.session_state.state = State()
if "last_analysis" not in st.session_state:
    st.session_state.last_analysis = {}

state = st.session_state.state

# ---------- Helpers ----------
def now():
    return datetime.now().strftime("%I:%M %p")

def context_text():
    return "\n".join(
        f"{m['role'].title()}: {m['text']}"
        for m in state.history[-12:]
    ) or "No previous conversation."

def safe_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    match = re.search(r"\{.*\}", text, re.S)
    if match:
        text = match.group(0)
    return json.loads(text)

def call_ai(prompt, api_key):
    client = Groq(api_key=api_key)
    result = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        temperature=0.2,
        messages=[
            {"role":"system","content":"You are an expert real-time customer support coach. Return valid JSON only."},
            {"role":"user","content":prompt}
        ]
    )
    return result.choices[0].message.content

def analyze_customer(message, api_key):
    prompt = f"""
Analyze ANY customer-support message dynamically. Do not assume a fixed category.
Use the conversation context.

CONTEXT:
{context_text()}

CUSTOMER MESSAGE:
{message}

Return exactly this JSON:
{{
 "sentiment":"Positive|Neutral|Negative",
 "emotion":"one short emotion",
 "intent":"one short intent",
 "urgency":"Low|Medium|High|Critical",
 "escalation_risk":"Low|Medium|High|Critical",
 "escalation_score":0,
 "key_issue":"short phrase",
 "main_concern":"short phrase",
 "patience_impact":0,
 "trust_impact":0,
 "suggested_reply":"professional, empathetic, actionable reply"
}}

escalation_score and impact values must be integers from 0 to 100.
"""
    return safe_json(call_ai(prompt, api_key))

def evaluate_agent(customer, agent, api_key):
    prompt = f"""
Evaluate the agent response in a customer support conversation.

CONTEXT:
{context_text()}

LATEST CUSTOMER:
{customer}

AGENT RESPONSE:
{agent}

Return exactly:
{{
 "tone":0,
 "empathy":0,
 "clarity":0,
 "accuracy":0,
 "actionability":0,
 "coaching_tip":"one concise coaching tip"
}}
Scores are integers from 0 to 100.
"""
    return safe_json(call_ai(prompt, api_key))

def risk_score(value):
    mapping = {"Low":25,"Medium":50,"High":75,"Critical":95}
    return mapping.get(value,50)

def update_metrics_from_customer(a):
    """
    Update coaching indicators from the AI classification.
    These are coaching indicators, not psychological measurements.

    We deliberately map negative customer states to negative deltas so that
    repeated frustration/anger/waiting messages visibly reduce patience.
    """
    sentiment = str(a.get("sentiment", "")).lower()
    emotion = str(a.get("emotion", "")).lower()
    urgency = str(a.get("urgency", "")).lower()
    risk = str(a.get("escalation_risk", "")).lower()

    patience_delta = 0
    trust_delta = 0

    # Sentiment
    if sentiment == "negative":
        patience_delta -= 8
        trust_delta -= 5
    elif sentiment == "positive":
        patience_delta += 3
        trust_delta += 6

    # Emotion
    if any(word in emotion for word in ["angry", "furious", "rage"]):
        patience_delta -= 12
        trust_delta -= 8
    elif any(word in emotion for word in ["frustrat", "annoy", "impatient", "upset"]):
        patience_delta -= 10
        trust_delta -= 6
    elif any(word in emotion for word in ["worried", "anxious", "concern", "disappoint"]):
        patience_delta -= 6
        trust_delta -= 4
    elif any(word in emotion for word in ["happy", "satisfied", "grateful", "pleased"]):
        patience_delta += 4
        trust_delta += 5

    # Urgency and escalation add pressure.
    if urgency == "high":
        patience_delta -= 4
    elif urgency == "critical":
        patience_delta -= 8

    if risk == "high":
        patience_delta -= 3
        trust_delta -= 2
    elif risk == "critical":
        patience_delta -= 6
        trust_delta -= 4

    # Also respect the model's explicit impact values, but only in the
    # direction that agrees with the customer's detected state.
    try:
        ai_patience = int(a.get("patience_impact", 0))
        ai_trust = int(a.get("trust_impact", 0))
    except (TypeError, ValueError):
        ai_patience, ai_trust = 0, 0

    if sentiment == "negative":
        patience_delta -= min(abs(ai_patience), 5)
        trust_delta -= min(abs(ai_trust), 4)
    elif sentiment == "positive":
        patience_delta += min(abs(ai_patience), 4)
        trust_delta += min(abs(ai_trust), 4)

    state.patience = max(0, min(100, state.patience + patience_delta))
    state.trust = max(0, min(100, state.trust + trust_delta))
    state.patience_history.append(state.patience)
    state.trust_history.append(state.trust)

def detect_promise(text):
    commitment = re.search(
        r"\b(I\s+(?:will|['’]ll|can)|we\s+(?:will|['’]ll|can)|let\s+me)\b",
        text, re.I
    )
    if not commitment:
        return
    deadline = "No deadline"
    minutes = re.search(r"\b(?:in|within)\s+(\d+)\s*(minute|minutes|min|hour|hours|day|days)\b", text, re.I)
    if minutes:
        n = int(minutes.group(1)); unit = minutes.group(2).lower()
        delta = timedelta(minutes=n) if "min" in unit else timedelta(hours=n) if "hour" in unit else timedelta(days=n)
        deadline = (datetime.now()+delta).strftime("%I:%M %p")
    description = text.strip()
    state.promises.append(Promise(description, deadline, now()))

def fulfill_promise(text):
    completion_words = ["done","completed","resolved","fixed","processed","checked","escalated","updated"]
    if not any(w in text.lower() for w in completion_words):
        return
    for p in reversed(state.promises):
        if p.status == "Pending":
            p.status = "Fulfilled"
            p.fulfilled_at = now()
            break

def reset():
    st.session_state.state = State()
    st.session_state.last_analysis = {}

# ---------- Header ----------
st.markdown("""
<div class="topbar">
  <div><span class="brand">🤖 AI CUSTOMER SUPPORT COACH</span>
  <span class="live"><span class="dot"></span>LIVE COACHING</span></div>
  <div></div>
</div>
""", unsafe_allow_html=True)

# ---------- Controls ----------
c1, c2, c3 = st.columns([1,1,4])
with c1:
    if st.button("🆕 New Conversation", use_container_width=True):
        reset(); st.rerun()
with c2:
    with st.popover("⚙ Settings"):
        st.text_input(
            "Groq API Key",
            type="password",
            key="api_key_input",
            placeholder="gsk_..."
        )
        st.caption("Your key is used only for this running session.")

# IMPORTANT: read the persistent Streamlit widget value.
# The previous version accidentally overwrote it with an empty value.
api_key = st.session_state.get("api_key_input", "").strip()

if api_key:
    st.success("Groq API key is loaded. You can analyze customer messages.", icon="✅")
else:
    st.info("Open ⚙ Settings and enter your Groq API key.", icon="🔑")

st.markdown("---")

# ---------- Top metrics ----------
def gauge_html(label, value, color, subtext):
    return f"""
    <div class="metric">
      <div class="card-title">{label}</div>
      <div style="font-size:38px;font-weight:800;color:{color};">{value}%</div>
      <div class="small">{subtext}</div>
    </div>
    """

risk = int(state.escalation_risk)
pat_text = "Healthy" if state.patience >= 70 else "Patience is decreasing" if state.patience >= 40 else "Very low patience"
trust_text = "Strong trust" if state.trust >= 70 else "Trust can improve" if state.trust >= 40 else "Trust is at risk"
risk_text = "Low" if risk < 40 else "Medium" if risk < 70 else "High"

m1,m2,m3,m4 = st.columns([1.1,1,1,1.1])
with m1:
    st.markdown('<div class="card"><div class="card-title">Conversation</div>', unsafe_allow_html=True)
    st.markdown(f"**Messages:** {len(state.history)}")
    st.markdown(f"**Status:** {'Active' if state.history else 'Waiting for customer'}")
    st.markdown("</div>", unsafe_allow_html=True)
with m2:
    st.markdown(gauge_html("Customer Patience",state.patience,"#ef8b16",pat_text),unsafe_allow_html=True)
with m3:
    st.markdown(gauge_html("Customer Trust",state.trust,"#22a447",trust_text),unsafe_allow_html=True)
with m4:
    st.markdown(gauge_html("Escalation Risk",risk,"#ef3131",risk_text),unsafe_allow_html=True)

st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)

# ---------- Main layout ----------
left, center, right = st.columns([1.15, 1.55, .95], gap="small")

with left:
    st.markdown('<div class="card"><div class="card-title">Conversation</div>', unsafe_allow_html=True)
    chat = '<div class="chatbox">'
    if not state.history:
        chat += '<div class="small" style="text-align:center;margin-top:180px;">Start by entering any customer sentence below.</div>'
    else:
        for m in state.history:
            role = "customer" if m["role"]=="customer" else "agent"
            icon = "👤" if role=="customer" else "🧑‍💼"
            chat += f'<div class="msg {role}"><b>{icon} {m["role"].title()}</b> <span class="small">{m["time"]}</span><br>{m["text"]}</div>'
    chat += "</div>"
    st.markdown(chat, unsafe_allow_html=True)

    st.markdown("**Customer Message**")
    customer = st.text_area("Customer", placeholder="Type customer message here...", height=90, label_visibility="collapsed")
    if st.button("🔍 Analyze Customer", type="primary", use_container_width=True):
        if not api_key:
            st.error("Enter your Groq API key in ⚙ Settings first.")
        elif not customer.strip():
            st.warning("Type a customer message first.")
        else:
            with st.spinner("Analyzing customer..."):
                try:
                    a = analyze_customer(customer.strip(), api_key)
                    state.history.append({"role":"customer","text":customer.strip(),"time":now()})
                    state.sentiment=a.get("sentiment","—")
                    state.emotion=a.get("emotion","—")
                    state.intent=a.get("intent","—")
                    state.urgency=a.get("urgency","—")
                    state.escalation_risk=int(a.get("escalation_score",risk_score(a.get("escalation_risk","Medium"))))
                    state.key_issue=a.get("key_issue","—")
                    state.main_concern=a.get("main_concern","—")
                    state.suggested_reply=a.get("suggested_reply","")
                    update_metrics_from_customer(a)
                    st.session_state.last_customer = customer.strip()
                    st.rerun()
                except Exception as e:
                    st.error(f"AI analysis failed: {e}")

    st.markdown("**Agent Response**")
    agent = st.text_area("Agent", placeholder="Type your response here...", height=90, label_visibility="collapsed")
    if st.button("🛡️ Evaluate Response", type="primary", use_container_width=True):
        if not api_key:
            st.error("Enter your Groq API key in ⚙ Settings first.")
        elif not agent.strip():
            st.warning("Type an agent response first.")
        elif not state.history:
            st.warning("Analyze a customer message first.")
        else:
            customer_latest = next((m["text"] for m in reversed(state.history) if m["role"]=="customer"), "")
            with st.spinner("Evaluating agent response..."):
                try:
                    e = evaluate_agent(customer_latest,agent.strip(),api_key)
                    state.history.append({"role":"agent","text":agent.strip(),"time":now()})
                    state.tone=int(e.get("tone",0)); state.empathy=int(e.get("empathy",0))
                    state.clarity=int(e.get("clarity",0)); state.accuracy=int(e.get("accuracy",0))
                    state.actionability=int(e.get("actionability",0))
                    state.coaching_tip=e.get("coaching_tip","")
                    avg=(state.tone+state.empathy+state.clarity+state.accuracy+state.actionability)/5
                    state.trust=max(0,min(100,state.trust+round((avg-70)/5)))
                    state.patience=max(0,min(100,state.patience+round((avg-70)/6)))
                    state.patience_history.append(state.patience); state.trust_history.append(state.trust)
                    detect_promise(agent.strip()); fulfill_promise(agent.strip())
                    st.rerun()
                except Exception as e:
                    st.error(f"Agent evaluation failed: {e}")
    st.markdown("</div>", unsafe_allow_html=True)

with center:
    st.markdown('<div class="card"><div class="card-title">Customer Analysis</div>', unsafe_allow_html=True)
    a1,a2=st.columns(2)
    with a1:
        st.markdown(f"**Sentiment**<br><span class='badge red'>{state.sentiment}</span>",unsafe_allow_html=True)
        st.markdown(f"**Emotion**<br><span class='badge blue'>{state.emotion}</span>",unsafe_allow_html=True)
        st.markdown(f"**Intent**<br>{state.intent}",unsafe_allow_html=True)
    with a2:
        st.markdown(f"**Urgency**<br><span class='badge orange'>{state.urgency}</span>",unsafe_allow_html=True)
        st.markdown(f"**Key Issue**<br>{state.key_issue}",unsafe_allow_html=True)
        st.markdown(f"**Main Concern**<br>{state.main_concern}",unsafe_allow_html=True)
    st.markdown("</div>",unsafe_allow_html=True)

    st.markdown('<div class="section-gap"></div>',unsafe_allow_html=True)
    st.markdown('<div class="card"><div class="card-title">AI Suggested Reply</div>',unsafe_allow_html=True)
    if state.suggested_reply:
        st.markdown(f"<div class='reply'>{state.suggested_reply}</div>",unsafe_allow_html=True)
        if st.button("📋 Use This Reply", use_container_width=True):
            st.session_state["suggested_copy"] = state.suggested_reply
    else:
        st.info("A suggested reply will appear after customer analysis.")
    st.markdown("</div>",unsafe_allow_html=True)

    st.markdown('<div class="section-gap"></div>',unsafe_allow_html=True)
    st.markdown('<div class="card"><div class="card-title">Agent Coaching</div>',unsafe_allow_html=True)
    scores=[state.tone,state.empathy,state.clarity,state.accuracy,state.actionability]
    labels=["Tone","Empathy","Clarity","Accuracy","Actionability"]
    cols=st.columns(5)
    for c,l,s in zip(cols,labels,scores):
        c.metric(l,s)
    st.markdown(f"<div class='tip'>💡 <b>Coaching Tip:</b> {state.coaching_tip}</div>",unsafe_allow_html=True)
    st.markdown("</div>",unsafe_allow_html=True)

with right:
    st.markdown('<div class="card"><div class="card-title">Promise Tracker</div>',unsafe_allow_html=True)
    if not state.promises:
        st.info("No promises detected yet.")
    else:
        for p in state.promises[-4:][::-1]:
            cls="green" if p.status=="Fulfilled" else "orange"
            icon="🟢" if p.status=="Fulfilled" else "🟠"
            st.markdown(f"<span class='badge {cls}'>{icon} {p.status.upper()}</span>",unsafe_allow_html=True)
            st.markdown(f"**{p.description[:90]}**")
            st.markdown(f"<span class='small'>Deadline: {p.deadline}<br>Promised at: {p.promised_at}<br>Fulfilled at: {p.fulfilled_at}</span>",unsafe_allow_html=True)
            st.markdown("---")
    st.markdown("</div>",unsafe_allow_html=True)

    st.markdown('<div class="section-gap"></div>',unsafe_allow_html=True)
    st.markdown('<div class="card"><div class="card-title">Session Metrics</div>',unsafe_allow_html=True)
    st.metric("Total Messages",len(state.history))
    st.metric("Current Patience",f"{state.patience}%")
    st.metric("Current Trust",f"{state.trust}%")
    kept=sum(p.status=="Fulfilled" for p in state.promises)
    st.metric("Promises Kept",f"{kept} / {len(state.promises)}")
    st.metric("Escalation Risk","High" if risk>=70 else "Medium" if risk>=40 else "Low")
    st.markdown("</div>",unsafe_allow_html=True)

# ---------- Trend + promises ----------
st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
c1,c2=st.columns([2,1])
with c1:
    st.markdown('<div class="card"><div class="card-title">Metrics Over Time</div>',unsafe_allow_html=True)
    import pandas as pd
    n=max(len(state.patience_history),len(state.trust_history))
    df=pd.DataFrame({
        "Turn": list(range(1,n+1)),
        "Patience": state.patience_history,
        "Trust": state.trust_history
    })
    st.line_chart(df.set_index("Turn"), height=230)
    st.markdown("</div>",unsafe_allow_html=True)

with c2:
    st.markdown('<div class="card"><div class="card-title">Live Status</div>',unsafe_allow_html=True)
    st.markdown(f"**Sentiment:** {state.sentiment}")
    st.markdown(f"**Urgency:** {state.urgency}")
    st.markdown(f"**Escalation:** <span class='badge red'>{risk_text}</span>",unsafe_allow_html=True)
    st.markdown(f"**Promises:** {len(state.promises)}")
    st.markdown("</div>",unsafe_allow_html=True)

st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
st.markdown('<div class="card"><div class="card-title">Recent Promises</div>',unsafe_allow_html=True)
if state.promises:
    rows=[]
    for p in state.promises:
        rows.append({"Description":p.description,"Deadline":p.deadline,"Status":p.status,"Promised At":p.promised_at,"Fulfilled At":p.fulfilled_at})
    st.dataframe(rows,use_container_width=True,hide_index=True)
else:
    st.caption("Promises detected from agent commitments will appear here.")
st.markdown("</div>",unsafe_allow_html=True)
