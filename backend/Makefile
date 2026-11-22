.PHONY: test lint check server simulate

test:
	.venv/bin/python -m pytest -q

lint:
	.venv/bin/python -m ruff check app tests simulator

check:
	.venv/bin/python -m compileall -q app tests
	.venv/bin/python -c "import app.main; print('app.main OK')"

server:
	.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

simulate:
	.venv/bin/python -m simulator.simulate $(SIM_ARGS)
