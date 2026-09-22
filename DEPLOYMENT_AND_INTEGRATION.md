# Deployment & Integration Guide

**Audience: non-technical readers.** This guide takes you from "I have the
project files" to "the chatbot is live on our college website with HTTPS",
using copy-paste commands. You do not need programming knowledge — you need
patience and an account or two.

**How to read this guide:**

- `code blocks like this` are commands. Click the copy icon, paste into a
  terminal, press Enter.
- **⚠ Ask your developer** marks anything that is safer to hand to a technical
  person (they can do it in minutes).
- `assistant.example.edu` and `www.your-college.edu` are **examples** — always
  replace them with your real domain names.

A companion technical document lives at
[docs/deployment-guide.md](docs/deployment-guide.md); this file is the
step-by-step version of it.

---

## 1. What you are setting up (in plain English)

| Piece | Its job |
| --- | --- |
| **Server** (cloud computer) | Runs everything 24/7 so the bot never sleeps |
| **Domain + HTTPS** (the padlock) | Gives your bot a trustworthy address like `https://assistant.example.edu` |
| **api** container | The brain — receives questions, applies the FAQ → metrics → Hybrid RAG → fallback rules, returns answers and records each answer's sources for auditing |
| **worker** container | The librarian — reads documents you upload and prepares them for search, in the background |
| **web** container | The receptionist — serves the admin dashboard and the widget file |
| **postgres** container | The filing cabinet — stores FAQs, documents, accounts, analytics, audit logs |
| **redis** container | The notice board — queues background jobs and caches answers |
| **clamav** container | The security scanner — virus-checks every uploaded file (added automatically by the production file) |
| **Caddy** (installed on the server itself) | The doorman — obtains and renews the HTTPS certificate and routes visitors safely |
| **`.env` file** | The settings folder — all keys and addresses live here. **It is a secret; never share it or upload it anywhere** |
| **LLM key** (OpenAI *or* Gemini *or* Groq) | Powers AI answers and document search. Any **one** key is enough |
| **Pinecone** | The semantic (meaning-based) half of Hybrid RAG for uploaded documents |
| **SMTP mailbox** | Delivers the six-digit login codes to administrators |
| **Meta WhatsApp credentials** | Enables the WhatsApp channel (required before switching to full production mode) |

**Two commands files you will use throughout:**

```bash
# The normal way to start/restart everything on the server:
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Where errors and progress are printed:
docker compose logs -f --tail=100 api worker
```

---

## 2. Everything you need before starting

| What | Required? | Where to get it | Why |
| --- | --- | --- | --- |
| Cloud server (VPS), Ubuntu 24.04 LTS, **4 GB RAM / 2 vCPU** (minimum 2 GB + swap, see §3.9) | **Yes** | DigitalOcean, Vultr, Hetzner, AWS EC2, or your college's own Linux server | Hosts the bot |
| Domain or sub-domain you control (e.g. `assistant.yourcollege.edu`) | **Yes** | Your college's domain registrar / IT team | HTTPS padlock; the widget loads from this address |
| This project's code | **Yes** | Your Git repository, or a ZIP of the project folder | — |
| **LLM API key — any ONE of:** OpenAI, Gemini, or Groq | **Yes** | platform.openai.com · aistudio.google.com (free tier) · console.groq.com (free) | AI answers; production refuses to start without one. Free keys are fine to begin with |
| Pinecone account + index (3072 dimensions) | For document search | pinecone.io (free starter tier) | Without it: FAQ + metric answers still work, document search does not |
| SMTP mailbox (login codes) | **Yes** | College mail server, Gmail **App Password**, or SendGrid free tier | Administrators cannot sign in without it |
| Meta WhatsApp credentials (4 values) | To reach **production** mode | developers.facebook.com (§3, Part 5) | The application requires them for full production launch |
| Git (`sudo apt install -y git`) or any ZIP tool | **Yes** | Already on most systems; otherwise the commands below install it | Gets the code onto the server |
| A terminal | **Yes** | macOS/Linux: Terminal · Windows: built-in `ssh` in PowerShell | Paste commands into the server |

