# config_example.json (annotations)

This file documents the minimal configuration provided in `config_example.json`.

- proxies: object
  - Optional. Configure if you use HTTP / HTTPS or SOCKS proxies.
  - Example: { "http": "http://127.0.0.1:8888", "https": "socks5://127.0.0.1:9050" }

- headers: object
  - Useful to set a realistic User-Agent. Defaults to a simple project UA in the example.

- OpenAI_API_KEY: string
  - Optional. Leave empty if you don't want to use OpenAI features.

- OpenAI_Model: string
  - Optional. The model name to use for cover letter generation (e.g., "gpt-4o").

- resume_path: string
  - Optional path to a local PDF resume used for tailoring prompts. Use a simple, single-column PDF for best results.

- search_queries: array of objects
  - Each object defines a LinkedIn search. Minimal keys: keywords and location. Optional keys include f_WT (work type) and pages_to_scrape.

- desc_words, title_include, title_exclude, company_exclude: arrays
  - Filtering rules to include/exclude jobs based on description, title, or company name.

- languages: array
  - If set, the scraper will discard jobs whose language doesn't match one in this list (e.g., ["en"]).

- timespan: string
  - LinkedIn timespan format like "r604800" (last 7 days). See the README for details.

- jobs_tablename / filtered_jobs_tablename: strings
  - Table names used when creating or querying the SQLite DB.

- db_path: string
  - Path to the SQLite database file. Default in the example is `./data/linkedinscraper.db`.

- pages_to_scrape / rounds / days_to_scrape: integers
  - Control how many pages and rounds to run the scraper for, and how many days back to keep.

Security notes:

- Never commit real `OpenAI_API_KEY` or other secrets to Git. Use environment variables or a `config.json` excluded from version control.
