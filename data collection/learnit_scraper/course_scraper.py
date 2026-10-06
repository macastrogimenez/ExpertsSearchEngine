import csv
import argparse

from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright


BASE_URL = "https://learnit.itu.dk/local/coursebase/"


# ============================================================
# TEXT HELPERS
# ============================================================

def clean_text(text: Optional[str]) -> str:
    if not text:
        return ""

    return " ".join(
        text.replace("\xa0", " ").split()
    )


def get_text(element, selector: str) -> str:
    try:
        locator = element.locator(selector)

        if locator.count() == 0:
            return ""

        return clean_text(
            locator.first.text_content()
        )

    except Exception:
        return ""


# ============================================================
# MAIN COURSE CARD
# ============================================================

def get_fact_value(card, selector: str) -> str:
    try:
        fact = card.locator(selector)

        if fact.count() == 0:
            return ""

        spans = fact.first.locator("span")

        if spans.count() < 2:
            return ""

        values = []

        for i in range(1, spans.count()):
            value = clean_text(
                spans.nth(i).text_content()
            )

            if value:
                values.append(value)

        return clean_text(
            " ".join(values)
        )

    except Exception:
        return ""


def get_course_summary(card) -> str:
    return get_text(
        card,
        ".cb-abstract",
    )


def get_single_subject(card) -> str:
    try:
        text = clean_text(
            card.text_content()
        ).lower()

        if "offered as a single subject" in text:
            return "Yes"

        return "No"

    except Exception:
        return "No"


def get_guest_students(card) -> str:
    try:
        text = clean_text(
            card.text_content()
        ).lower()

        if "offered to guest students" in text:
            return "Yes"

        return "No"

    except Exception:
        return "No"


# ============================================================
# READ MORE
# ============================================================

def get_read_more_url(card) -> str:
    try:
        links = card.locator(
            'a[href*="view=public"][href*="ciid="]'
        )

        for i in range(links.count()):
            link = links.nth(i)

            text = clean_text(
                link.text_content()
            )

            href = (
                link.get_attribute("href")
                or ""
            )

            if (
                text.lower() == "read more"
                and "view=public" in href
                and "ciid=" in href
            ):
                return urljoin(
                    BASE_URL,
                    href,
                )

        return ""

    except Exception:
        return ""


def get_official_sections(
    detail_page,
    url: str,
) -> tuple[str, str]:

    if not url:
        return "", ""

    try:
        detail_page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        detail_page.wait_for_selector(
            ".cb-content",
            timeout=30000,
        )

        sections = detail_page.evaluate(
            """
            () => {
                const container =
                    document.querySelector(
                        ".cb-content"
                    );

                if (!container) {
                    return {
                        abstract: "",
                        description: ""
                    };
                }

                function getSection(name) {
                    const headings =
                        [...container.querySelectorAll("h5")];

                    const heading = headings.find(
                        h =>
                            h.textContent
                                .trim()
                                .toLowerCase()
                            === name.toLowerCase()
                    );

                    if (!heading) {
                        return "";
                    }

                    const parts = [];

                    let node =
                        heading.nextSibling;

                    while (node) {

                        if (
                            node.nodeType === 1
                            && node.tagName === "H5"
                        ) {
                            break;
                        }

                        if (
                            node.nodeType === 1
                            || node.nodeType === 3
                        ) {
                            const text =
                                (node.textContent || "")
                                    .replace(
                                        /\\s+/g,
                                        " "
                                    )
                                    .trim();

                            if (text) {
                                parts.push(text);
                            }
                        }

                        node =
                            node.nextSibling;
                    }

                    return parts.join(" ");
                }

                return {
                    abstract:
                        getSection("Abstract"),

                    description:
                        getSection("Description")
                };
            }
            """
        )

        abstract = clean_text(
            sections.get(
                "abstract",
                "",
            )
        )

        description = clean_text(
            sections.get(
                "description",
                "",
            )
        )

        return abstract, description

    except Exception as exc:
        print(
            f"    Read more extraction failed: {exc}"
        )

        return "", ""


# ============================================================
# SCRAPE CURRENT PAGE
# ============================================================

def scrape_current_page(
    page,
    detail_page,
    remaining_limit=None,
):
    results = []

    cards = page.locator(
        "#data .card.cb-frontend.fjs_item"
    )

    count = cards.count()

    print(
        f"Found {count} course occurrences"
    )

    for i in range(count):

        if (
            remaining_limit is not None
            and len(results) >= remaining_limit
        ):
            break

        card = cards.nth(i)

        title = get_text(
            card,
            ".card-header h5",
        )

        print(
            f"  [{i + 1}/{count}] {title}"
        )

        course_summary = (
            get_course_summary(card)
        )

        ects = get_fact_value(
            card,
            ".cb-ects",
        )

        semester = get_fact_value(
            card,
            ".cb-period",
        )

        language = get_fact_value(
            card,
            ".cb-language",
        )

        exam = get_fact_value(
            card,
            ".cb-exam",
        )

        teacher = get_fact_value(
            card,
            ".cb-teachers",
        )

        programme = get_fact_value(
            card,
            ".cb-studyprogramme",
        )

        single_subject = (
            get_single_subject(card)
        )

        guest_students = (
            get_guest_students(card)
        )

        read_more_url = (
            get_read_more_url(card)
        )

        abstract = ""
        description = ""

        if read_more_url:
            print(
                "    Read more found"
            )

            abstract, description = (
                get_official_sections(
                    detail_page,
                    read_more_url,
                )
            )

            print(
                f"    Abstract: "
                f"{'Yes' if abstract else 'No'}"
            )

            print(
                f"    Description: "
                f"{'Yes' if description else 'No'}"
            )

        results.append(
            {
                "Course Name":
                    title,

                "Course Summary":
                    course_summary,

                "Abstract":
                    abstract,

                "Description":
                    description,

                "ECTS":
                    ects,

                "Semester":
                    semester,

                "Language":
                    language,

                "Exam":
                    exam,

                "Teacher":
                    teacher,

                "Programme":
                    programme,

                "Single Subject":
                    single_subject,

                "Guest Students":
                    guest_students,
            }
        )

    return results


