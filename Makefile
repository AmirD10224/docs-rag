.PHONY: help install fetch-samples format lint typecheck test cov ci eval eval-live demo clean

help:
	@echo "DocsRAG. common targets"
	@echo "  make install        Install Python deps via uv"
	@echo "  make fetch-samples  Download the 3 sample PDFs into data/samples/"
	@echo "  make format         Format with ruff"
	@echo "  make lint           Lint with ruff"
	@echo "  make typecheck      Run mypy --strict"
	@echo "  make test           Run pytest with coverage"
	@echo "  make ci             format check + lint + typecheck + test"
	@echo "  make eval           Run evals (mock providers)"
	@echo "  make eval-live      Run evals (live providers. spends real credits)"
	@echo "  make demo           MOCK_PROVIDERS=true uvicorn (offline demo)"

install:
	uv sync --all-extras

fetch-samples:
	@mkdir -p data/samples
	@echo "Fetching sample documents into data/samples/..."
	@curl -fsSL -o data/samples/attention_is_all_you_need.pdf https://arxiv.org/pdf/1706.03762
	@curl -fsSL -o data/samples/apple_10k_fy2024.pdf https://www.apple.com/newsroom/pdfs/fy2024-q4/FY24_Q4_Consolidated_Financial_Statements.pdf
	@curl -fsSL -o data/samples/gitlab_msa.pdf https://about.gitlab.com/handbook/legal/subscription-agreement/main-subscription-agreement-08-21-2018.pdf || \
		echo "GitLab MSA fetch failed. supply your own MSA PDF as data/samples/gitlab_msa.pdf"
	@ls -lh data/samples/

format:
	uv run ruff format backend evals

format-check:
	uv run ruff format --check backend evals

lint:
	uv run ruff check backend evals

lint-fix:
	uv run ruff check --fix backend evals

typecheck:
	uv run mypy --strict backend/docs_rag evals

test:
	uv run pytest

cov:
	uv run pytest --cov-report=html

ci: format-check lint typecheck test

eval:
	PYTHONPATH=backend:. uv run python evals/run.py

eval-live:
	PYTHONPATH=backend:. uv run python evals/run.py --live

demo:
	MOCK_PROVIDERS=true uv run uvicorn docs_rag.main:app --reload --app-dir backend

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov coverage.xml .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
