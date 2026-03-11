

**📋  TEAM IDEA BRIEF  —  v2.0**

Dev Season of Code  —  Devpost Hackathon  —  SWE Track

**Heal-K8s**

Predictive \+ Self-Healing Kubernetes Agent

**No LLM dependency. Pure engineering.**

*"It predicts crashes. It prevents them. If it misses — it fixes them. Gets smarter every time."*

Team: 4  |  7 Days  |  SWE Track

# **1\.  What Are We Building?**

One line version:

| 💡  The Pitch A system that watches your Kubernetes servers, predicts when they are about to crash, prevents the crash before it happens — and if it misses, diagnoses and fixes the crash in seconds. The AI is a fallback, not the core. |
| :---- |

**The problem we are solving:**

| 😴  The 3 AM Problem — Two Versions Version 1 (Reactive): A pod crashes. Engineer gets paged at 3 AM. 45-90 minutes of manual log reading. Every time. Even for the same failure that happened last week.   |   Version 2 (No Prevention): Every tool that exists today — free or paid — waits for the crash to happen before doing anything. Nobody ships a free tool that predicts and prevents. |
| :---- |

**What we do that nobody else does free:**

* **Predict the crash** before it happens using time-series math on memory metrics

* **Prevent it** with a one-click approval before the pod ever dies

* **Fix it** if the crash is too sudden to predict — using deterministic pattern matching

* **Remember it** so the next identical failure resolves even faster

* **LLM is last resort only** — called for unknown failures, not every single incident

# **2\.  Are We Just Calling an LLM API?**

This is an important question. Here is the honest answer:

| ✅  No — The LLM Is a Fallback, Not the Core The core of Heal-K8s is two Python engines we build ourselves: (1) a time-series predictor using rate-of-change math, and (2) a signature diagnosis engine using regex pattern matching. These handle \~90% of real Kubernetes failures instantly with no API call. The LLM is only triggered for the \~10% of failures that are completely unknown and match no pattern. |
| :---- |

| Component | What It Is | LLM Needed? | Who Builds It |
| :---- | :---- | :---- | :---- |
| Predictive Engine | Rate-of-change calculator on memory metrics. Confirms sustained growth over 45 seconds before alerting. | ❌ Pure math | Person B |
| Signature Engine | Dictionary of known failure patterns. Matches log text \+ metric conditions. Returns fix instantly. | ❌ Regex \+ rules | Person B |
| Incident Memory | SQLite database. Checks for previous identical failures first. Returns known fix with confidence score. | ❌ Key-value lookup | Person D |
| LLM Fallback | Only called when signature engine finds no match. Claude / GPT-4o with Function Calling outputs structured JSON fix. | ✅ Yes — 10% of cases | Person B |
| Execution Engine | Kubernetes Python Client. Executes the approved fix command programmatically. | ❌ Pure K8s API | Person A |
| Dashboard | Vanilla JS \+ Chart.js. Shows prediction countdown, confidence badges, real-time memory chart, Approve button. | ❌ Pure frontend | Person C |

# **3\.  The Three Layers — How It Works**

| 🔮  Layer 1 — Predictive Prevention (Best Case) Prometheus samples memory every 10 seconds. Our predictor checks: is this growth sustained for 45+ seconds at 0.5+ MB/s? If yes — alert before crash. We show a countdown on the dashboard. Engineer clicks Approve. Pod is fixed before it ever dies. |
| :---- |

| 🔍  Layer 2 — Signature Diagnosis (90% of Crashes) If crash happens anyway: our engine checks the pod logs against 4 known failure patterns (OOMKilled, CrashLoopBackOff, ImagePullBackOff, PodPending). Instant match — no API call — fix applied in milliseconds. Green badge on dashboard: Signature Match — 99% confidence. |
| :---- |

| 🤖  Layer 3 — LLM Fallback (Unknown Failures Only) If no signature matches: THEN we call Claude / GPT-4o. The AI reads the logs and outputs a structured JSON fix plan. Yellow badge on dashboard: AI Diagnosis. Engineer reviews more carefully because it is an unknown failure. |
| :---- |

# **4\.  The False Positive Problem — We Planned For It**

If you were thinking: 'what if the predictor fires when nothing is actually wrong?' — good. We thought about it too.

| ⚠️  The Problem A Python garbage collector temporarily spikes memory. Our naive predictor screams 'CRASH IN 30 SECONDS'. Nothing happens. We look stupid. |
| :---- |

| ✅  Our Solution — The Sustained Growth Confirmation Window We do not predict on a single spike. We require: (1) 45 seconds of consistent growth, (2) growth rate above 0.5 MB/s minimum, (3) at least 6 consecutive rising readings. A GC spike lasts 2-3 seconds. A real memory leak is sustained. This rule eliminates \~90% of false positives. |
| :---- |

