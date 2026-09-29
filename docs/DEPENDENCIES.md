# Dependencies and redistribution review

Test environment: Windows, CPython 3.12.13, uv 0.11.28, Node.js 24.18.0, pnpm 11.19.0, and Docker Desktop 4.49.0 / Engine 28.5.1. `apps/api/uv.lock` and `apps/web/pnpm-lock.yaml` resolve exact package versions; `uv sync --frozen` and `pnpm install --frozen-lockfile` are the intended install commands. The Compose tags are exact: `postgres:17.11-alpine3.24`, `python:3.12.13-slim-bookworm`, `node:24.21.0-bookworm-slim`, and [`caddy:2.11.4-alpine`](https://hub.docker.com/_/caddy). Both images built and the local Compose stack passed the health/proxy smoke; the managed shell needed approved access to the Docker socket.

Key installed API versions reported during local testing: FastAPI 0.141.1, SQLAlchemy 2.1.1, Alembic 1.20.0, LangChain 1.4.2, LangGraph 1.2.12, pypdfium2 5.13.0, Pillow 12.3.0, openpyxl 3.1.5, argon2-cffi 25.1.0, and ty 0.0.84 for Python type checking. The synthetic generator also used ReportLab 4.5.1 and Poppler `pdftoppm` 26.05.0. Its documents use generated shapes/text and PDF Helvetica, with no external logos, photos, or design assets. The complete Windows OCR benchmark used [Tesseract 5.5.3.20260724](https://github.com/UB-Mannheim/tesseract/wiki) and the official [English `tessdata_fast` model](https://github.com/tesseract-ocr/tessdata_fast); both were extracted into ignored project-local `tmp`, outside the shipped source and lockfiles. `OMP_THREAD_LIMIT=1` bounded OCR CPU use. The final frontend dependency versions are in its lockfile; run `pnpm -C apps/web list --depth 0` when verifying a release build.

## Licensing decisions

| Component | Observed license position | Distribution action |
|---|---|---|
| [pypdfium2](https://github.com/pypdfium2-team/pypdfium2#licensing) | Apache-2.0 / BSD-3-Clause for bindings; bundled PDFium and other notices apply | Keep the wheel's PDFium/dependency notices with a distributed image. Check the exact wheel build. |
| [Pillow](https://github.com/python-pillow/Pillow/blob/main/LICENSE) | MIT-CMU/PIL license | Preserve its copyright and license notice. |
| [ReportLab open-source toolkit](https://docs.reportlab.com/developerfaqs/) | BSD license | Preserve notice if bundling generator dependencies; do not confuse with commercial ReportLab PLUS. |
| [Tesseract OCR](https://github.com/tesseract-ocr/tesseract/blob/main/LICENSE) | Apache-2.0 for the engine; its dependencies and [English trained-data model](https://github.com/tesseract-ocr/tessdata_fast/blob/main/LICENSE) have separate notices | Review exact Windows/Debian package, language-data, and transitive notices before redistribution. The portable benchmark copy is not part of the repository. |
| [Poppler `pdftoppm`](https://gitlab.com/freedesktop-sdk/mirrors/freedesktop/poppler/poppler) | GPL-licensed development-time rasterizer for synthetic fixture generation; not installed in the API image | Check obligations before distributing a bundled binary with the generator. |
| [Caddy](https://github.com/caddyserver/caddy/blob/master/LICENSE) | Apache-2.0 web server in the production web image | Preserve the image's bundled notices and review its transitive packages before redistribution. |

We avoided PyMuPDF in the runtime because its [official licensing](https://github.com/pymupdf) is AGPL-3.0 or a commercial Artifex license. This is a licensing design decision, not legal certification. Before selling or redistributing a container or installer, generate a complete transitive software bill of materials, retain notices for the exact wheels/npm packages/base images, and have the chosen distribution model reviewed. The direct-dependency review above does not establish third-party rights for every transitive package.

## Version and API references

The LangChain adapter uses [model structured output](https://docs.langchain.com/oss/python/langchain/structured-output) with a Pydantic schema. The workflow uses documented [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) and [persistence](https://docs.langchain.com/oss/python/langgraph/persistence). Package upgrades require re-running migration, extraction/evidence, retry/concurrency, export, and browser checks; do not assume a semver-compatible upgrade preserves model or OCR behavior.
