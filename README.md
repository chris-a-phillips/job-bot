
## Table of Contents
- [LinkedIn Job Scraper](#linkedIn-job-scraper)
- [Problem](#problem)
- [IMPORTANT NOTE](#important-note)
- [Prerequisites](#prerequisites)
# job-bot

A LinkedIn job-scraper, local job database, and small web UI with optional OpenAI-powered resume tailoring and cover-letter generation.

This repository contains tools to scrape LinkedIn job results, filter and store them in a local SQLite database, review and mark jobs using a lightweight Flask web UI, and (optionally) generate tailored cover letters using OpenAI.

## Table of contents
- About
- Features
- Security & legal notice
- Quick start
- Configuration
- Usage
  - Scraper
  - Web UI
  - Resume & OpenAI features
- Development
- Tests
- Troubleshooting
- Contributing
- License

## About

job-bot is a personal productivity tool to make finding and applying to jobs faster. It scrapes LinkedIn search results (locally), deduplicates and filters postings according to user-configurable rules, and stores results in a SQLite database you control. The included Flask UI makes it easy to triage jobs and track application status.

This project is intended for personal use and experimentation. It is not an official LinkedIn product.

## Features

- Scrape LinkedIn search result pages and store job postings in SQLite
- Filter jobs by title, description, company, language, and custom keywords
- Basic web UI (Flask) to view jobs and mark them applied / rejected / interview / hidden
- Optional OpenAI integration to parse your resume and generate tailored cover letters
- Configurable proxies, headers and scraping parameters

## Security & legal notice

- LinkedIn's Terms of Service prohibit scraping. Use this project at your own risk. Consider the legal and ethical implications before running the scraper.
- Use proxies and rotate user-agents to reduce the risk of being blocked. The project includes support for proxy configuration but does not ship or recommend proxies.
- Do not commit API keys, credentials, or personal data to the repository. Use `config.json` (gitignored) and environment variables.

## Quick start

1. Clone the repo:

      git clone https://github.com/chris-a-phillips/job-bot.git
      cd job-bot

2. Install dependencies (recommended: use a virtualenv or pipenv)

      python3 -m venv .venv
      source .venv/bin/activate
      pip install -r requirements.txt

3. Copy the example config and edit it:

      cp config_example.json config.json
      # edit config.json with your preferred search queries, proxy and OpenAI settings

4. Populate the database (run the scraper once):

      python app.py --init-db

      # or run the scraper directly (see Configuration / Usage)

5. Start the web UI:

      python app.py

6. Open your browser at: http://127.0.0.1:5000

Notes:
- The repo contains `config_example.json` as a starting point. Keep your real API keys and secrets out of version control.

## Configuration

The primary configuration file is `config.json` at the repository root. A template is provided in `config_example.json`.

Important fields (high level):

- proxies: { "http": "http://...", "https": "socks5://..." } (optional) — set this if you use proxies
- headers: { "User-Agent": "..." } — recommended to set a realistic UA
- OpenAI_API_KEY: string (optional) — used for resume parsing and cover-letter generation
- OpenAI_Model: string (optional) — model name to use for generation (e.g., gpt-4o or gpt-4)
- resume_path: path to your resume PDF (optional)
- search_queries: list of search objects each with keywords, location, and optional filters (f_WT, f_SB2, timespan, pages_to_scrape)
- title_include / title_exclude / desc_words / company_exclude: lists of keywords to include/exclude
- db_path: path to the SQLite database file (default: data/linkedinscraper.db)
- pages_to_scrape / rounds / days_toscrape: scraping control parameters

See `config_example.json` for a concrete example.

### OpenAI integration

If you set `OpenAI_API_KEY`, the repo can:

- Parse your resume (PDF) and extract a plain-text representation for better prompts
- Generate a tailored cover letter for a selected job

Security tips:

- Don't store API keys in the repo. Use environment variables or `config.json` that is excluded from Git.

## Usage

This project has three main flows: scraping, reviewing via the web UI, and generating cover letters.

### Scraper

The scraper implementation lives in the utils and input packages. The main entry point historically was `main.py` (older versions) but this repo uses `app.py` to provide both initialization and the web server. To run the scraper directly, look for the `run.py` scripts in `utils/`.

Typical scraping run (example):

      python utils/run.py --config config.json

Or run the legacy entrypoint if present:

      python main.py

The scraper will insert new jobs into the configured SQLite DB and apply filters from `config.json`.

### Web UI

Start the Flask app:

      python app.py

The UI provides a table of jobs and simple actions (apply / reject / interview / hide). Actions persist to the SQLite DB. The HTML templates are in `templates/` and static JS is in `static/`.

### Resume parsing & cover-letter generation

If `OpenAI_API_KEY` is configured and `resume_path` points to a PDF, the resume tools under `utils/resume/` can parse and prepare prompts for the OpenAI model. The UI includes actions to generate a cover letter for a selected job using the resume and job description as context.

## Development

Project layout (important files and folders):

- `app.py` - Flask application and lightweight CLI
- `utils/` - helper scripts (scraper runner, resume tools, etc.)
- `data/` - generated artifacts and the SQLite DB (data/linkedinscraper.db)
- `input/` - constants and job description templates
- `static/`, `templates/` - web UI assets
- `tests/` - unit tests

If you change dependencies, update `requirements.txt` and `Pipfile`/`pyproject.toml` as needed.

## Tests

Run unit tests with the project's test runner. This repo includes a minimal pytest setup. To run tests:

      pytest -q

Or run the single test file included:

      pytest tests/test_proxy_connection.py::test_proxy_connection -q

If you run into failures, check the test output for missing environment variables or required services (some tests may expect network access).

## Troubleshooting

- Database locked errors: make sure no other process is writing to the SQLite DB. Delete the `.db` if you want to start fresh (backup first).
- Scraper blocked / 429 errors: rotate proxies, lower request rate, change user-agent.
- Resume parsing issues: use a simple, single-column PDF resume for best results.

## Contributing

Contributions are welcome. Suggested workflow:

1. Open an issue to discuss significant changes.
2. Create a branch for your change (e.g., feature/xyz).
3. Add tests for new behavior and run `pytest`.
4. Open a pull request and reference the issue.

Please keep secrets out of commits and include clear commit messages.

## License

This project is licensed under the MIT License. See `LICENSE` for details.

## Acknowledgements

- Built for personal productivity and experimentation.
- Uses BeautifulSoup, Requests, Flask, Pandas, and OpenAI (optional).

---

If you'd like, I can also:

- Add an example `Makefile` target to run the scraper and start the UI
- Improve `config_example.json` to show a minimal, safe configuration
- Add a basic smoke test that starts the Flask app and queries the homepage

Next I'll run the test suite to ensure nothing is broken by this documentation change. (This is quick and shouldn't modify code.)
