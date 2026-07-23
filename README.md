# CI | Tidbits | Security Scan

> **Bite-sized how-to** | ~10 min setup
---

> ## ⚠️ This repo is intentionally vulnerable
>
> The Python app under `app/` and the pinned versions in `requirements.txt` are **deliberately insecure** so the scanners have something to find. It contains, on purpose:
>
> - Known-CVE dependency versions (`flask==1.0`, `pyyaml==5.3.1`, `requests==2.19.0`, …)
> - SQL injection, `yaml.load` without SafeLoader, `subprocess(shell=True)`, `os.system` with user input, MD5 password hashing, a hardcoded secret, disabled TLS verification, and `pickle.loads` on untrusted bytes.
>
> **Do not** use this code, or any part of it, as the basis for a real project. **Do not** deploy it to any network you do not fully control. **Do not** copy `requirements.txt` into another repo. It exists for one purpose: to demonstrate that Harness CI catches these things before they merge.

---

## What is a lightweight security scan?

A lightweight security scan is a **shift-left gate**: run a small, fast pair of scanners inside your CI pipeline so vulnerabilities fail the build before code merges, not after it ships. This tidbit uses two complementary scanners in parallel:

- **Trivy** — a **Software Composition Analysis (SCA)** scanner. Reads dependency manifests (`requirements.txt`, `package.json`, `go.sum`, etc.) and flags known CVEs against installed versions. Catches **what you imported**.
- **Semgrep** — a **Static Application Security Testing (SAST)** scanner. Pattern-matches your source code against curated rulesets and flags insecure code shapes (`yaml.load`, `subprocess(..., shell=True)`, hardcoded secrets, SQL string concatenation, etc.). Catches **how you wrote it**.

Running them **in parallel** as two Run steps keeps total scan time close to the slower of the two — a one-line YAML change (`- parallel:`) that you can reuse for any pair of independent CI gates (lint + test, scan + license check, and so on).

**The result:** a red build the moment a vulnerable dependency is pinned or an insecure pattern is written, with both classes of findings surfaced side-by-side in the execution graph.

---

## Prerequisites

Before you start, make sure you have:

- A Harness account with a **Project** (note its org + project identifiers).
- A **Git connector** (GitHub / GitLab / Bitbucket) pointed at your fork of this repo.
- Harness Cloud build credits (default on Harness-hosted runners). **No STO license, no delegate, no scanner licenses required** — Trivy and Semgrep both run as public Docker images in a Run step.

> **Note:** The scanner images (`aquasec/trivy`, `semgrep/semgrep`) are pulled anonymously from Docker Hub. If you hit pull rate limits, add a Docker Hub connector and reference it via `connectorRef` on each Run step.

---

## Step 1 — Fork this repo and review the sample app

The repo ships with an intentionally vulnerable Python **Order Service** under `app/` and a pinned `requirements.txt` at the root, so the scanners have something to find on the first run.

```
.
├── .harness/
│   └── security_scan.yaml    ← the pipeline
├── app/
│   ├── __init__.py
│   ├── main.py               ← Flask app factory + routes  (debug=True)
│   ├── models.py             ← Product / User / Order dataclasses (clean)
│   ├── services.py           ← Pricing, coupons, order lifecycle (clean)
│   ├── config.py             ← YAML config loader           (yaml.load)
│   ├── db.py                 ← SQLite persistence           (SQL injection)
│   ├── auth.py               ← Password hashing + tokens    (MD5, hardcoded secret)
│   ├── backup.py             ← Admin backup routines        (shell=True, os.system)
│   └── external.py           ← Exchange rates + payments    (verify=False, pickle.loads)
├── requirements.txt          ← pinned vulnerable deps
└── README.md
```

Fork the repo into your own GitHub org so your Harness Git connector can read it. No local Python setup is needed — the scanners run inside CI containers.

> **Tip:** Not every file is vulnerable. `models.py` and `services.py` are deliberately clean, so Semgrep has to walk past real business logic to find the interesting stuff — a more honest picture of what SAST looks like in a real codebase.

---

## Step 2 — Import the pipeline

In your Harness project:

1. Go to **Pipelines → Create a Pipeline → Import From Git**, *or* choose **Create** and switch the editor to **YAML**.
2. Paste the contents of `.harness/security_scan.yaml`.
3. Edit the `# REPLACE:` lines: set `projectIdentifier` and `orgIdentifier` to yours.
4. Save.

---

## Step 3 — Run the pipeline (expect a RED build)

1. Click **Run**. Harness prompts for the codebase runtime inputs — pick your **Git connector**, enter the **repo name** (e.g. `your-user/ci-tidbits-security-scan`), and pick a **branch** (e.g. `main`).
2. Click **Run Pipeline**.

In the execution graph, watch the two scanners run **side-by-side** under a single parallel block. Both are expected to fail.

### Expected Trivy findings

