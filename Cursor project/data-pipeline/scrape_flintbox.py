import time
import random
import argparse
from pathlib import Path
from typing import Optional, Dict, List

import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException


# Path to your input Excel file
INPUT_FILE = "Patents Database.xlsx"  # update if your file has a different name/path

# Output Excel name
OUTPUT_EXCEL = "Patents_Full_Data.xlsx"

# Column in the sheet that contains the Flintbox URLs
FLINTBOX_URL_COLUMN = "Flintbox Link"

# Target columns to populate from the Flintbox page
TARGET_COLUMNS = [
    "Problem",
    "Solution",
    "Abstract",
    "Benefit",
    "Market Application",
    "Problem 1",
    "Solution 1",
    "Benefit 1",
    "Publications",
    "Other",
]

# Keywords used for text-based parsing of sections
# Not every entry has all sections; missing ones stay empty.
SECTION_HEADER_VARIANTS: Dict[str, List[str]] = {
    "Problem": ["problem"],
    "Solution": ["solution"],
    "Abstract": ["abstract", "background"],
    "Benefit": ["benefit", "benefits", "advantage", "advantages", "key benefits"],
    "Market Application": ["market application", "applications", "application", "market application(s)"],
    "Problem 1": ["problem 1", "problem 1:"],
    "Solution 1": ["solution 1", "solution 1:"],
    "Benefit 1": ["benefit 1", "benefit 1:"],
    "Publications": ["publications", "publication", "related publications", "patents and publications"],
    "Other": ["other", "other information", "additional information", "notes", "miscellaneous"],
}


def create_driver() -> webdriver.Chrome:
    """Create a headless Chrome Selenium WebDriver."""
    chrome_options = Options()
    # Headless Chrome
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(30)
    return driver


def get_main_container_text(driver: webdriver.Chrome) -> str:
    """
    Return the text content of the main container of the Flintbox page.

    To be aggressive, this falls back to the full body text if no specific
    main container can be identified.
    """
    candidates = [
        (By.TAG_NAME, "main"),
        (By.CSS_SELECTOR, "[role='main']"),
        (By.CSS_SELECTOR, "div[data-testid='technology-page']"),
        (By.CSS_SELECTOR, "div.MuiContainer-root"),
    ]

    for by, selector in candidates:
        try:
            el = driver.find_element(by, selector)
            text = el.text.strip()
            if text:
                return text
        except NoSuchElementException:
            continue

    # Fallback: entire body
    try:
        body = driver.find_element(By.TAG_NAME, "body")
        return body.text
    except NoSuchElementException:
        return ""


def extract_section_text_from_text(full_text: str, section_name: str) -> str:
    """
    Extract a section by scanning plain text lines for keywords such as
    'Problem', 'Solution', 'Benefit', etc., then collecting subsequent lines
    until another section header is reached.
    """
    if not full_text:
        return ""

    header_variants = SECTION_HEADER_VARIANTS.get(section_name, [])
    if not header_variants:
        return ""

    # Prepare lines
    lines = [ln.strip() for ln in full_text.splitlines() if ln.strip()]
    lower_lines = [ln.lower() for ln in lines]

    # Flatten all keywords to detect boundaries between sections
    all_kw_to_section: Dict[str, str] = {}
    for sec, kws in SECTION_HEADER_VARIANTS.items():
        for kw in kws:
            all_kw_to_section[kw.lower()] = sec

    # Helper to test if a line looks like a section header
    def match_header(line_lower: str, target_keywords: List[str]) -> Optional[str]:
        for kw in target_keywords:
            kw = kw.lower()
            if line_lower.startswith(kw + ":") or line_lower == kw or line_lower.startswith(kw + " "):
                return kw
        return None

    def is_any_header(line_lower: str) -> bool:
        for kw in all_kw_to_section.keys():
            if line_lower.startswith(kw + ":") or line_lower == kw or line_lower.startswith(kw + " "):
                return True
        return False

    start_idx: Optional[int] = None
    header_inline_text: Optional[str] = None

    # Find the header line for this section
    for i, line_lower in enumerate(lower_lines):
        kw = match_header(line_lower, header_variants)
        if kw is not None:
            original_line = lines[i]
            # Capture any inline text after "Keyword:"
            pos = original_line.lower().find(kw)
            after = original_line[pos + len(kw) :]
            if ":" in after:
                after = after.split(":", 1)[1]
            header_inline_text = after.strip(" :-\t")
            start_idx = i + 1
            break

    if start_idx is None:
        return ""

    # Collect until next header for any known section
    collected: List[str] = []
    if header_inline_text:
        collected.append(header_inline_text)

    for j in range(start_idx, len(lines)):
        line_l = lower_lines[j]
        if is_any_header(line_l):
            break
        collected.append(lines[j])

    if not collected:
        return ""

    # Join and deduplicate consecutive duplicates
    result_lines: List[str] = []
    prev = None
    for ln in collected:
        if ln != prev:
            result_lines.append(ln)
        prev = ln

    return "\n".join(result_lines)


