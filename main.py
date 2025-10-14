#!/usr/bin/env python3
"""Top-level entrypoint for job-bot scraper.

Provides a simple CLI so users can run `python main.py` or `python app.py`.
This script delegates to `utils/run.py`'s main(config_path) function when available,
otherwise it falls back to running the module as a script.
"""
import sys
import os

DEFAULT_CONFIG = "config.json"

def _run_with_utils(config_path):
    # Import the utils.run module and call its main function
    try:
        from utils import run as run_module
    except Exception as e:
        print(f"Could not import utils.run: {e}")
        return 2

    if hasattr(run_module, "main"):
        run_module.main(config_path)
        return 0
    else:
        print("utils.run does not expose a main(config_path) function.")
        return 3

def _run_as_script(config_path):
    # Fallback: try to execute utils/run.py as a script
    run_py = os.path.join(os.path.dirname(__file__), "utils", "run.py")
    if os.path.exists(run_py):
        os.execv(sys.executable, [sys.executable, run_py, config_path])
    else:
        print("No utils/run.py found to run as script.")
        return 4

def parse_args(argv):
    # Accept --config <path> or a single positional config path.
    config = DEFAULT_CONFIG
    if not argv:
        return config
    if argv[0] in ("-h", "--help"):
        print("Usage: python main.py [--config CONFIG_PATH]")
        sys.exit(0)
    if argv[0] == "--config" and len(argv) >= 2:
        return argv[1]
    # fallback to first arg being the config path
    return argv[0]

def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    config = parse_args(argv)
    # Try the preferred path (importing module)
    rc = _run_with_utils(config)
    if rc != 0:
        # fallback to executing the script file
        return _run_as_script(config)
    return 0

if __name__ == "__main__":
    sys.exit(main())