Nothing else is required: **Docker, ClamAV, nginx, PostgreSQL, Redis, and
Celery are all installed/started by the commands below** — you never install
databases by hand.

---

# PART A — Set up the server

## Step 1: Create the server

1. Sign up at any cloud provider (they all work the same way).
2. Create a server ("Droplet" / "Instance" / "VPS"):
   - Image: **Ubuntu 24.04 LTS**
   - Size: **4 GB RAM / 2 vCPU** (a 2 GB server also works — do Step 3.9)
   - Note the **server's public IP address** — you will need it in Step 2.

## Step 2: Point your domain at the server

1. Open your domain registrar's control panel (where the college domain is
   managed) → **DNS settings**.
2. Add one record:

   | Type | Name (host) | Value (points to) | TTL |
   | --- | --- | --- | --- |
   | `A` | `assistant` (or whatever prefix you want) | your server's IP address | Automatic |

   Example: `assistant.yourcollege.edu → 203.0.113.10`
3. Wait 5–30 minutes for it to take effect. You can check by running this from
   **your own PC**:

   ```bash
   ping -c 3 assistant.yourcollege.edu
   ```

   It must print your server's IP. (`nslookup assistant.yourcollege.edu` works
   on Windows.)

## Step 3: Log in to the server and install everything

### 3.1 Log in (SSH)

On your PC, open a terminal and run (replace with your IP and username — the
provider shows you which, often `root` or `ubuntu`):

```bash
ssh user@203.0.113.10
```

Accept the fingerprint question with `yes`, then type the password your
provider gave you (it does not show while typing — that is normal).

> Windows alternative: press `Win`, type `PowerShell`, press Enter, and run the
> same `ssh` command.

You are now "sitting at" your server. Every command below runs **there**.

### 3.2 Install Docker (runs the whole project)

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

Log out and back in so the permission takes effect:

```bash
exit
ssh user@203.0.113.10
docker --version
docker compose version
```

Both commands must print version numbers.

### 3.3 Get the project code onto the server

**Option 1 — Git (if your repository is public or you have access):**

```bash
sudo apt update && sudo apt install -y git unzip
cd ~
git clone <REPOSITORY-URL> ciet-bot
cd ciet-bot
```

**Option 2 — Upload a ZIP (no Git needed):**

On **your PC**: open the project folder, select everything **except**
`.env`, `node_modules`, and `.venv`, right-click → *Send to → Compressed
(zip) folder*. Then, from your PC:

```powershell
scp .\CIET_BOT.zip user@203.0.113.10:~
```

Back on the server:

```bash
sudo apt update && sudo apt install -y unzip
cd ~
unzip CIET_BOT.zip -d ciet-bot
cd ciet-bot
```

You should now be inside the project folder (you can confirm with `ls` — you
must see `docker-compose.yml`).

### 3.4 Create your secret settings file (`.env`)

```bash
cp .env.example .env
nano .env
```

`nano` opens the file in the terminal. Generate the two secret values first —
open a **second** SSH window (`ssh user@IP` again) and run:

```bash
openssl rand -hex 48     # → this is your JWT_SECRET (copy the whole output)
openssl rand -hex 16     # → this is your WHATSAPP_VERIFY_TOKEN (save both)
```

Back in `nano`, edit the file so these lines are filled in (replace every
example value; keep everything else as the template left it):

