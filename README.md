# CI | Tidbits | Security Scan

> **Bite-sized how-to** | ~10 min setup

---

> ## ⚠️ This repo pins vulnerable dependencies on purpose
>
> `requirements.txt` in this repo is deliberately pinned to old library versions with known CVEs (`flask==1.0`, `pyyaml==5.3.1`, `requests==2.19.0`, `urllib3==1.24.1`, `jinja2==2.10`) so the CI scan has something to find. The Python code under `app/` is clean — no intentional insecure patterns. **Do not** copy `requirements.txt` into a real project. **Do not** deploy this app to any network you do not fully control.

---

## What is a lightweight dependency scan?

A dependency scan is a **shift-left gate**: run a Software Composition Analysis (SCA) scanner inside your CI pipeline so vulnerable dependencies fail the build before code merges, not after it ships. This tidbit uses **Trivy** as a plain CI Run step — one image, one command, one gate:

- **Trivy** reads dependency manifests (`requirements.txt`, `package.json`, `go.sum`, and dozens more), cross-references them against a vulnerability database, and reports CVEs against the installed versions.
- The Run step **exits non-zero** on any CRITICAL or HIGH finding, which fails the Harness stage, which fails the pipeline.

**The result:** a red build the moment a pinned dependency has a known vulnerability with a fix available. Your code can be pristine and your deps can still sink you — that is what SCA catches.

> **Why just Trivy?** This is the smallest possible version of a shift-left security gate — one scanner, one step, ~15 lines of pipeline YAML. For SAST, secret scanning, IaC scanning, or multi-scanner setups, see the "What's next?" section.

---

## Prerequisites

Before you start, make sure you have:

- A Harness account with a **Project** (note its org + project identifiers).
- A **Git connector** (GitHub / GitLab / Bitbucket) pointed at your fork of this repo.
- Harness Cloud build credits (default on Harness-hosted runners). Trivy runs as a public Docker image inside a plain CI Run step — no additional licenses required.

> **Note:** The Trivy image (`aquasec/trivy`) is pulled anonymously from Docker Hub. If you hit pull rate limits, add a Docker Hub connector and reference it via `connectorRef` on the Run step.

---

## Step 1 — Fork this repo and review the sample app

The repo ships with a small Python **Order Service** under `app/` and a pinned `requirements.txt` at the root. The app is deliberately clean — the entire vulnerable surface lives in `requirements.txt`.

```
.
├── .harness/
│   └── security_scan.yaml    ← the pipeline (one CI stage, one Run step)
├── app/
│   ├── __init__.py
│   ├── main.py               ← Flask app factory + routes
│   ├── models.py             ← Product / Order / OrderItem dataclasses
│   ├── services.py           ← pricing, coupons, order lifecycle
│   ├── config.py             ← YAML config loader
│   └── db.py                 ← SQLite persistence, parameterised queries
├── requirements.txt          ← pinned vulnerable deps ← the scan target
└── README.md
```

Fork the repo into your own GitHub org so your Harness Git connector can read it. No local Python setup is needed — Trivy runs inside a CI container.

---

## Step 2 — Import the pipeline

In your Harness project:

1. Go to **Pipelines → Create a Pipeline → Import From Git**, _or_ choose **Create** and switch the editor to **YAML**.
2. Paste the contents of `.harness/security_scan.yaml`.
3. Edit the `# REPLACE:` lines: set `projectIdentifier` and `orgIdentifier` to yours.
4. Save.

---

## Step 3 — Run the pipeline (expect a RED build)

1. Click **Run**. Harness prompts for the codebase runtime inputs — pick your **Git connector**, enter the **repo name** (e.g. `your-user/ci-tidbits-security-scan`), and pick a **branch** (e.g. `main`).
2. Click **Run Pipeline**.

The **Trivy Dependency Scan** step runs, downloads the vulnerability DB, scans `requirements.txt`, and exits with `1` because CRITICAL/HIGH findings were detected.

### Expected Trivy findings

Approximate output (exact CVE list depends on when the DB was last refreshed):

```
requirements.txt (pip)
======================
Total: 10 (CRITICAL: 1, HIGH: 8, MEDIUM: 1)

┌──────────┬────────────────┬──────────┬─────────┬───────────────────────────────┐
│ Library  │ Vulnerability  │ Severity │ Version │ Title                         │
├──────────┼────────────────┼──────────┼─────────┼───────────────────────────────┤
│ pyyaml   │ CVE-2020-14343 │ CRITICAL │ 5.3.1   │ arbitrary code execution      │
│ jinja2   │ CVE-2019-10906 │ HIGH     │ 2.10    │ sandbox escape                │
│ jinja2   │ CVE-2020-28493 │ HIGH     │ 2.10    │ ReDoS in urlize filter        │
│ requests │ CVE-2018-18074 │ HIGH     │ 2.19.0  │ Authorization header leak     │
│ urllib3  │ CVE-2019-11324 │ HIGH     │ 1.24.1  │ CRLF injection                │
│ urllib3  │ CVE-2019-11236 │ HIGH     │ 1.24.1  │ CRLF injection in URL         │
│ ...      │                │          │         │                               │
└──────────┴────────────────┴──────────┴─────────┴───────────────────────────────┘
```