**And in the demo — we show a false positive being correctly ignored. On purpose. Before the judge asks.**

# **5\.  The Demo — Three Scenarios**

We run three scenarios in the demo. Each one proves something different.

| Scenario | What We Show | Why It Matters |
| :---- | :---- | :---- |
| 1 — Prediction prevents crash | Memory leaks slowly. Predictor confirms sustained growth. Dashboard shows countdown. We approve before crash. Pod never dies. | The wow moment. No other free tool shows this. |
| 2 — Crash happens, signature fixes it | Sudden crash — too fast to predict. Signature engine identifies OOMKilled instantly. No API call. 99% confidence. One click fix. | Proves the system is useful even without prediction. |
| 3 — False positive correctly ignored | GC spike triggers — memory jumps then drops in 3 seconds. Predictor sees it but 45-second window not filled. No alert fires. | Shows engineering maturity. Judges always ask about false positives. |

# **6\.  Who Does What**

Four independent tracks. Nobody waits for anyone. We connect on Day 5\.

| 🔧  Person A — Infrastructure Lead Owns:  Minikube cluster \+ Prometheus \+ leaky pod script \+ K8s Python Client execution engine Week focus:  Days 1-2: Get cluster running and crashing. Days 3-4: Execution engine. Day 5: Integrate. |
| :---- |

| 🧠  Person B — Signature \+ Predictive Engine \+ LLM Fallback Owns:  Time-series predictor \+ regex signature dict \+ FastAPI backend \+ LLM fallback for unknown failures Week focus:  Days 1-2: Predictor \+ /trigger-fake endpoints. Days 3-4: Signature engine \+ LLM fallback. Day 5: Integrate. |
| :---- |

| 🎨  Person C — Frontend Lead Owns:  Real-time dashboard \+ Chart.js chart \+ prediction countdown timer \+ approval UI \+ confidence badges Week focus:  Days 1-2: HTML skeleton \+ chart. Days 3-4: Countdown \+ badges \+ Approve button. Day 5: Connect live. |
| :---- |

| 💾  Person D — Memory Engine \+ QA \+ Demo Owns:  SQLite incident memory \+ confidence scoring \+ end-to-end testing \+ demo video recording Week focus:  Days 1-2: Build memory.py. Days 3-4: Integrate with engine. Day 5: Full loop test. Day 6: Record video. |
| :---- |

## **6.1  Day 1 API Contract — Non-Negotiable**

All four of us agree on this before writing any feature code. This is how we work independently without blocking each other:

| Endpoint | Who Builds | Returns | Who Needs It |
| :---- | :---- | :---- | :---- |
| POST /trigger-alert | Person B (Day 1\) | Accepts: { pod\_name, namespace, logs, metrics } | Person A wires Prometheus here |
| GET /system-status | Person A (Day 2\) | Returns: { pod\_status, memory\_readings\[\], prediction\_seconds, badge\_type, diagnosis, confidence, kubectl\_command } | Person C polls every 2 seconds |
| POST /execute | Person A (Day 3\) | Accepts: { kubectl\_command } — runs the fix | Person C Approve button calls this |
| GET /incident-history | Person D (Day 3\) | Returns: { incidents\[\] } | Person C history panel |

# **7\.  The 7-Day Plan**

| Day | Person A | Person B | Person C | Person D |
| :---- | :---- | :---- | :---- | :---- |
| Day 1 | Minikube \+ leaky pod crashing | FastAPI \+ /trigger-fake-alert \+ /trigger-fake-prediction | HTML skeleton with all panels | Incident memory schema shared with team |
| Day 2 | Prometheus via Helm (4hr limit) \+ build GET /system-status skeleton | Predictive engine: rate calc \+ 45s confirmation window | Chart.js memory graph \+ threshold line | memory.py: store, lookup, confidence functions |
| Day 3 | K8s Python Client — restart pods | Signature engine: 4 patterns (OOMKill, CrashLoop, ImagePull, Pending) | Prediction countdown \+ Approve button \+ badges | GET /incident-history endpoint \+ unit tests |
| Day 4 | Wire full execution loop via curl | LLM fallback \+ memory lookup integrated into full diagnosis flow | Connect dashboard to live /system-status polling | Memory check runs before signature engine |
| Day 5 | ALL FOUR — Integration Day — run all 3 demo scenarios together |  |  |  |
| Day 6 | Logging \+ read-only mode \+ code cleanup | Edge case testing across all 5 failure paths | Full UI polish \+ recovery animation | 15x Golden Loop runs \+ record 3-min demo video |
| Day 7 | README \+ curl guide \+ architecture diagram | Engine \+ API docs in README | Devpost screenshots | Devpost submission by 6 PM |

