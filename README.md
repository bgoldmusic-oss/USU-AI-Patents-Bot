# USU Patents Research Intelligence

Streamlit chatbot that answers questions about USU Patents using a local CSV/Excel file and Anthropic Claude.

## Setup (one-time)

1. **Create a virtual environment (recommended):**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

   If any package fails, install individually:
   ```bash
   pip install streamlit pandas openpyxl anthropic python-dotenv
   ```

3. **Set your Anthropic API key:**
   - Copy `.env.example` to `.env`
   - Edit `.env` and set `ANTHROPIC_API_KEY=sk-ant-...` (get a key from https://console.anthropic.com/)

## Data

- Put your patent data in **`patents.csv`** or **`patents.xlsx`** in this folder.
- Required columns: **Title**, **Abstract**, **Inventor**, **Link**.
- The app loads all rows and sends them as context to Claude (no vector DB).

## Run the app

```bash
streamlit run app.py
```

Then open the URL shown in the terminal (usually http://localhost:8501).
