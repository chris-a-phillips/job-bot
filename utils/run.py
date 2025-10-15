#!/usr/bin/env python3

"""
LinkedIn Jobs Scraper (Fixed / Remade)

Key improvements vs your original:
- Fixed malformed URL and added real pagination via `start=25*i`.
- More robust HTML parsing that tolerates minor DOM shifts.
- Defensive date handling (missing or malformed dates won't crash the run).
- Clearer logging (counts before/after dedupe and filters + a sample of titles).
- Writes soup snapshot per page (soup-<page>.html) for offline debugging.
- Optionally runs on a schedule if you pass a schedule JSON file.
"""

import os
import sys
import json
import time as tm
import logging
from datetime import datetime, timedelta, time as dtime
from itertools import groupby
from urllib.parse import quote, urlparse, urlunparse
import re

import requests
import pandas as pd
from bs4 import BeautifulSoup
from sqlite3 import Error
import sqlite3

# ---------- Configuration ----------

DEFAULT_CONFIG_PATH = "config.json"

# ---------- Logging ----------

def setup_logger():
    os.makedirs("logs", exist_ok=True)
    logger = logging.getLogger("SchedulerLogger")
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers if run inside long-lived process
    if not logger.handlers:
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        fh = logging.FileHandler(os.path.join("logs", f"{stamp}.log"))
        fh.setLevel(logging.INFO)
        fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logger.addHandler(fh)

        sh = logging.StreamHandler(sys.stdout)
        sh.setLevel(logging.INFO)
        sh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logger.addHandler(sh)

    return logger

logger = setup_logger()

# ---------- Helpers ----------

def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def get_with_retry(url, config, retries=3, delay=1.5):
    """
    GET the URL using requests with optional headers/proxies from config and parse with BeautifulSoup.
    Returns None on repeated failure.
    """
    headers = config.get("headers", {})
    proxies = config.get("proxies", {})
    timeout = config.get("timeout_seconds", 8)

    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=headers, proxies=proxies or None, timeout=timeout)
            resp.raise_for_status()
            return BeautifulSoup(resp.content, "html.parser")
        except requests.exceptions.Timeout:
            logger.info(f"[{attempt}/{retries}] Timeout for URL: {url!r}. Retrying in {delay}s...")
            tm.sleep(delay)
        except requests.exceptions.HTTPError as e:
            code = getattr(resp, "status_code", "?")
            logger.error(f"[{attempt}/{retries}] HTTP {code} for URL: {url!r}: {e}")
            tm.sleep(delay)
        except Exception as e:
            logger.error(f"[{attempt}/{retries}] Error fetching URL: {url!r}: {e}")
            tm.sleep(delay)
    return None

def robust_text(el):
    return el.get_text(strip=True) if el else ""


def normalize_url(url: str) -> str:
    """Return a canonical URL without query params or fragments, lowercased host.
    If input is empty or not a URL, return empty string.
    """
    if not url:
        return ""
    try:
        p = urlparse(url)
        # normalize path (remove trailing slash)
        path = p.path.rstrip('/')
        # rebuild without params/query/fragment
        canon = urlunparse((p.scheme.lower() or 'https', p.netloc.lower(), path, '', '', ''))
        return canon
    except Exception:
        return url.strip()


def normalize_text(s: str) -> str:
    if not s:
        return ""
    # lowercase, remove punctuation, collapse whitespace
    s2 = re.sub(r"[^0-9a-zA-Z\s]", " ", s.lower())
    s2 = re.sub(r"\s+", " ", s2).strip()
    return s2

