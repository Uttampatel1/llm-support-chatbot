"""Streamlit chat UI for the support bot. Run:  streamlit run app.py"""
from __future__ import annotations

import os

import streamlit as st

from src.agent import SupportAgent
from src.config import get_settings
from src.generate_data import seed

st.set_page_config(page_title="Support Chatbot", page_icon="🛍️")

settings = get_settings()
if not os.path.exists(settings.db_path):
    seed(settings.db_path)

if "agent" not in st.session_state:
    st.session_state.agent = SupportAgent(settings)
    st.session_state.history = []

st.title("🛍️ Tea & Coffee — Support Assistant")
st.caption(
    f"Provider: **{st.session_state.agent.provider.name}**. "
    "Demo accounts: alice@example.com (ORD-1001 delivered, ORD-1002 shipped)."
)

with st.sidebar:
    st.subheader("Try asking")
    st.write("- My email is alice@example.com")
    st.write("- What's the status of ORD-1002?")
    st.write("- List my orders")
    st.write("- I want to return ORD-1001 because it arrived damaged")
    st.write("- What's your return policy?")
    st.write("- How much is the kettle?")
    if st.button("Reset conversation"):
        st.session_state.agent = SupportAgent(settings)
        st.session_state.history = []

for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("tools"):
            with st.expander("🔧 tool calls"):
                st.json(msg["tools"])

if prompt := st.chat_input("Ask about orders, returns, products…"):
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    result = st.session_state.agent.chat(prompt)
    with st.chat_message("assistant"):
        st.markdown(result.reply)
        if result.tool_calls:
            with st.expander("🔧 tool calls"):
                st.json(result.tool_calls)
    st.session_state.history.append(
        {"role": "assistant", "content": result.reply, "tools": result.tool_calls}
    )
