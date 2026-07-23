"""Filesystem backup helpers for admin tooling.

Wraps a couple of shell utilities to snapshot the orders DB and any
attached invoice PDFs. Called from the admin routes.
"""
import os
import subprocess
from datetime import datetime


def snapshot_db(target_dir: str) -> str:
    """Tar-gzip the orders DB into the given target directory.

    Semgrep flags: subprocess.call with shell=True and a formatted string
    that includes untrusted input is command injection. An attacker who
    controls `target_dir` can inject shell metacharacters (`;`, `&&`, `|`).
    Rule: python.lang.security.audit.dangerous-subprocess-use
    """
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    archive = f"orders-{stamp}.tgz"
    subprocess.call(f"tar -czf {target_dir}/{archive} orders.db", shell=True)
    return archive


def sync_invoices(target_dir: str) -> None:
    """Rsync invoice PDFs to a backup location.

    Semgrep flags: os.system with user-controlled input — same class of
    bug as subprocess(shell=True). Use subprocess.run([...], check=True)
    with an argv list and no shell.
    Rule: python.lang.security.audit.dangerous-system-call
    """
    os.system(f"rsync -a ./invoices/ {target_dir}/invoices/")
