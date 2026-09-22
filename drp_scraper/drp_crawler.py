# Scrapes researcher data from DRP using ORCID values

from pathlib import Path

import pandas as pd
from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
)


# Paths and configuration
URL = "https://local.forskningsportal.dk/search/78730"

BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "person.CSV - ExpertsWithORCid.csv"
DOWNLOAD_DIR = BASE_DIR / "downloads"


def safe_filename(text: str, max_len: int = 120) -> str:
    # Make researcher names safe to use as filenames
    cleaned = "".join(
        c if c.isalnum() or c in (" ", "-", "_") else "_"
        for c in str(text)
    )

    cleaned = "_".join(cleaned.split())

    return cleaned[:max_len] if cleaned else "export"


def choose_orcid(page):
    # Select ORCID as the search field
    dropdown = page.locator("select").first
    dropdown.wait_for(state="visible", timeout=15000)

    try:
        dropdown.select_option(label="ORCID")
        print("Selected search field: ORCID")
        return

    except Exception:
        pass

    # Fallback in case exact label selection fails
    options = dropdown.locator("option")

    for i in range(options.count()):
        option = options.nth(i)

        label = option.inner_text().strip()
        value = option.get_attribute("value")

        if "orcid" in label.lower():
            dropdown.select_option(value=value)

            print(f"Selected search field via fallback: {label}")

            return

    raise RuntimeError(
        "Could not find 'ORCID' in the dropdown."
    )


def fill_search_value(page, orcid: str):
    # Find the visible search input and enter the ORCID
    text_inputs = page.locator("input[type='text']")

    if text_inputs.count() == 0:
        raise RuntimeError("No text input found.")

    for i in range(text_inputs.count()):
        inp = text_inputs.nth(i)

        if inp.is_visible():
            inp.fill("")
            inp.fill(orcid)

            print(f"Filled search with ORCID: {orcid}")

            return

    raise RuntimeError(
        "No visible text input found."
    )


def click_search(page):
    # Submit the search
    search_button = page.get_by_role(
        "button",
        name="Search",
    )

    search_button.wait_for(
        state="visible",
        timeout=15000,
    )

    search_button.click()

    print("Clicked Search")

    # Give DRP time to load the results
    page.wait_for_timeout(3000)


def export_results(page, output_dir: Path, stem: str):
    # Open the export menu
    export_button = page.get_by_role(
        "button",
        name="Export Results",
    )

    export_button.wait_for(
        state="visible",
        timeout=15000,
    )

    export_button.scroll_into_view_if_needed()
    page.wait_for_timeout(500)

    export_button.click(force=True)

    print("Clicked Export Results")

    # Select the JSON records export
    json_option = page.get_by_text(
        "List of JSON records",
        exact=False,
    )

    json_option.wait_for(
        state="visible",
        timeout=15000,
    )

    with page.expect_download(timeout=60000) as download_info:
        json_option.click()

    print("Clicked: List of JSON records")

    download = download_info.value

    # DRP uses .lst for this export, so save it explicitly as .json
    target = output_dir / f"{stem}.json"

    download.save_as(str(target))

    if not target.exists():
        raise RuntimeError(
            f"Download was triggered but file was not saved: {target}"
        )

    print(f"Saved JSON: {target}")

    return target


def main():
    print("Looking for CSV at:", CSV_PATH)
    print("CSV exists:", CSV_PATH.exists())

    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"CSV not found: {CSV_PATH}"
        )

    # Create the downloads folder if it does not already exist
    DOWNLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Load researcher data
    df = pd.read_csv(CSV_PATH)

    print("CSV columns:", df.columns.tolist())

    if "orcid" not in df.columns:
        raise ValueError(
            "CSV must contain a column named 'orcid'."
        )

    # Remove researchers without an ORCID
    df = df.dropna(subset=["orcid"]).copy()

    df["orcid"] = (
        df["orcid"]
        .astype(str)
        .str.strip()
    )

    df = df[df["orcid"] != ""]

    if df.empty:
        raise ValueError(
            "No non-empty ORCID values found."
        )

    print(f"Researchers to process: {len(df)}")

    # Start browser
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            slow_mo=300,
        )

        context = browser.new_context(
            accept_downloads=True,
        )

        page = context.new_page()

        # Search and export each researcher
        for idx, row in enumerate(
            df.itertuples(index=False),
            start=1,
        ):
            orcid = str(row.orcid).strip()

            first_name = str(
                getattr(row, "firstName", "")
            ).strip()

            last_name = str(
                getattr(row, "lastName", "")
            ).strip()

            full_name = f"{first_name} {last_name}".strip()

            print(
                f"\n[{idx}/{len(df)}] "
                f"{full_name} | ORCID: {orcid}"
            )

            # Use researcher name and ORCID for the output filename
            if full_name:
                stem = safe_filename(
                    f"{full_name}_{orcid}"
                )
            else:
                stem = safe_filename(orcid)

            expected_file = DOWNLOAD_DIR / f"{stem}.json"

            try:
                # Open a fresh DRP search page
                page.goto(
                    URL,
                    wait_until="domcontentloaded",
                    timeout=60000,
                )

                page.wait_for_timeout(2000)

                # Search by ORCID
                choose_orcid(page)
                fill_search_value(page, orcid)
                click_search(page)

                # Export results
                downloaded_file = export_results(
                    page,
                    DOWNLOAD_DIR,
                    stem,
                )

                print(f"SUCCESS: {full_name}")
                print(f"File: {downloaded_file.name}")

            except PlaywrightTimeoutError as e:
                print(
                    f"TIMEOUT: {full_name} | "
                    f"{orcid} | {e}"
                )

                # A timeout can occur after the download has completed
                if expected_file.exists():
                    print(
                        "JSON exists despite timeout. "
                        "Treating as successful."
                    )
                    continue

                # Save screenshot for failed searches
                screenshot_path = (
                    DOWNLOAD_DIR
                    / f"{stem}_timeout.png"
                )

                try:
                    page.screenshot(
                        path=str(screenshot_path),
                        full_page=True,
                    )

                    print(
                        f"Saved timeout screenshot: "
                        f"{screenshot_path}"
                    )

                except Exception as screenshot_error:
                    print(
                        "Could not save screenshot:",
                        screenshot_error,
                    )

            except Exception as e:
                print(
                    f"FAILED: {full_name} | "
                    f"{orcid} | {e}"
                )

                # Do not mark as failed if the file was downloaded
                if expected_file.exists():
                    print(
                        "JSON exists despite error. "
                        "Treating as successful."
                    )
                    continue

                screenshot_path = (
                    DOWNLOAD_DIR
                    / f"{stem}_error.png"
                )

                try:
                    page.screenshot(
                        path=str(screenshot_path),
                        full_page=True,
                    )

                    print(
                        f"Saved error screenshot: "
                        f"{screenshot_path}"
                    )

                except Exception as screenshot_error:
                    print(
                        "Could not save screenshot:",
                        screenshot_error,
                    )

        context.close()
        browser.close()

    print(
        f"\nScraping finished. "
        f"Downloads saved to: {DOWNLOAD_DIR}"
    )


if __name__ == "__main__":
    main()