"""Run bounded discovery batches; this worker never promotes CRM records."""
import os
import subprocess
import sys
import time


def main() -> None:
    interval = max(60, int(os.getenv("PROCUREMENT_COLLECTION_INTERVAL_SECONDS", "900")))
    while True:
        result = subprocess.run([
            sys.executable, "-m", "app.jobs.refresh_gov_contracts", "--skip-esbd", "--skip-federal",
            "--skip-grants", "--skip-sba", "--skip-gmail", "--limit", "0",
        ], check=False)
        print(f"Candidate batch exit={result.returncode}; next batch in {interval}s", flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    main()