```env
ENVIRONMENT=local

# --- AI: paste ANY ONE key you created (Gemini/Groq free tiers are fine) ---
GEMINI_API_KEY=paste-your-real-key-here
LLM_PROVIDER_ORDER=openai,gemini,groq

# --- Your addresses (no trailing slash on origins!) ---
API_BASE_URL=https://assistant.example.edu
WIDGET_ORIGIN=https://www.your-college.edu
ADMIN_ORIGIN=https://assistant.example.edu
ALLOWED_HOSTS=localhost,127.0.0.1,assistant.example.edu
ALLOWED_WIDGET_DOMAINS=localhost,127.0.0.1,assistant.example.edu,www.your-college.edu,your-college.edu
CORS_ORIGINS_EXTRA=https://www.your-college.edu,https://your-college.edu

# --- Paste the long value from "openssl rand -hex 48" ---
JWT_SECRET=paste-the-96-character-hex-string-here

# --- Email for login codes (Gmail needs a "App Password", see note below) ---
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-address@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=your-address@gmail.com
SMTP_FROM_NAME=CIET AI Assistant

# --- Pinecone (document search) ---
PINECONE_API_KEY=your-pinecone-key
PINECONE_INDEX=your-index-name
PINECONE_NAMESPACE=

# --- Leave empty for now; Part 5 fills these in before going live ---
WHATSAPP_VERIFY_TOKEN=
WHATSAPP_APP_SECRET=
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
```

**Notes:**

- *Line by line, what each setting means* is documented in
  [.env.example](.env.example) itself — every line there has a comment.
- **Gmail users:** plain passwords no longer work. In your Google Account →
  *Security → 2-Step Verification → App passwords*, create one and put it in
  `SMTP_PASSWORD`. College mail servers or SendGrid work the same way.
- If any password contains spaces or `#`, wrap its value in double quotes.
- Save in nano: press `Ctrl+O`, then Enter, then `Ctrl+X`.

### 3.5 Start the project

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

The first run downloads and builds everything — **5–15 minutes**. Watch it:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

Wait until `api`, `worker`, `web`, `postgres`, `redis`, and `clamav` all show
`healthy` (ClamAV may show `starting` for a few minutes the very first time —
it is downloading its virus database).

> What this command did for you:
> - applied the database migrations automatically,
> - **stopped PostgreSQL, Redis, and the raw API from being reachable from the
>   internet** (only your server can touch them),
> - added the ClamAV virus scanner that production mode requires.

### 3.6 Install Caddy (the HTTPS padlock)