| 🛡️  The Survival Rule Person A: you have a 4-hour limit on Prometheus on Day 2\. If it is not firing webhooks to your backend by then — switch to /trigger-fake-alert immediately and move on. Person B can keep building the prediction engine against fake metrics. A working engine on mocked data is infinitely better than a broken Prometheus setup blocking the whole team. |
| :---- |

# **8\.  Tech Stack — Plain English**

| Technology | What It Is | Why We Use It |
| :---- | :---- | :---- |
| Minikube | Kubernetes running on your laptop | Free, offline, reproducible — no AWS bills |
| Prometheus | Monitoring tool that watches server metrics | Industry standard — same tool real DevOps teams use |
| FastAPI (Python) | Framework for building web APIs | Fast to build, easy to read, good async support |
| Time-series math (Python) | Rate-of-change calculation — no ML library | The predictor core — just arithmetic on memory readings |
| Regex \+ rules dict (Python) | Pattern matching for known failure signatures | Instant, deterministic, auditable — no AI needed |
| Claude / GPT-4o | AI model with Function Calling — last resort only | Structured JSON output for unknown failures — \~10% of cases |
| SQLite | Lightweight file-based database | Stores incident memory — zero setup, works offline |
| Kubernetes Python Client | Official library to control Kubernetes from Python | Safe, auditable execution — no raw shell commands |
| Vanilla JS \+ Chart.js | Plain JavaScript \+ charting library | Real frontend — not a Streamlit shortcut |

# **9\.  How We Work Together — Git & Folder Structure**

We are on 4 separate PCs. This section tells every person exactly what to open, what to create, and how to merge without chaos.

## **9.1  Day 1 Setup — First 30 Minutes**

Person A creates the GitHub repo. Everyone else clones it.

| 🔧  Person A Does This First 1\. Go to github.com → New Repository → Name: heal-k8s → Set Public → Add README → Share link with team.   2\. Everyone else runs:  git clone https://github.com/yourteam/heal-k8s.git  then  cd heal-k8s |
| :---- |

Then everyone creates their own branch — never work on main directly:

| Person | Branch Name | Command to Run on Your PC |
| :---- | :---- | :---- |
| Person A | person-a-infrastructure | git checkout \-b person-a-infrastructure |
| Person B | person-b-backend | git checkout \-b person-b-backend |
| Person C | person-c-frontend | git checkout \-b person-c-frontend |
| Person D | person-d-memory | git checkout \-b person-d-memory |

## **9.2  Folder Structure — Who Owns What**

Each person owns exactly one folder. Nobody touches another person's folder until Integration Day.

| Folder | Owner | Files to Create Inside |
| :---- | :---- | :---- |
| heal-k8s/infrastructure/ | Person A | leaky\_app.py, leak-pod.yaml, k8s\_executor.py, prometheus/values.yaml |
| heal-k8s/backend/ | Person B | main.py (FastAPI \+ all endpoints), predictor.py, signature\_engine.py, llm\_fallback.py |
| heal-k8s/frontend/ | Person C | index.html, app.js, style.css |
| heal-k8s/memory/ | Person D | memory.py, models.py — incident\_memory.db is auto-created on first run |
| heal-k8s/tests/ | Person D | test\_predictor.py, test\_signature.py, test\_memory.py |
| heal-k8s/requirements.txt | Person B — Day 1 | fastapi, uvicorn, kubernetes, anthropic — everyone runs pip install \-r requirements.txt |
| heal-k8s/.env.example | Person B — Day 1 | ANTHROPIC\_API\_KEY=your\_key\_here — everyone copies to .env, never commit .env |

| ⚠️  The One Golden Rule Each person ONLY touches their own folder all week. The only shared files are requirements.txt and README.md — one person edits those at a time. This prevents 90% of merge conflicts before they happen. |
| :---- |

## **9.3  Daily Git Routine — Every Person, Every Day**

| When | Command | What It Does |
| :---- | :---- | :---- |
| Morning — start of day | git pull origin main | Gets any changes teammates merged overnight — always do this first |
| During the day | Write code normally in your folder | Stay inside your folder only |
| Evening — end of day | git add . | Stages all your changes for saving |
| Evening | git commit \-m "Day 2: predictor rate calc done" | Saves your work with a descriptive message |
| Evening | git push origin your-branch-name | Uploads your work to GitHub so team can see it |

## **9.4  How to Work Without Blocking Each Other (Days 1-4)**

Days 1 to 4 everyone uses mocks so nobody waits for anyone else:

| 🧠  Person B — Mock Imports Until Day 5 In backend/main.py write mock functions for anything Person A or D hasn't built yet. Example: def restart\_pod(pod\_name, namespace): return {status: mock\_success}   and   def lookup\_pattern(failure\_type): return None. Add a comment above each: \# MOCK — replace Day 5 with: from infrastructure.k8s\_executor import restart\_pod. On Day 5 delete the mock function and uncomment the real import. |
| :---- |

| 🎨  Person C — MOCK\_MODE Flag Until Day 5 At the top of frontend/app.js add: const MOCK\_MODE \= true. When true, fetchStatus() returns a hardcoded JSON object with fake memory readings, prediction countdown, and diagnosis. Build and animate the entire dashboard against this fake data Days 1-4. On Day 5: change to MOCK\_MODE \= false. The dashboard instantly connects to Person B's live backend. |
| :---- |

| 💾  Person D — Build and Test Fully in Isolation memory.py is a standalone Python module — no dependencies on anyone else. Build and test it with pytest independently all week. Person B imports your module on Day 4\. Make sure these three function signatures are exactly right: lookup\_pattern(failure\_type: str) → dict or None,   store\_outcome(failure\_type, fix, success: bool),   update\_confidence(failure\_type, success: bool). |
| :---- |

## **9.5  Integration Day — Day 5 (Step by Step)**

Everyone joins a video call. Person B drives the merge. Follow this exact order:

| Step | Command | Who |
| :---- | :---- | :---- |
| 1\. Switch to main | git checkout main | Person B |
| 2\. Merge infrastructure | git merge person-a-infrastructure | Person B |
| 3\. Merge backend | git merge person-b-backend | Person B |
| 4\. Merge frontend | git merge person-c-frontend | Person B |
| 5\. Merge memory | git merge person-d-memory | Person B |
| 6\. Fix any conflicts | Edit conflict files together on call — Git marks them with \<\<\<\< and \>\>\>\> | Everyone |
| 7\. Push merged main | git push origin main | Person B |
| 8\. Everyone pulls | git pull origin main | Persons A, C, D |
| 9\. Remove all mocks | Set MOCK\_MODE=false \+ uncomment real imports in main.py | Person B \+ C |
| 10\. Run the full loop | uvicorn backend.main:app \--port 8000 then open index.html | Test together |

## **9.6  Running the Project on Your PC**

| Person | What to Run | Command |
| :---- | :---- | :---- |
| Person A | Test the leaky pod script | python infrastructure/leaky\_app.py |
| Person A | Check pod status | kubectl get pods \-n default |
| Person A | Test K8s executor | python infrastructure/k8s\_executor.py |
| Person B | Run the full backend | uvicorn backend.main:app \--reload \--port 8000 |
| Person B | Test predictor alone | python backend/predictor.py |
| Person B | Test signature engine alone | python backend/signature\_engine.py |
| Person C | Open the dashboard | Open frontend/index.html in Chrome — no server needed |
| Person C | Debug API calls | Chrome → F12 → Network tab → watch /system-status polling |
| Person D | Run all tests | pytest tests/ \-v |
| Person D | Inspect memory database | python \-c "import sqlite3; c=sqlite3.connect('memory/incident\_memory.db'); print(c.execute('SELECT \* FROM incidents').fetchall())" |

## **9.7  Quick Reference Cheatsheet**

|  | Person A | Person B | Person C | Person D |
| :---- | :---- | :---- | :---- | :---- |
| Branch | person-a-infrastructure | person-b-backend | person-c-frontend | person-d-memory |
| My folder | infrastructure/ | backend/ | frontend/ | memory/ \+ tests/ |
| First file to create | infrastructure/leaky\_app.py | backend/main.py | frontend/index.html | memory/memory.py |
| Mock I provide to team | k8s\_executor.py (Person B imports Day 4\) | POST /trigger-alert \+ GET /system-status (Person C polls Day 2\) | Nothing — I consume APIs | memory.py (Person B imports Day 4\) |
| My mock until Day 5 | N/A | def restart\_pod() returns fake JSON | MOCK\_MODE \= true in app.js | N/A — standalone module |
| Done and ready by | Day 4 afternoon | Day 2 (/system-status skeleton) | Day 5 (connects live) | Day 4 afternoon |

| 📋  Daily Standup — 15 Minutes Every Morning on a Call Each person answers 3 questions: (1) What did I finish yesterday? (2) What am I building today? (3) Am I blocked by anyone? No other meetings needed all week. If you are blocked — message the relevant person immediately. Do not wait for standup. |
| :---- |

Heal-K8s  |  Team Brief  v3.0  |  Dev Season of Code 2025

*"Built for the engineers who deserve to sleep through the night."*