from pathlib import Path
import json
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
OUTPUT_CSV = BASE_DIR / "drp_combined.csv"


def read_json_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read().strip()

    if not content:
        return []

    # First try normal JSON: [...] or {...}
    try:
        data = json.loads(content)

        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            return [data]

    except json.JSONDecodeError:
        pass

    # Otherwise try JSON Lines / NDJSON
    records = []

    for line_number, line in enumerate(content.splitlines(), start=1):
        line = line.strip()

        if not line:
            continue

        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as e:
            print(
                f"Invalid JSON in {file_path.name}, "
                f"line {line_number}: {e}"
            )

    return records


def main():
    json_files = sorted(DOWNLOAD_DIR.glob("*.json"))

    print(f"Found {len(json_files)} JSON files.")

    rows = []
    files_with_data = 0
    empty_files = []

    for file_path in json_files:
        try:
            records = read_json_file(file_path)

            if not records:
                empty_files.append(file_path.name)
                continue

            files_with_data += 1

            for record in records:
                record["source_file"] = file_path.name
                rows.append(record)

        except Exception as e:
            print(f"Error reading {file_path.name}: {e}")

    if not rows:
        print("No data found.")
        return

    df = pd.json_normalize(rows)

    df.to_csv(
        OUTPUT_CSV,
        index=False,
        encoding="utf-8-sig"
    )

    print("\nDone!")
    print(f"JSON files found: {len(json_files)}")
    print(f"Files with data: {files_with_data}")
    print(f"Empty/unreadable files: {len(empty_files)}")
    print(f"Publication rows: {len(df)}")
    print(f"CSV saved to: {OUTPUT_CSV}")

    if empty_files:
        print("\nFiles with no records:")
        for filename in empty_files:
            print(f"  - {filename}")


if __name__ == "__main__":
    main()