Caddy is a small, free web server that obtains and **automatically renews**
your HTTPS certificate:

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install -y caddy
```

Tell it how to route visitors:

```bash
sudo nano /etc/caddy/Caddyfile
```

Delete anything already there and paste this (**replace the example domain
with yours**, keep the curly braces and indentation):

```
assistant.example.edu {
	handle /api/* {
		reverse_proxy 127.0.0.1:8000
	}
	handle /healthz {
		reverse_proxy 127.0.0.1:8000
	}
	handle /readyz {
		reverse_proxy 127.0.0.1:8000
	}
	handle {
		reverse_proxy 127.0.0.1:8080
	}
}
```

Save (`Ctrl+O`, Enter, `Ctrl+X`) and activate it:

```bash
sudo systemctl enable --now caddy
sudo systemctl reload caddy
```

**In plain English:** chat traffic (`/api/...`) and the health checks go
straight to the brain (`:8000`); everything else — the widget file and the
admin dashboard — goes to the receptionist (`:8080`). Caddy automatically
fetches the padlock certificate the first time someone visits over
`https://`.

### 3.7 Open only the safe doors (firewall)

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
sudo ufw status
```

You should see only `OpenSSH`, `80`, and `443` allowed. The database, Redis,
and raw API ports stay invisible to the outside world — that is intentional.

### 3.8 First start checklist

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps   # all healthy?
sudo systemctl status cuddy 2>/dev/null || sudo systemctl status caddy | head -5   # caddy active (green)?
```

---

## Step 4: Verify everything works

Open these addresses in **your browser** (replace the domains):

| Address | What you should see |
| --- | --- |
| `https://assistant.example.edu/healthz` | the word `ok` |
| `https://assistant.example.edu/readyz` | JSON text containing `"ai":"configured"` |
| `https://assistant.example.edu/widget/` | a page with the CIET widget preview |
| `https://assistant.example.edu/admin/` | the admin login page |
| the address bar | a **padlock** next to the URL |

If the padlock is missing, your domain probably is not pointing at the server
yet (Step 2) — Caddy retries automatically once DNS is correct.

---

# PART B — First administrator account

There is intentionally **no "Sign up" page**. The first account is created
with one command on the server:

```bash
cd ~/ciet-bot
docker compose exec api python -m scripts.reset_admin --email you@your-college.edu
```

- It asks for a password **twice**, with typing hidden — choose a strong one.
- The password is never shown, logged, or emailed anywhere. **Do not lose it.**

Then sign in at `https://assistant.example.edu/admin/`:

1. Enter email + password.
2. A **six-digit code** is emailed to you (this is why SMTP was configured in
   Step 3.4). Enter it — you are in.
3. *Didn't receive the email?* Check spam. In the very first local setup mode
   the mail may instead be waiting inside the server — read it with:

   ```bash
   docker compose exec api sh -c 'f=$(ls -t storage/mail-outbox | head -1); cat "storage/mail-outbox/$f"'
   ```

Every future login works the same way: password, then the emailed code.

---

# PART C — Load the bot's knowledge (this is what makes it smart)

A brand-new installation answers honestly: *"I don't have that information
yet."* That is the safety design — it never guesses. Feed it content:

1. Go to `https://assistant.example.edu/admin/`.
2. **FAQs → Add**: the questions students actually ask (admission dates, fee
   structure, hostel, transport, contacts). Write both the question and the
   approved answer.
3. **Metrics → Add**: sensitive numbers (placement percentage, fee amounts,
   lab counts). These are shown **exactly as entered** and are never left to
   the AI to phrase — this is what guarantees no invented statistics.
4. **Documents → Upload**: prospectus, syllabus, policies (PDF, DOCX, XLSX,
   TXT — each file is virus-scanned). Watch the status column change to
   **`indexed`** — until then, its content is not searchable. Slow? Check the
   librarian: `docker compose logs -f worker`.
5. Refresh, ask the same questions in the preview at
   `https://assistant.example.edu/widget/` — you should now get real answers
   drawn from your own uploaded content. The chat shows only the clean answer;
   where each answer came from is recorded automatically for auditing.

Revisit this whenever fees, placements, or policies change. Also skim
**Feedback** and **Analytics** regularly — they show what students ask and
where answers were unhelpful.

---

# PART D — Go live (switch on full production security)

The app deliberately **refuses to start in production mode until everything
below is in place**, and tells you exactly what is missing. Do this as the
final step, after Parts A–C work.

## D.1 What production mode requires (checklist)

| Requirement | Where to set it | How |
| --- | --- | --- |
| `ENVIRONMENT=production` | `.env` | change `local` → `production` after the items below are all filled |
| Strong `JWT_SECRET` (64+ characters) | `.env` | already done in Step 3.4 |
| HTTPS origins, real host names | `.env` | already done in Step 3.4 (`API_BASE_URL`, `WIDGET_ORIGIN`, `ADMIN_ORIGIN`, `ALLOWED_HOSTS`, `ALLOWED_WIDGET_DOMAINS`) |
| At least one LLM key | `.env` | already done in Step 3.4 |
| Real SMTP | `.env` | already done in Step 3.4 |
| Virus scanner (ClamAV) | nothing to do — **already provided** by `docker-compose.prod.yml` | — |
| All four WhatsApp values | `.env` | **D.2 below** |

## D.2 Get the four WhatsApp values from Meta (~15 minutes)

1. Go to <https://developers.facebook.com> → **Create App** → type
   *Business* → name it (e.g. "CIET Assistant") → Create app.
2. Add the **WhatsApp** product to the app.
3. Open **App settings → Basic** → copy the **App Secret**
   → `WHATSAPP_APP_SECRET`.
4. Open **WhatsApp → API Setup** (or *Getting started*) → copy the **Phone
   number ID** → `WHATSAPP_PHONE_NUMBER_ID`.
5. For a permanent token: **Business Settings → System users → Add** (role
   Admin) → *Generate new token* → tick the WhatsApp permission → copy the
   token → `WHATSAPP_ACCESS_TOKEN`. (The temporary token on the API Setup
   page expires after 24 hours — the permanent one does not.)
6. Paste the random value you generated earlier
   (`openssl rand -hex 16`) → `WHATSAPP_VERIFY_TOKEN`.

> **Do you need WhatsApp right now?** It is *required by the production
> setting itself*. If you truly cannot create the Meta app yet, you can keep
> `ENVIRONMENT=local` or `staging` for an internal preview — but **staging and
> local are not hardened for public launch** (they do not use secure cookies
> and have relaxed checks). For a real public launch, complete this step.

## D.3 Switch over

1. Edit `.env`: fill the four `WHATSAPP_*` lines and change the first line to
   `ENVIRONMENT=production`.
2. Restart only the parts affected:

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --force-recreate api worker
   ```

3. **Check it started.** Production mode fails closed on *any* missing or weak
   setting and prints the exact problem:

   ```bash
   docker compose logs --tail=50 api
   ```

   If you see `...must be set for production`, fix that line in `.env` and
   repeat step 2.
4. Confirm readiness again: visit `https://assistant.example.edu/readyz` →
   `"ai":"configured"`.
5. Sign out and sign in once to confirm the full login still works (cookies
   are now marked `Secure`, which is expected).

**Your site is now running in production mode.** 🎉

---

# PART E — Put the chatbot on the college website

## E.1 One-time allow-listing (already done if you copied Step 3.4)

The bot only answers websites you trust. These two lines in `.env` must
contain the college website's exact address (with `https://` and `www.` if the
browser shows `www.`):

```env
ALLOWED_WIDGET_DOMAINS=www.your-college.edu,your-college.edu
CORS_ORIGINS_EXTRA=https://www.your-college.edu,https://your-college.edu
```

After any change:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --force-recreate api worker
```

> Origins are written as `scheme://host` with **no trailing slash**. If the
> widget ever fails with a CORS/403 error, the most common cause is a typo
> mismatch (e.g. the site is `www.` but you listed it without `www.`).

## E.2 Add two lines to the website's HTML

Your server hosts the widget file itself — no extra hosting or build step is
needed. The bot serves it at:

```text
https://assistant.example.edu/ciet-ai.js
```

Open the college website's **site-wide footer code** (the place where
analytics/tracking scripts are usually pasted) and add:

```html
<script>
  window.CIET_AI_CONFIG = {
    apiUrl: "https://assistant.example.edu",   /* REQUIRED: your bot's address */
    tenant: "ciet",
    position: "bottom-right",                  /* or "bottom-left" */
    primaryColor: "#1a56db",                   /* optional: button/brand colour */
    privacyUrl: "https://www.your-college.edu/privacy" /* optional */
  };