```
requirements.txt (pip)
======================
Total: 8 (CRITICAL: 2, HIGH: 6)

┌──────────┬────────────────┬──────────┬─────────┬───────────────┐
│ Library  │ Vulnerability  │ Severity │ Version │ Fixed Version │
├──────────┼────────────────┼──────────┼─────────┼───────────────┤
│ pyyaml   │ CVE-2020-14343 │ CRITICAL │ 5.3.1   │ 5.4           │
│ jinja2   │ CVE-2019-10906 │ HIGH     │ 2.10    │ 2.10.1        │
│ requests │ CVE-2018-18074 │ HIGH     │ 2.19.0  │ 2.20.0        │
│ urllib3  │ CVE-2019-11324 │ HIGH     │ 1.24.1  │ 1.24.2        │
│ ...      │                │          │         │               │
└──────────┴────────────────┴──────────┴─────────┴───────────────┘
```

Exit code `1` → step fails.

### Expected Semgrep findings

```
app/main.py
   67  debug-enabled                     Flask app.run(debug=True)

app/config.py
   30  dangerous-yaml-load               yaml.load(f) without SafeLoader

app/db.py
   38  formatted-sql-query               string concat in cursor.execute
   86  formatted-sql-query               f-string interpolation in SELECT

app/auth.py
   18  detected-generic-secret           hardcoded SESSION_SECRET
   31  insecure-hash-algorithms-md5      hashlib.md5 used for password hashing

app/backup.py
   21  dangerous-subprocess-use          subprocess.call with shell=True
   33  dangerous-system-call             os.system with user-controlled input

app/external.py
   24  disabled-cert-validation          requests.get(..., verify=False)
   37  avoid-pickle                      pickle.loads on untrusted data
```

Exit code `1` → step fails.

**Red is the correct outcome for the first run.** It proves the gate works.

---

## Step 4 — Fix, re-run, watch it go green

Turn the findings green a file at a time so the demo tells a clean story:

**Fix the dependencies** (Trivy):

```txt
# requirements.txt — after
flask>=3.0.0
pyyaml>=6.0.1
requests>=2.32.0
urllib3>=2.2.2
jinja2>=3.1.4
```

**Fix the code** (Semgrep) — one row per finding, with line numbers:

| File           | Line(s) | Change                                                                        |
| -------------- | ------- | ----------------------------------------------------------------------------- |
| `main.py`      | 67      | `debug=True` → `debug=False`                                                  |
| `config.py`    | 30      | `yaml.load(f)` → `yaml.safe_load(f)`                                          |
| `db.py`        | 38      | Concatenated SQL → parameterised (`... WHERE email = ?`, `(email,)`)          |
| `db.py`        | 86      | f-string SQL → parameterised (`... WHERE sku = ?`, `(sku,)`)                  |
| `auth.py`      | 18      | Move `SESSION_SECRET` to `os.environ["SESSION_SECRET"]`                       |
| `auth.py`      | 31      | `hashlib.md5(...)` → `bcrypt.hashpw(...)` (or argon2)                         |
| `backup.py`    | 21      | `subprocess.call(cmd, shell=True)` → `subprocess.run([...], check=True)`      |
| `backup.py`    | 33      | `os.system(...)` → `subprocess.run([...], check=True)`                        |
| `external.py`  | 24      | Drop `verify=False`                                                           |
| `external.py`  | 37      | `pickle.loads(blob)` → `json.loads(blob.decode())`                            |

Commit, push, re-run the pipeline. Both scan steps go green in parallel. That's the whole story of the tidbit: a two-scanner gate you can drop into any CI pipeline in about twenty lines of YAML.

---

## Pipeline YAML reference

The full pipeline lives at `.harness/security_scan.yaml`. Key shape:

```yaml
stages:
  - stage:
      name: Scan
      type: CI
      spec:
        cloneCodebase: true
        runtime:
          type: Cloud
          spec: {}
        execution:
          steps:
            - parallel:
                - step:
                    name: Trivy Dependency Scan
                    type: Run
                    spec:
                      image: aquasec/trivy:0.55.2
                      command: |-
                        trivy fs --scanners vuln \
                          --severity CRITICAL,HIGH \
                          --exit-code 1 --ignore-unfixed .
                - step:
                    name: Semgrep Static Scan
                    type: Run
                    spec:
                      image: semgrep/semgrep:1.90.0
                      command: |-
                        semgrep scan \
                          --config p/python \
                          --config p/security-audit \
                          --error app
```

> **Tip:** Pin your scanner image tags (`aquasec/trivy:0.55.2`, `semgrep/semgrep:1.90.0`). Rules and defaults shift between minor versions, and a demo that worked yesterday should still work tomorrow.

---

## Common Issues & Tips

**Trivy step passes with zero findings.**
The vuln DB failed to download (no network egress from the build container). Check the step log for `Vulnerability DB downloaded`; if missing, add `--debug` to the trivy command. Alternately, someone updated `requirements.txt` — check the pins.

**Semgrep step passes with zero findings.**
Someone edited `app/`, or the ruleset changed. Confirm `--config p/python --config p/security-audit` are both present and the image tag is pinned.