# ============================================================
# RESULTS PER PAGE
# ============================================================

def set_per_page(
    page,
    value="50",
):
    try:
        selects = page.locator(
            "select"
        )

        for i in range(
            selects.count()
        ):
            select = selects.nth(i)

            options = select.locator(
                "option"
            )

            option_texts = []

            for j in range(
                options.count()
            ):
                option_texts.append(
                    clean_text(
                        options.nth(j)
                        .text_content()
                    )
                )

            if value not in option_texts:
                continue

            select.select_option(
                label=value
            )

            page.wait_for_timeout(
                1500
            )

            page.wait_for_selector(
                "#data .card.cb-frontend.fjs_item",
                timeout=30000,
            )

            print(
                f"Results per page set to {value}"
            )

            return

    except Exception as exc:
        print(
            f"Could not change results per page: {exc}"
        )


# ============================================================
# PAGINATION
# ============================================================

def goto_next_page(page) -> bool:
    try:
        next_buttons = page.get_by_text(
            "Next →",
            exact=False,
        )

        if next_buttons.count() == 0:
            next_buttons = (
                page.get_by_text(
                    "Next",
                    exact=True,
                )
            )

        if next_buttons.count() == 0:
            return False

        button = None

        for i in range(
            next_buttons.count()
        ):
            candidate = (
                next_buttons.nth(i)
            )

            if candidate.is_visible():
                button = candidate
                break

        if button is None:
            return False

        cards = page.locator(
            "#data .card.cb-frontend.fjs_item"
        )

        old_first_id = ""

        if cards.count() > 0:
            old_first_id = (
                cards.first
                .get_attribute("id")
                or ""
            )

        button.click()

        if old_first_id:
            try:
                page.wait_for_function(
                    """
                    oldId => {
                        const first =
                            document.querySelector(
                                "#data .card.cb-frontend.fjs_item"
                            );

                        return (
                            first
                            && first.id !== oldId
                        );
                    }
                    """,
                    old_first_id,
                    timeout=30000,
                )

            except Exception:
                page.wait_for_timeout(
                    1500
                )

        else:
            page.wait_for_timeout(
                1500
            )

        page.wait_for_selector(
            "#data .card.cb-frontend.fjs_item",
            timeout=30000,
        )

        return True

    except Exception as exc:
        print(
            f"Pagination failed: {exc}"
        )

        return False


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--out",
        type=Path,
        default=Path(
            "learnit_courses.csv"
        ),
    )

    parser.add_argument(
        "--headless",
        action="store_true",
    )

    parser.add_argument(
        "--max-pages",
        type=int,
        default=200,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
    )

    args = parser.parse_args()

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=args.headless
        )

        context = browser.new_context(
            viewport={
                "width": 1600,
                "height": 1100,
            },
            java_script_enabled=True,
            locale="en-US",
        )

        page = context.new_page()

        detail_page = (
            context.new_page()
        )

        print(
            "Opening LearnIT..."
        )

        page.goto(
            BASE_URL,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        page.wait_for_selector(
            "#data .card.cb-frontend.fjs_item",
            timeout=60000,
        )

        set_per_page(
            page,
            "50",
        )

        all_rows = []

        for page_num in range(
            1,
            args.max_pages + 1,
        ):
            print(
                f"\n=== PAGE {page_num} ==="
            )

            remaining = None

            if args.limit is not None:
                remaining = (
                    args.limit
                    - len(all_rows)
                )

                if remaining <= 0:
                    break

            page_rows = (
                scrape_current_page(
                    page,
                    detail_page,
                    remaining_limit=remaining,
                )
            )

            all_rows.extend(
                page_rows
            )

            print(
                f"Total collected: "
                f"{len(all_rows)}"
            )

            if (
                args.limit is not None
                and len(all_rows)
                >= args.limit
            ):
                break

            if not goto_next_page(
                page
            ):
                print(
                    "No next page found."
                )

                break

        if args.limit is not None:
            all_rows = all_rows[
                :args.limit
            ]

        fieldnames = [
            "Course Name",
            "Course Summary",
            "Abstract",
            "Description",
            "ECTS",
            "Semester",
            "Language",
            "Exam",
            "Teacher",
            "Programme",
            "Single Subject",
            "Guest Students",
        ]

        with args.out.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as f:

            writer = csv.DictWriter(
                f,
                fieldnames=fieldnames,
            )

            writer.writeheader()

            writer.writerows(
                all_rows
            )

        browser.close()

        print(
            "\nDone."
        )

        print(
            f"Wrote {len(all_rows)} "
            f"course occurrences."
        )

        print(
            f"CSV: "
            f"{args.out.resolve()}"
        )


if __name__ == "__main__":
    main()