</script>
<script src="https://assistant.example.edu/ciet-ai.js" defer></script>
```

**Where exactly to paste it, by website type:**

| Website type | Where the footer script goes |
| --- | --- |
| Plain HTML site | Immediately before `</body>` in each page's template (or the shared footer file) |
| WordPress | A plugin such as **WPCode** ("Insert Headers and Footers") → paste into the **Footer** section so it appears on every page. ⚠ Ask your developer before editing theme files |
| Wix | *Settings → Custom code → Footer* → paste → publish |
| Squarespace | *Website → Settings → Advanced → Code Injection → Footer* |
| Site managed by an external agency | Send them this section — it is two script tags plus the allow-list restart |

> ⚠ **`apiUrl` is mandatory.** If you leave it out, the widget falls back to
> `http://localhost:8000` and will only work on your developer's own laptop.

## E.3 Test it like a student would

1. Open the college homepage and press **Ctrl+Shift+R** (hard refresh, to
   clear cache).
2. A chat launcher bubble should appear in the chosen corner — **on desktop
   and on a phone**.
3. Ask: *"What are the lab facilities?"* → you should get a real answer from
   your content, or an honest fallback if you have not loaded that content yet
   (Part C).
4. Open the language menu and switch to **తెలుగు** and **हिन्दी** — the
   interface **and the whole conversation, including messages you asked
   earlier, should switch language with you**.
