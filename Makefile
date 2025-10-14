PYTHON ?= python3
VENV ?= .venv

.PHONY: help start scrape init-db venv

help:
	@echo "Makefile targets:"
	@echo "  start    - create venv (if missing), install deps and start the Flask app"
	@echo "  scrape   - run the scraper (uses utils/run.py if available)"
	@echo "  init-db  - create the SQLite DB directory and ensure DB exists"

start: venv
	$(VENV)/bin/$(PYTHON) app.py


scrape: venv
	# Use top-level main.py to run the scraper (delegates to utils/run.py)
	if [ -f main.py ]; then \
		$(VENV)/bin/$(PYTHON) main.py --config config.json; \
	else \
		echo "No main.py entrypoint found."; exit 1; \
	fi

init-db:
	# Ensure data directory and create DB using the create_db target (avoids here-doc issues)
	@mkdir -p data
	@$(MAKE) create_db

venv:
	if [ ! -d $(VENV) ]; then \
		python3 -m venv $(VENV); \
		$(VENV)/bin/pip install -U pip; \
		$(VENV)/bin/pip install -r requirements.txt; \
	else \
		echo "Virtualenv exists: $(VENV)"; \
	fi

# Define the database path from the config or use a safe relative default
# You can override by running: make DB_PATH=/path/to/db create_db
DB_PATH ?= ./data/linkedinscraper.db

.PHONY: create_db reset_db

# Command to create the database directory if it doesn't exist
create_db_dir:
	@mkdir -p $(dir $(DB_PATH))

# Command to create the database
create_db: create_db_dir
	@echo "Creating database..."
	@sqlite3 $(DB_PATH) "CREATE TABLE IF NOT EXISTS jobs ( \
		id INTEGER PRIMARY KEY AUTOINCREMENT, \
		title TEXT NOT NULL, \
		company TEXT NOT NULL, \
		location TEXT NOT NULL, \
		description TEXT, \
		posted_date TEXT, \
		date TEXT, \
		job_url TEXT NOT NULL, \
		job_description TEXT, \
		date_loaded TEXT, \
		hidden INTEGER DEFAULT 0, \
		applied INTEGER DEFAULT 0, \
		interview INTEGER DEFAULT 0, \
		rejected INTEGER DEFAULT 0, \
		cover_letter TEXT, \
		resume TEXT, \
		confidence_score INTEGER DEFAULT 0, \
		analysis TEXT \
	);"
	@echo "Database created successfully."

# Command to reset the database
reset_db: create_db_dir
	@echo "Resetting database..."
	@rm -f $(DB_PATH)
	@$(MAKE) create_db
	@echo "Database reset successfully."

# Command to clone the database with a timestamp
clone_db:
	@echo "Cloning database..."
	@cp $(DB_PATH) $(dir $(DB_PATH))db_`date +%Y%m%d_%H%M%S`_clone.sqlite
	@echo "Database cloned successfully as db_`date +%Y%m%d_%H%M%S`_clone.sqlite"

# Command to run the script without the scheduler
run_bot:
	@echo "Running script without schedule..."
	@python3 main.py

# Command to run the script with the scheduler
run_scheduled_bot:
	@echo "Running script with schedule..."
	@python3 main.py schedule.json

# Command to clean out log folder
clean_logs:
	@echo "Cleaning logs..."
	@rm -rf logs/*
	@echo "Logs cleaned successfully."

# Create command to create resume
