.PHONY: test lint check server

test:
	.venv/bin/python -m pytest -q

lint:
	.venv/bin/python -m ruff check app tests

check:
	.venv/bin/python -m compileall -q app tests
	.venv/bin/python -c "import app.main; print('app.main OK')"

server:
	.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