5. Ask a nonsense question → you should get the safe "I don't have that"
   style answer, **not** a made-up one.
6. From another device (your phone on mobile data), repeat steps 1–3.

Programmers embedding the widget can also open it on demand with:

```js
window.CIETAI.open();
```

---

# PART F — Keeping it running (daily operations)

## F.1 Nightly backups

```bash
crontab -e
```

Paste this line (it saves a database backup at 02:15 every day; adjust the
folder if you like):

```cron
15 2 * * * mkdir -p $HOME/backups && cd $HOME/ciet-bot && ./scripts/backup-postgres.sh $HOME/backups/ciet-$(date +\%F).dump >/dev/null 2>&1
```

Keep copies **off the server** too (download weekly, or use your provider's
snapshot feature). Restore instructions live in
[docs/production-runbook.md](docs/production-runbook.md) — **⚠ hand the actual
restore to a developer**, and never test it on the live server first.

## F.2 Updating to a new version

```bash
cd ~/ciet-bot
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## F.3 Reading logs (what is actually happening)

```bash
docker compose logs -f --tail=100 api worker     # live feed; Ctrl+C to exit
```

## F.4 Health monitoring

Bookmark `https://assistant.example.edu/readyz` — `"ai":"configured"` plus HTTP
200 means everything is fine. Point any free uptime monitor (UptimeRobot,
Healthchecks.io, …) at that address so you get an email if the bot goes down.

## F.5 Disk space

ClamAV's virus database and Docker images need ~1–2 GB. Check with `df -h`.
To clean old images only (never use `-v`, that deletes data):

```bash
docker image prune -f
```

## F.6 What it costs (typical)

| Item | Typical cost |
| --- | --- |
| Server (4 GB VPS) | ~$16–24/month (or college hardware: ₹0) |
| Domain | Already owned by the college |
| Docker, Caddy, ClamAV, PostgreSQL, Redis | Free (open source) |
| Gemini / Groq API keys | Free tiers available; great for launch |
| OpenAI API key | Pay per use (only when you switch to it) |
| Pinecone | Free starter tier fits a college knowledge base |
| SMTP | Free on Gmail app passwords / college mail; SendGrid free tier otherwise |
| Meta WhatsApp | Free customer-service window; per-conversation pricing afterwards |
| This project's code | Free for CIET institutional use |

---

# PART G — When something goes wrong