**`docker pull` rate-limit on the scanner images.**
Public Docker Hub anonymous pulls are throttled. Add a Docker registry connector in Harness and set `connectorRef:` on each Run step to it.

**Steps ran sequentially, not in parallel.**
The `- parallel:` list item must sit directly under `steps:`, with the two `- step:` entries nested under it. Indentation matters — YAML is unforgiving here.

**The build failed but I can't tell which scanner found what.**
Each Run step's log is independent — click into each step separately in the execution view. The `echo "=== ... ==="` header at the top of each command block makes the log easy to scan.

---

## What's next?

- **Fail modes as a variable.** Add a `fail_on_findings` pipeline variable (String, `<+input>.default("true").allowedValues("true","false")`) and gate the `--exit-code 1` / `--error` flags on it. Lets you run the same pipeline in "report only" mode against legacy code.
- **Add a third scanner.** Gitleaks for secrets, Checkov for IaC, Grype as a second SCA opinion — same `- parallel:` pattern, one more `- step:`.
- **Graduate to Harness STO.** When you want findings deduplicated, tracked as issues, gated by OPA policies, and rolled up across pipelines, this pattern is the starting point — the same scanner integrations exist as first-class STO steps.

---

## Resources

- [Run step settings](https://developer.harness.io/docs/continuous-integration/use-ci/run-step-settings/)
- [Run steps in parallel](https://developer.harness.io/docs/continuous-integration/use-ci/optimize-and-more/run-steps-in-parallel/)
- [Trivy CLI reference](https://aquasecurity.github.io/trivy/latest/docs/references/configuration/cli/trivy_fs/)
- [Semgrep CLI reference](https://semgrep.dev/docs/cli-reference)
- [Harness STO overview](https://developer.harness.io/docs/security-testing-orchestration/sto-overview/)

---

# Order Service — Security Scan Demo App

A small Python Flask **Order Service** with intentional vulnerabilities across the codebase, designed to demonstrate **lightweight security scanning in Harness CI**. Every insecure pattern here is on purpose.

---

## What the app does

A stripped-down e-commerce backend:

- Browse products (`GET /products`, optionally filtered by category).
- Log in and receive a signed session token (`POST /auth/login`).
- Place an order with an optional coupon code (`POST /orders`).
- Trigger an admin backup of the DB and invoice PDFs (`POST /admin/backup`).

The domain logic is real — `services.py` computes subtotals, applies percent / flat coupons, walks the order state machine (`pending → paid → shipped`), and calculates tax by country. Only the security-sensitive plumbing (config loading, DB access, auth, backups, external calls) is deliberately broken.

---

## Project structure

```
app/
├── __init__.py       — package marker
├── main.py           — Flask app factory + routes            [debug=True]
├── models.py         — Product / User / Order / OrderItem    (clean)
├── services.py       — build_order, apply_coupon, tax, state (clean)
├── config.py         — YAML config loader                    [yaml.load]
├── db.py             — sqlite3 wrappers                      [SQL injection ×2]
├── auth.py           — password hashing + session tokens     [MD5, hardcoded secret]
├── backup.py         — snapshot_db, sync_invoices            [shell=True, os.system]
└── external.py       — currency + payment gateway            [verify=False, pickle.loads]

requirements.txt      — pinned vulnerable deps
```

---

## What each scanner finds

| Layer                          | Trivy (SCA)                          | Semgrep (SAST)                                          |
| ------------------------------ | ------------------------------------ | ------------------------------------------------------- |
| `requirements.txt`             | pyyaml, flask, requests, urllib3, jinja2 CVEs (2 CRIT / 6 HIGH) | — |
| `app/main.py`                  | —                                    | Flask `debug=True`                                      |
| `app/config.py`                | —                                    | `yaml.load` without SafeLoader                          |
| `app/db.py`                    | —                                    | SQL injection via string concat + f-string              |
| `app/auth.py`                  | —                                    | Hardcoded secret, MD5 password hashing                  |
| `app/backup.py`                | —                                    | `subprocess(shell=True)`, `os.system` with user input   |
| `app/external.py`              | —                                    | `requests` with `verify=False`, `pickle.loads` on bytes |

Ten Semgrep findings and eight-ish Trivy findings out of the box — enough to make the "red build" moment obvious on camera, few enough that you can talk through them in ninety seconds.

---

## Running the app locally (optional)

You don't need to run the app for the scans to work — the scanners are static, they never execute code. But if you want to poke at it:

```bash
pip install -r requirements.txt
python -m app.main
# then in another terminal:
curl "http://localhost:8080/products?category=books"
```

> **Warning:** Do not expose this to any network you don't fully control. It is deliberately exploitable.

---

## Tech Stack

- **Python 3.11+**
- **Flask** (pinned to a vulnerable 1.0 for the demo)
- **PyYAML, requests, urllib3, jinja2** (all pinned to vulnerable versions)
- **SQLite** (via the standard library — no ORM)
- **Harness CI** with Trivy + Semgrep as parallel Run steps
