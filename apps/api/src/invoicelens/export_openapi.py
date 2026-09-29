"""Print the FastAPI OpenAPI contract without starting a database or worker."""

import json
import sys

from .main import app


def main() -> None:
    json.dump(app.openapi(), sys.stdout, ensure_ascii=False, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
