from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.db import SessionLocal, init_db
from app.services.raw_dataset_archive import archive_dataset_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive a raw Excel dataset into the database.")
    parser.add_argument("--input", required=True, help="Path to the .xlsx/.xls source file")
    parser.add_argument("--dataset-key", required=True, help="Stable dataset key")
    parser.add_argument("--title", required=True, help="Human-readable dataset title")
    parser.add_argument("--dataset-type", required=True, help="Dataset type, e.g. adjustment_snapshot")
    parser.add_argument("--summary-json", default=None, help="Optional path to a summary JSON file")
    parser.add_argument("--notes", default=None, help="Optional notes stored with the dataset")
    args = parser.parse_args()

    summary_json = {}
    if args.summary_json:
        summary_json = json.loads(Path(args.summary_json).expanduser().read_text(encoding="utf-8"))

    init_db()
    with SessionLocal() as db:
        archive = archive_dataset_file(
            db,
            dataset_key=args.dataset_key,
            title=args.title,
            dataset_type=args.dataset_type,
            input_path=Path(args.input),
            summary_json=summary_json,
            notes=args.notes,
        )
        db.commit()
        print(
            json.dumps(
                {
                    "id": archive.id,
                    "dataset_key": archive.dataset_key,
                    "title": archive.title,
                    "dataset_type": archive.dataset_type,
                    "source_filename": archive.source_filename,
                    "workbook_format": archive.workbook_format,
                    "total_rows": archive.total_rows,
                    "total_columns": archive.total_columns,
                    "file_size_bytes": archive.file_size_bytes,
                    "sheet_names": archive.sheet_names,
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