Exit code `1` → step fails → pipeline is red.

**Red is the correct outcome for the first run.** It proves the gate works.

---

## Step 4 — Fix, re-run, watch it go green

Bump the pins to current versions:

```txt
# requirements.txt — after
flask>=3.0.0
pyyaml>=6.0.1
requests>=2.32.0
urllib3>=2.2.2
jinja2>=3.1.4
```

Commit, push, re-run the pipeline. Trivy finds nothing above HIGH, exits `0`, the step goes green, the pipeline goes green. That's the whole story of the tidbit: a one-step CI gate you can drop into any pipeline in about fifteen lines of YAML.

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
            - step:
                name: Trivy Dependency Scan
                type: Run
                spec:
                  image: aquasec/trivy:0.55.2
                  command: |-
                    trivy fs \
                      --scanners vuln \
                      --severity CRITICAL,HIGH \
                      --exit-code 1 \
                      --ignore-unfixed .
```

> **Tip:** Pin the Trivy image tag (`aquasec/trivy:0.55.2`). Trivy's defaults, output format, and rule set shift between minor versions — pinning means the demo that worked yesterday still works tomorrow.

### What the flags do

| Flag                       | Effect                                                            |
| -------------------------- | ----------------------------------------------------------------- |
| `fs`                       | Scan the filesystem (as opposed to `image`, `repo`, `sbom`, etc.) |
| `--scanners vuln`          | Only run the vulnerability scanner (skip secret and misconfig)    |
| `--severity CRITICAL,HIGH` | Only report CRITICAL and HIGH findings                            |
| `--exit-code 1`            | Exit non-zero when findings are present → fails the CI step       |
| `--ignore-unfixed`         | Skip CVEs with no fix available yet (reduces noise)               |
| `--no-progress`            | Cleaner logs on non-interactive terminals                         |

---

## Common Issues & Tips

**Trivy step passes with zero findings.**
The vuln DB failed to download (no network egress from the build container). Check the step log for `Vulnerability DB downloaded`; if missing, add `--debug` to the trivy command. Alternately, someone updated `requirements.txt` — check the pins.

**`docker pull` rate-limit on the scanner image.**
Public Docker Hub anonymous pulls are throttled. Add a Docker registry connector in Harness and set `connectorRef:` on the Run step.

**The step passes but I know my deps are vulnerable.**
`--ignore-unfixed` skips CVEs without a released fix. Drop that flag to see them all (at the cost of some noise). Also check `--severity` — CVEs below HIGH won't be reported.

**I want the scan to run but not fail the build.**
Remove `--exit-code 1`. The scanner will still print its findings; the step will always exit `0`. Useful for a "shadow mode" rollout before you turn the gate on.

---

## What's next?

- **Add a static (SAST) scan alongside.** Add a second Run step with `semgrep/semgrep:1.90.0` and `semgrep scan --config p/python --error app`. Wrap both under `- parallel:` to keep total scan time close to the slower of the two.
- **Fail modes as a variable.** Add a `fail_on_findings` pipeline variable (`<+input>.default("true").allowedValues("true","false")`) and gate `--exit-code 1` on it. Same pipeline runs in enforce or report-only mode.

---

## Resources

- [Run step settings](https://developer.harness.io/docs/continuous-integration/use-ci/run-step-settings/)
- [Trivy `fs` CLI reference](https://aquasecurity.github.io/trivy/latest/docs/references/configuration/cli/trivy_fs/)
- [Trivy severity filtering](https://aquasecurity.github.io/trivy/latest/docs/configuration/filtering/)

---

# Order Service — Dependency Scan Demo App

A small Python Flask **Order Service** used as a target for the CI dependency scan. The code is clean; the vulnerabilities live entirely in `requirements.txt`.

## What the app does

A stripped-down e-commerce backend:

- Browse products (`GET /products`, optionally filtered by category).
- Place an order with an optional coupon code (`POST /orders`).

The domain logic in `services.py` is real — it computes subtotals, applies percent / flat coupons, walks the order state machine (`pending → paid → shipped`), and calculates tax by country.

## Project structure

```
app/
├── __init__.py       — package marker
├── main.py           — Flask app factory + routes
├── models.py         — Product / Order / OrderItem dataclasses
├── services.py       — build_order, apply_coupon, tax, state transitions
├── config.py         — YAML config loader (uses safe_load)
└── db.py             — sqlite3 wrappers (parameterised queries)

requirements.txt      — pinned vulnerable deps ← the scan target
```

## Running the app locally (optional)

You don't need to run the app for the scan to work — Trivy is static, it never executes code. But if you want to poke at it:

```bash
pip install -r requirements.txt
python -m app.main
# then in another terminal:
curl "http://localhost:8080/products?category=books"
```

## Tech Stack

- **Python 3.11+**
- **Flask** (pinned to a vulnerable 1.0 for the demo)
- **PyYAML, requests, urllib3, jinja2** (all pinned to vulnerable versions)
- **SQLite** (via the standard library — no ORM)
- **Harness CI** with Trivy as a single Run step
