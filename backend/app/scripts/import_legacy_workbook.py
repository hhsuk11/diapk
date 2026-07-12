import json
import sys
from dataclasses import asdict
from pathlib import Path

from app.db.session import SessionLocal
from app.services.importer import import_legacy_workbook


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print(
            "Usage: python -m app.scripts.import_legacy_workbook <workbook.xlsx>",
            file=sys.stderr,
        )
        return 2

    with SessionLocal() as db:
        result = import_legacy_workbook(Path(args[0]), db)

    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
