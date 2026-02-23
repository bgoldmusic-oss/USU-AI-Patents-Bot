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

DATA_FILE = "patents.csv"
DATA_FILE_XLSX = "patents.xlsx"

SYSTEM_PROMPT = """You are a helpful research assistant for USU (Utah State University) Patents.
Answer questions using ONLY the patent records provided below. If the answer is not in the data, say so clearly.
Cite specific patents (title or inventor) when relevant. Be concise and accurate."""


def load_patents():
    """Load patent data from CSV or Excel. Returns a DataFrame."""
    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE)
    if os.path.exists(DATA_FILE_XLSX):
        return pd.read_excel(DATA_FILE_XLSX, engine="openpyxl")
    raise FileNotFoundError(
        f"Neither {DATA_FILE} nor {DATA_FILE_XLSX} found. "
        "Add one of them to this folder with columns: Title, Abstract, Inventor, Link."
    )


def patents_to_context(df: pd.DataFrame) -> str:
    """Turn the DataFrame into a single text block for the LLM context."""
    rows = []
    for i, row in df.iterrows():
        rows.append(
            f"Patent {i + 1}:\n"
            f"  Title: {row.get('Title', '')}\n"
            f"  Abstract: {row.get('Abstract', '')}\n"
            f"  Inventor: {row.get('Inventor', '')}\n"
            f"  Link: {row.get('Link', '')}\n"
        )
    return "\n".join(rows)


def ask_claude(user_question: str, context: str) -> str:
    """Send user question + patent context to Claude and return the reply."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
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
    st.caption("Ask questions about USU patents. Data is loaded from a local CSV or Excel file.")

    try:
        df = load_patents()
        context = patents_to_context(df)
        st.sidebar.success(f"Loaded {len(df)} patent(s) from {DATA_FILE if os.path.exists(DATA_FILE) else DATA_FILE_XLSX}.")
    except FileNotFoundError as e:
        st.error(str(e))
        st.stop()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask a question about the patents..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                reply = ask_claude(prompt, context)
            st.markdown(reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})


if __name__ == "__main__":
    main()