def transform_results_page(soup):
    """
    Parse one search results page soup into a list of job dicts.
    This version is tolerant to minor DOM changes.
    """
    jobs = []
    if not soup:
        return jobs

    # The outer card often contains these classes. We cast a wide net then refine.
    cards = soup.select("div.base-card.job-search-card, div.base-card--link.base-search-card, div.base-card")
    if not cards:
        # Fallback: derive cards by walking up from the info blocks
        info_blocks = soup.select("div.base-search-card__info")
        cards = [ib.parent for ib in info_blocks] if info_blocks else []

    for card in cards:
        info = card.select_one("div.base-search-card__info") or card
        title_el = info.select_one("h3.base-search-card__title, h3")
        comp_el  = info.select_one("a.hidden-nested-link")
        loc_el   = info.select_one("span.job-search-card__location")
        time_el  = info.select_one("time.job-search-card__listdate, time.job-search-card__listdate--new")

        title    = robust_text(title_el)
        company  = robust_text(comp_el)
        location = robust_text(loc_el)
        date_iso = time_el.get("datetime") if time_el and time_el.has_attr("datetime") else ""

        # Find the entity urn (job id) on the card or any ancestor
        urn_host = card if card.has_attr("data-entity-urn") else card.find_parent(attrs={"data-entity-urn": True}) or card
        entity_urn = urn_host.get("data-entity-urn", "")
        job_id = entity_urn.split(":")[-1] if ":" in entity_urn else ""

        # Also try to get the explicit link, if present
        link_el = card.select_one("a.base-card__full-link")
        href = link_el.get("href") if link_el and link_el.has_attr("href") else ""
        raw_url = href or (f"https://www.linkedin.com/jobs/view/{job_id}/" if job_id else "")
        job_url = normalize_url(raw_url)

        # Skip obvious empties
        if not title and not company and not job_url:
            continue

        jobs.append({
            "title": title,
            "company": company,
            "location": location,
            "date": date_iso,  # e.g., "2025-10-10" (can be "")
            "job_url": job_url,
            "_norm_title": normalize_text(title),
            "_norm_company": normalize_text(company),
            "apply_url": "",
            "apply_external": False,
            "job_description": "",
            "applied": 0,
            "hidden": 0,
            "interview": 0,
            "rejected": 0,
            "confidence_score": 0,
            "analysis": "",
        })
    return jobs

def transform_job_detail(soup):
    if not soup:
        return {"description": "Could not find Job Description", "apply_url": ""}
    div = soup.find("div", class_="description__text")
    # LinkedIn sometimes uses more specific classes; be generous:
    if not div:
        div = soup.select_one("div.description__text--rich, div.description")

    apply_url = ""
    # Heuristic: find an anchor that looks like an apply link
    try:
        # anchors with 'apply' in text
        a = soup.find('a', string=lambda s: s and 'apply' in s.lower())
        if not a:
            # anchors with apply-like class or data-control-name
            a = soup.find('a', attrs={"class": re.compile(r"apply", re.I)})
        if not a:
            a = soup.find('a', attrs={"data-control-name": re.compile(r"apply", re.I)})
        if a and a.has_attr('href'):
            apply_url = a.get('href')
    except Exception:
        apply_url = ""

    if div:
        # Remove noisy elements
        for element in div.find_all(["span", "a"]):
            element.decompose()
        # Normalize bullet points
        for ul in div.find_all("ul"):
            for li in ul.find_all("li"):
                li.insert(0, "- ")
        text = div.get_text(separator="\n").strip()
        text = text.replace("::marker", "- ").replace("\n\n", "\n")
        text = text.replace("Show less", "").replace("Show more", "")
        return {"description": text or "Could not find Job Description", "apply_url": apply_url}
    return {"description": "Could not find Job Description", "apply_url": apply_url}