| What you see | What it means | What to do |
| --- | --- | --- |
| Website won't open at all | DNS not ready or firewall/proxy down | `ping your-domain` (must show your IP); `sudo systemctl status caddy` (must be active); `sudo ufw status` (80/443 allowed) |
| No padlock / "not secure" | Certificate not issued yet | Confirm Step 2 DNS is correct, then `sudo systemctl reload caddy`; for details check `sudo journalctl -u caddy -n 50` |
| `/readyz` says AI not configured | No usable LLM key | Re-check `GEMINI_API_KEY` (or OpenAI/Groq) in `.env`, then §3.5's restart command for `api worker` |
| App refuses to start after editing `.env` | Production validation found a missing/weak setting | `docker compose logs --tail=50 api` — it names the exact setting; fix it and restart `api worker` |
| Widget launcher doesn't appear | Snippet missing/wrong, or cached page | Verify both script tags are on the page with correct `apiUrl`; Ctrl+Shift+R; check the browser's console (F12) for red errors |
| Widget appears but answers fail with 403/CORS | Website not allow-listed | Add its exact origin to `ALLOWED_WIDGET_DOMAINS` **and** `CORS_ORIGINS_EXTRA`, restart `api worker` (§E.1) |
| Widget works on your PC but not for a colleague | Browser privacy extensions/strict cookie settings block the visitor cookie | Retest in a normal or private window without extensions |
| Every answer is the safe fallback | Knowledge base is empty or documents not indexed | Part C: add FAQs; wait for status `indexed`; `docker compose logs -f worker` |
| Documents stuck at "queued/processing" | Worker or ClamAV problem | `docker compose logs -f worker`; if `clamav` shows unhealthy, give the server more memory (or add swap, §3.9) |
| Login says SMTP/`BLOCKED — EXTERNAL CONFIGURATION REQUIRED` | Email not configured (or you are in staging/production without SMTP) | Re-check the five `SMTP_*` lines, restart `api worker` |
| No login email arrives | Wrong SMTP credentials, spam folder, or provider blocks the app | Verify with a test tool ⚠; Gmail requires an **App Password**, not the normal password |
| WhatsApp messages not replying | Channel not enabled yet | Complete Part D.2; check Meta's **App Dashboard → WhatsApp → API Setup** shows your number; `docker compose logs api \| grep -i whatsapp` |
| Server runs out of memory | ClamAV + stack on a small server | Add swap (§3.9) or move to a 4 GB server |

## §3.9 Add swap (only for 2 GB servers)

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h    # must show a "Swap" line with 2.0Gi
```

---

# PART H — Handing over to a developer

Everything above can be done by a careful non-technical person, but keep your
developer in the loop for:

- **⚠ Restores** from backup and any database surgery
- **⚠ Certificate problems** that survive a DNS check + Caddy reload
- **⚠ Custom domains** (running the bot on a second domain, sub-paths, or
  behind an existing college reverse proxy — tell them the Caddyfile must then
  route `/api/*`, `/healthz`, and `/readyz` to `127.0.0.1:8000` and everything
  else to `127.0.0.1:8080`)
- **⚠ Load/performance checks** before a high-traffic event (admission
  season): `python scripts/load_test.py`
- **⚠ Optional monitoring stack**: [deploy/prometheus.yml](deploy/prometheus.yml)
  and [deploy/grafana-dashboard.json](deploy/grafana-dashboard.json)

Point them at these files — they document the system in depth:

| File | Contents |
| --- | --- |
| [README.md](README.md) | Architecture, features, Hybrid RAG, full developer setup, test suites, project status |
| [docs/deployment-guide.md](docs/deployment-guide.md) | Technical deployment prerequisites |
| [docs/architecture.md](docs/architecture.md) | Components, answer flow, security flows, trust boundaries |
| [docs/api.md](docs/api.md) | API endpoint reference |
| [docs/production-runbook.md](docs/production-runbook.md) | Health checks, incident response, backup/restore, rollback |
| [docs/known-limitations.md](docs/known-limitations.md) | Honest list of what still needs external credentials |
| [SECURITY.md](SECURITY.md) | Threat model and hardening summary |
| [docker-compose.prod.yml](docker-compose.prod.yml) | Exactly what the production overlay changes (ClamAV + private ports) |

---

### Quick command reference (print this)

```bash
# Status
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps

# Start / stop / restart
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
docker compose -f docker-compose.yml -f docker-compose.prod.yml down        # NEVER add -v on the server
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --force-recreate api worker   # after .env edits

# Logs
docker compose logs -f --tail=100 api worker

# Health
curl -s https://assistant.example.edu/healthz
curl -s https://assistant.example.edu/readyz

# First admin account (local setup phase only)
docker compose exec api python -m scripts.reset_admin --email you@your-college.edu

# Daily backup (manual run)
./scripts/backup-postgres.sh $HOME/backups/manual.dump
```