def safe_get_url(row_value: object) -> Optional[str]:
    """Convert a cell value to a usable URL string, if possible."""
    if row_value is None:
        return None
    try:
        text = str(row_value).strip()
    except Exception:
        return None
    if not text or text.lower() in ("nan", "none"):
        return None
    return text


def load_input_dataframe() -> pd.DataFrame:
    """Load the input Excel file and normalize column names."""
    path = Path(INPUT_FILE)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

    suffix = path.suffix.lower()
    if suffix not in {".xlsx", ".xls"}:
        raise ValueError(f"Expected an Excel file (.xlsx or .xls), got: {suffix}")

    # Read the specific sheet using openpyxl
    df = pd.read_excel(path, sheet_name="my sheet", engine="openpyxl")
    # Strip any leading/trailing whitespace from column names
    df.columns = df.columns.str.strip()
    return df


def main(max_rows: Optional[int] = None) -> None:
    # Load data
    df = load_input_dataframe()

    # Ensure required columns exist
    if FLINTBOX_URL_COLUMN not in df.columns:
        raise ValueError(f"Expected a column named '{FLINTBOX_URL_COLUMN}' in the input file.")

    for col in TARGET_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    driver = create_driver()
    wait = WebDriverWait(driver, 20)

    try:
        for idx, row in df.iterrows():
            if max_rows is not None and idx >= max_rows:
                break

            try:
                url = safe_get_url(row.get(FLINTBOX_URL_COLUMN))
                if not url:
                    continue

                print(f"Processing row {idx + 1}: {url}")

                try:
                    driver.get(url)
                    # Wait for the page body to load
                    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                    # Allow extra time for dynamic content to render
                    time.sleep(5)

                    # Grab main container text once per page
                    full_text = get_main_container_text(driver)

                    # Extract all sections from the plain text
                    for col in TARGET_COLUMNS:
                        try:
                            section_text = extract_section_text_from_text(full_text, col)
                        except Exception as exc:
                            print(f"  Error extracting section '{col}' from {url}: {exc}")
                            section_text = ""

                        if section_text:
                            df.at[idx, col] = section_text

                except (TimeoutException, WebDriverException) as exc:
                    print(f"  Error loading {url}: {exc}")

                # Small delay between requests to be polite
                time.sleep(2.0 + random.uniform(0.0, 1.0))

            except Exception as exc:
                # Catch-all so that a single bad row doesn't stop the whole run.
                print(f"Unexpected error on row {idx + 1}: {exc}")

    finally:
        driver.quit()

    # Save the updated data to a new Excel file
    df.to_excel(OUTPUT_EXCEL, index=False)
    print(f"Saved updated data to '{OUTPUT_EXCEL}'.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape Problem/Solution/Benefit from Flintbox links.")
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Maximum number of rows to process (for testing). Omit to process all rows.",
    )
    args = parser.parse_args()

    main(max_rows=args.max_rows)