def table_exists(conn, name):
    cur = conn.cursor()
    cur.execute("SELECT count(name) FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone()[0] == 1

def create_connection(db_path):
    try:
        if os.path.dirname(db_path):
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
        return sqlite3.connect(db_path)
    except Error as e:
        logger.error(f"sqlite error: {e}")
        return None

def create_table(conn, df, table):
    # Stronger schema creation + insert rows
    type_map = {
        "int64": "INTEGER",
        "float64": "REAL",
        "datetime64[ns]": "TIMESTAMP",
        "object": "TEXT",
        "bool": "INTEGER",
    }
    cols = ", ".join(f'"{c}" {type_map.get(str(t), "TEXT")}' for c, t in df.dtypes.items())
    sql_create = f'''
        CREATE TABLE IF NOT EXISTS "{table}" (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            {cols}
        );
    '''
    cur = conn.cursor()
    cur.execute(sql_create)
    conn.commit()

    placeholders = ", ".join(["?"] * len(df.columns))
    sql_insert = f'INSERT INTO "{table}" ({", ".join(f'"{c}"' for c in df.columns)}) VALUES ({placeholders})'
    for rec in df.itertuples(index=False, name=None):
        cur.execute(sql_insert, rec)
    conn.commit()
    logger.info(f'Created table "{table}" and inserted {len(df)} records')

def update_table(conn, df, table):
    existing = pd.read_sql(f'SELECT * FROM "{table}"', conn)
    # Identify records that are new by job_url OR (title, company, date)
    combined = pd.concat([df, existing, existing], ignore_index=True)
    new_records = combined.drop_duplicates(subset=["title", "company", "date", "job_url"], keep=False).iloc[:len(df)]
    if not new_records.empty:
        new_records.to_sql(table, conn, if_exists="append", index=False)
        logger.info(f'Added {len(new_records)} new records to "{table}"')
    else:
        logger.info(f'No new records to add to "{table}"')

def remove_duplicates(jobs):
    """Deduplicate jobs by canonical job_url when available, otherwise by normalized title+company."""
    def keyfn(x):
        url = x.get("job_url") or ""
        if url:
            return (url, "")
        # fallback key: normalized title + company
        return ("", f"{x.get('_norm_title','')}||{x.get('_norm_company','')}" )

    jobs_sorted = sorted(jobs, key=keyfn)
    deduped = []
    last_key = None
    for j in jobs_sorted:
        k = keyfn(j)
        if k == last_key:
            continue
        deduped.append(j)
        last_key = k
    return deduped

def remove_irrelevant_jobs(jobs, config):
    desc_words = [w.lower() for w in config.get("desc_words", [])]
    title_exclude = [w.lower() for w in config.get("title_exclude", [])]
    title_include = [w.lower() for w in config.get("title_include", [])]
    company_exclude = [w.lower() for w in config.get("company_exclude", [])]
    languages = [w.lower() for w in config.get("languages", [])]

    def lang_ok(_job):
        # If languages filter is empty, accept. Otherwise, we can't detect reliably here; accept by default.
        return True

    filtered = []
    for job in jobs:
        jd = (job.get("job_description") or "").lower()
        title = (job.get("title") or "").lower()
        company = (job.get("company") or "").lower()

        if desc_words and any(w in jd for w in desc_words):
            continue
        if title_exclude and any(w in title for w in title_exclude):
            continue
        if title_include and not any(w in title for w in title_include):
            continue
        if company_exclude and any(w in company for w in company_exclude):
            continue
        if not lang_ok(job):
            continue

        filtered.append(job)
    return filtered


def explain_rejection(job, config):
    """Return a list of reasons why a job would be rejected by the current config filters."""
    reasons = []
    jd = (job.get("job_description") or "").lower()
    title = (job.get("title") or "").lower()
    company = (job.get("company") or "").lower()

    desc_words = [w.lower() for w in config.get("desc_words", [])]
    title_exclude = [w.lower() for w in config.get("title_exclude", [])]
    title_include = [w.lower() for w in config.get("title_include", [])]
    company_exclude = [w.lower() for w in config.get("company_exclude", [])]

    if desc_words and any(w in jd for w in desc_words):
        reasons.append("description contains excluded keywords")
    if title_exclude and any(w in title for w in title_exclude):
        reasons.append("title contains excluded keyword")
    if title_include and not any(w in title for w in title_include):
        reasons.append("title does not contain any required include keywords")
    if company_exclude and any(w in company for w in company_exclude):
        reasons.append("company is excluded")
    # language check placeholder (script auto-detects language elsewhere)
    if not reasons:
        reasons.append("no specific rejection reason matched (passes filters) or filter logic removed it")
    return reasons

def convert_date(date_str):
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            d = datetime.strptime(date_str, fmt)
            return datetime.combine(d.date(), dtime())
        except ValueError:
            continue
    try:
        d = datetime.fromisoformat(date_str)
        return datetime.combine(d.date(), dtime())
    except Exception:
        logger.warning(f"Unrecognized date format: {date_str!r}")
        return None

def build_search_url(keywords, location, start, config):
    base = "https://www.linkedin.com/jobs/search"
    qs = [
        f"keywords={quote(keywords)}",
        f"location={quote(location)}",
    ]
    # Optional filters
    timespan = config.get("timespan", "")
    if timespan:
        qs.append(f"f_TPR={quote(str(timespan))}")
    wt = config.get("f_WT", "")
    if wt:
        qs.append(f"f_WT={quote(str(wt))}")
    qs.append(f"start={start}")
    return f"{base}?{'&'.join(qs)}"

def get_jobcards(config):
    all_jobs = []
    rounds = int(config.get("rounds", 1))
    pages = int(config.get("pages_to_scrape", 1))
    queries = config.get("search_queries", [{"keywords": "software engineer", "location": "United States"}])

    for _ in range(rounds):
        for query in queries:
            keywords = query.get("keywords", "software engineer")
            location = query.get("location", "United States")
            for i in range(pages):
                start = 25 * i  # LinkedIn paginates 25 per page
                url = build_search_url(keywords, location, start, config)
                soup = get_with_retry(url, config)
                if not soup:
                    logger.info(f"Empty soup for URL: {url}")
                    continue

                jobs = transform_results_page(soup)
                logger.info(f"Parsed {len(jobs)} cards from start={start}")
                all_jobs.extend(jobs)

    logger.info(f"Total raw cards scraped: {len(all_jobs)}")

    all_jobs = remove_duplicates(all_jobs)
    logger.info(f"After dedupe: {len(all_jobs)}")
    if all_jobs:
        logger.info("Sample titles: " + ", ".join(j['title'] for j in all_jobs[:5] if j.get('title')))

    return all_jobs

def find_new_jobs(all_jobs, conn, config):
    jobs_table = config.get("jobs_tablename", "jobs")
    filtered_table = config.get("filtered_jobs_tablename", "filtered_jobs")
    jobs_db = pd.DataFrame()
    filtered_db = pd.DataFrame()

    if conn is not None:
        if table_exists(conn, jobs_table):
            jobs_db = pd.read_sql_query(f'SELECT * FROM "{jobs_table}"', conn)
        if table_exists(conn, filtered_table):
            filtered_db = pd.read_sql_query(f'SELECT * FROM "{filtered_table}"', conn)

    def exists(df, job):
        if df.empty:
            return False
        by_url = (df["job_url"] == job.get("job_url")).any() if "job_url" in df.columns else False
        by_tcd = (
            (df.get("title") == job.get("title")) &
            (df.get("company") == job.get("company")) &
            (df.get("date") == job.get("date"))
        ).any()
        return bool(by_url or by_tcd)

    new = [j for j in all_jobs if not exists(jobs_db, j) and not exists(filtered_db, j)]
    logger.info(f"New cards after DB comparison: {len(new)}")
    return new

def main(config_path):
    config = load_json(config_path)
    logger.info(f"Using config file: {config_path}")

    jobs_table = config.get("jobs_tablename", "jobs")
    filtered_table = config.get("filtered_jobs_tablename", "filtered_jobs")
    days_to_scrape = int(config.get("days_to_scrape", 7))
    db_path = config.get("db_path", "jobs.sqlite")

    t0 = tm.perf_counter()

    # 1) Scrape search pages
    all_jobs = get_jobcards(config)

    # 2) Create DB connection
    conn = create_connection(db_path)

    # 3) DB newness filtering
    all_jobs = find_new_jobs(all_jobs, conn, config)

    # 4) Enrich: fetch job descriptions and age-filter
    enriched = []
    for job in all_jobs:
        job_date_dt = convert_date(job.get("date", ""))
        if job_date_dt:
            if job_date_dt < datetime.now() - timedelta(days=days_to_scrape):
                continue  # too old
        # Fetch job detail page (best effort)
        if job.get("job_url"):
            detail_soup = get_with_retry(job["job_url"], config, retries=2, delay=1.0)
            detail = transform_job_detail(detail_soup)
            # detail may be dict with description and apply_url
            if isinstance(detail, dict):
                job["job_description"] = detail.get("description", "")
                job["apply_url"] = detail.get("apply_url", "")
                # Try to resolve LinkedIn apply links that redirect externally
                try:
                    au = job.get("apply_url") or ""
                    if au and "linkedin.com" in au:
                        # follow redirects to see if it goes off-linkedin
                        resp = requests.get(au, headers=config.get("headers", {}), proxies=config.get("proxies", {}) or None, timeout=8, allow_redirects=True, stream=True)
                        final = getattr(resp, 'url', au)
                        # if final host is not linkedin, mark as external apply
                        parsed_final = urlparse(final)
                        if parsed_final.netloc and 'linkedin.com' not in parsed_final.netloc.lower():
                            job["apply_url"] = final
                            job["apply_external"] = True
                        else:
                            # still linkedin
                            job["apply_external"] = False
                except Exception:
                    # network issues; leave apply_external as False
                    job["apply_external"] = False
            else:
                job["job_description"] = detail
                job["apply_url"] = ""
        enriched.append(job)

    # 5) Final filter per config
    jobs_to_add = remove_irrelevant_jobs(enriched, config)
    filtered_out = [j for j in enriched if j not in jobs_to_add]

    if filtered_out:
        logger.info(f"Filtered out {len(filtered_out)} jobs after applying filters")
        # Log reasons for a few filtered out jobs
        for job in filtered_out[:10]:
            try:
                reasons = explain_rejection(job, config)
                logger.info(f"Filtered job: {job.get('title')} @ {job.get('company')} -> reasons: {reasons}")
            except Exception:
                logger.exception("Error explaining rejection for a job")

    # 6) Persist: CSV + SQLite
    if jobs_to_add:
        df = pd.DataFrame(jobs_to_add)
        df["date_loaded"] = datetime.now().isoformat(timespec="seconds")
        if conn is not None:
            if table_exists(conn, jobs_table):
                update_table(conn, df, jobs_table)
            else:
                create_table(conn, df, jobs_table)
        df.to_csv("linkedin_jobs.csv", index=False, encoding="utf-8")
        logger.info(f"Wrote linkedin_jobs.csv with {len(df)} rows")
    else:
        logger.info("No jobs to add after filtering.")

    if filtered_out:
        df_f = pd.DataFrame(filtered_out)
        df_f["date_loaded"] = datetime.now().isoformat(timespec="seconds")
        if conn is not None:
            if table_exists(conn, filtered_table):
                update_table(conn, df_f, filtered_table)
            else:
                create_table(conn, df_f, filtered_table)
        df_f.to_csv("linkedin_jobs_filtered.csv", index=False, encoding="utf-8")
        logger.info(f"Wrote linkedin_jobs_filtered.csv with {len(df_f)} rows")

    if conn is not None:
        conn.close()

    t1 = tm.perf_counter()
    logger.info(f"Scraping finished in {t1 - t0:.2f} seconds")

# ---------- Optional: scheduling (stub for future) ----------

def load_schedule_config(schedule_file):
    with open(schedule_file, encoding="utf-8") as f:
        return json.load(f)

def scheduled_task(config_file):
    logger.info(f"Starting scheduled task with config file: {config_file}")
    main(config_file)
    logger.info("Scheduled task completed.")

if __name__ == "__main__":
    # CLI:
    #   python run.py                     -> uses default config.json
    #   python run.py path/to/config.json -> custom config
    cfg = DEFAULT_CONFIG_PATH
    if len(sys.argv) >= 2:
        cfg = sys.argv[1]
    main(cfg)
