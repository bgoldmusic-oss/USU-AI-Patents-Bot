"""
USU Patents Research Intelligence — Streamlit chatbot.
Loads local CSV/Excel and answers questions using Claude with full patent context.
"""
import os
import streamlit as st
import pandas as pd
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

DATA_FILE = "Patents_Full_Data.xlsx"

SYSTEM_PROMPT = """You are a helpful research assistant for USU (Utah State University) Patents.
Answer questions using ONLY the patent records provided below. If the answer is not in the data, say so clearly.
Cite specific patents (title or inventor) when relevant. Be concise and accurate.
Always include the Flintbox link at the bottom of any patent detail response, formatted as a markdown link like this: [View on Flintbox](URL)"""


def load_patents():
    """Load patent data from Excel. Returns a DataFrame."""
    if not os.path.exists(DATA_FILE):
        raise FileNotFoundError(f"{DATA_FILE} not found. Add it to this folder.")
    return pd.read_excel(DATA_FILE, engine="openpyxl")


def patents_to_context(df: pd.DataFrame) -> str:
    """Turn the DataFrame into a single text block for the LLM context."""
    rows = []
    for i, row in df.iterrows():
        rows.append(
            f"Patent {i + 1}:\n"
            f"  Title: {row.get('Title', '')}\n"
            f"  Problem: {row.get('Problem', '')}\n"
            f"  Solution: {row.get('Solution', '')}\n"
            f"  Abstract: {row.get('Abstract', '')}\n"
            f"  Benefit: {row.get('Benefit', '')}\n"
            f"  Market Application: {row.get('Market Application', '')}\n"
            f"  Inventors: {row.get('Inventors', '')}\n"
            f"  Flintbox Link: {row.get('Flintbox Link', '')}\n"
        )
    return "\n".join(rows)


def ask_claude(user_question: str, context: str) -> str:
    """Send user question + patent context to Claude and return the reply."""
    api_key = st.secrets.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return (
            "Error: ANTHROPIC_API_KEY is not set. "
            "Create a .env file with: ANTHROPIC_API_KEY=your_key_here"
        )
    client = Anthropic(api_key=api_key)
    full_prompt = (
        "Here are the patent records to use for answering:\n\n"
        f"{context}\n\n"
        "---\n\n"
        f"User question: {user_question}"
    )
    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": full_prompt}],
        )
        return message.content[0].text
    except Exception as e:
        return f"API error: {str(e)}"


def main():
    st.set_page_config(page_title="USU Patents Research", layout="centered")
    st.title("USU Patents Research Intelligence")
    password = st.text_input("Password", type="password", key="password")
    if password != "USU2026":
        if password:
            st.error("Wrong password. Try again.")
        st.stop()
    st.caption("Ask questions about USU patents. Data is loaded from a local Excel file.")

    try:
        df = load_patents()
        context = patents_to_context(df)
        st.sidebar.success(f"Loaded {len(df)} patent(s) from {DATA_FILE}.")
        if st.sidebar.button("Reset", help="Clear chat and start again"):
            st.session_state.messages = []
            st.rerun()
    except FileNotFoundError as e:
        st.error(str(e))
        st.stop()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    LICENSING_MSG = "If you require more information or are interested in licensing please contact USU's Tech Transfer office at techtransfer@usu.edu"

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant":
                st.caption(LICENSING_MSG)

    if prompt := st.chat_input("Ask a question about the patents..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                reply = ask_claude(prompt, context)
            st.markdown(reply)
            st.caption(LICENSING_MSG)
        st.session_state.messages.append({"role": "assistant", "content": reply})


if __name__ == "__main__":
    main()
