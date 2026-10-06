# Budget Buddy

Budget Buddy is a personal expense and budget tracker made for students (age 13 and up). You log what you spend, set a monthly budget, and the app shows where your money goes and gives simple tips. It runs in the browser and can be installed on a phone or computer like an app.

## Features

**Account**
- Sign up with an age group and consent, then confirm your email with a 6-digit code.
- Log in, reset a forgotten password with an emailed code, change your password.
- Settings page, and you can delete your account and data.
- A short tutorial for new users, plus Help, Privacy and Terms pages.

**Expenses**
- Add expenses by typing, by voice, or by photographing a receipt (the receipt is read by Google Gemini).
- Recurring expenses (daily, weekly, monthly or yearly) that are added for you.
- History with search and filters, and export to CSV, Excel or PDF.

**Budgets**
- A monthly budget per user, with past months kept in budget history.
- Carry-over (on by default, can be turned off in Settings): last month's budget is copied into the new month, so the dashboard is never empty on the 1st.

**Insights and help**
- Coach Insight: rules decide what matters in your spending, and AI writes the tip.
- Monthly reports with AI commentary.
- "Ask Buddy": a chat where you ask questions about your spending.

**Notifications**
- In-app notifications, plus web push notifications on devices that allow them.
- Push messages from the app itself stay quiet at night (10 PM to 8 AM).

## How it is built

| Part | Technology | Where |
| --- | --- | --- |
| API (the server) | Python, FastAPI, SQLAlchemy | `Backend/` |
| Database | SQLite on your computer, Postgres (Neon) when deployed | `Backend/database.py` |
| Database changes | Alembic migrations, run automatically on start | `Backend/alembic/` |
| Website | Plain HTML and JavaScript, Tailwind CSS | `Frontend/` |
| AI features | Google Gemini | `Backend/services/gemini_client.py` |
| Email | Brevo HTTPS API, or Gmail SMTP | `Backend/services/email_service.py` |
| Push notifications | Web Push (VAPID) | `Backend/services/push_service.py` |
| Hosting | Render (API and site), Neon (database) | `render.yaml` |

## Run it on your computer

You need Python 3.11 and Node.js (Node only if you change the styling). Open two terminal windows.

**1. Backend (the API)**

```
cd Backend
pip install -r requirements.txt
cp .env.example .env
```

Open `Backend/.env` and fill in the values (see Configuration below). At minimum set `JWT_SECRET`. To make one:

```
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Then start the server:

```
python3 -m uvicorn main:app --reload --port 8000
```

The API is now at http://127.0.0.1:8000. With `DATABASE_URL` left empty, it creates a SQLite file called `Backend/database.db` for you. If no email is set up, sign-up skips the email confirmation step, so you can still create an account.

**2. Frontend (the website)**

```
cd Frontend
python3 -m http.server 5500
```

Open http://127.0.0.1:5500/HTML's/login.html. The backend only accepts a few local addresses, and port 5500 is one of them. When you open the site from your own computer, it talks to the API on port 8000 automatically.

**3. Tests**

```
cd Backend
python3 -m pytest -q
```

The tests use a throwaway database. They never call the real AI, email or push services, and never touch `database.db`.

**Changing styles.** The site uses Tailwind CSS. After you change classes in the HTML, rebuild the stylesheet (`Frontend/css/app.css` is committed to the repo):

```
cd Frontend
npm install
npm run build:css
```

## Configuration

Settings are read from environment variables. Locally they live in `Backend/.env` (never commit this file; it is in `.gitignore`). On Render you enter them in the dashboard. The values below are only descriptions; get your own real ones.

| Name | What it is for | Required? | Where to get it |
| --- | --- | --- | --- |
| `JWT_SECRET` | Signs login tokens. At least 32 characters. | Required | Make it with the command above. Render makes one for you. |
| `DATABASE_URL` | Which database to use. Empty means local SQLite. | Required in production | Neon dashboard, connection string (`postgresql://...?sslmode=require`). |
| `FRONTEND_ORIGINS` | The website address(es) allowed to call the API, comma-separated. | Required in production | The URL of your Render site, such as `https://budget-buddy.onrender.com`. |
| `APP_ENV` | Set to `production` on the live server. Hides the API docs, removes local addresses from the allowed list, turns on HTTPS-only. | Production only | Type `production`. Leave it unset locally. |
| `APP_TIMEZONE` | Timezone for "today", reminders and quiet hours. Default `Asia/Kolkata`. | Optional | A name from the tz database, such as `Europe/London`. |
| `GEMINI_API_KEY` | Turns on receipt scan, voice entry, tips, reports and chat. | Optional (AI features stop working without it) | Google AI Studio (aistudio.google.com), "Get API key". |
| `GEMINI_MODEL`, `GEMINI_FALLBACK_MODEL` | Which Gemini models to use. Defaults are `gemini-flash-lite-latest` and `gemini-flash-latest`. Not listed in `.env.example`. | Optional | Google's model list. |
| `BREVO_API_KEY` | Sends email over HTTPS. Use this on the live server. | Optional locally, needed live | brevo.com, SMTP & API, API keys. |
| `EMAIL_FROM` | The "From" address, like `Budget Buddy <you@example.com>`. Must be a verified sender in Brevo. | Needed with Brevo | The sender you verify in Brevo. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` | Sends email through Gmail on your own computer. Leave empty when using Brevo. | Optional | Gmail address and an App Password from myaccount.google.com/apppasswords. |
| `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` | Keys for web push notifications. | Optional (no push without them) | Run `python3 scripts/generate_vapid_keys.py` inside `Backend/`. |
| `VAPID_SUBJECT` | A `mailto:` contact address that push services can reach. | Optional | Your own email, written as `mailto:you@example.com`. |
| `API_BASE` | (Render site only) The API's address, baked into the site when it is built. | Required for the site | The URL of your Render API service. |
| `PYTHON_VERSION`, `NODE_VERSION` | Language versions on Render. | Already set in `render.yaml` | Nothing to do. |
| `TEST_DATABASE_URL` | Lets the tests run on a throwaway Postgres instead of SQLite. | Optional | Your own test database. Never the live one. |

Changing the VAPID keys later logs out every device from push notifications, so create them once per environment.

## Deploying (free)

You will use Render (hosting), Neon (database), Brevo (email) and a pinger (keeps the server awake). Everything below has a free plan.

1. Push this repository to GitHub.
2. Create a free Postgres database on neon.tech. Copy its connection string. This is your `DATABASE_URL`.
3. Create a free account on brevo.com. Verify your sender address, then create an API key. These are `EMAIL_FROM` and `BREVO_API_KEY`. (Render's free servers block normal SMTP email, which is why Brevo is used.)
4. Get a Gemini key from aistudio.google.com. This is `GEMINI_API_KEY`.
5. Make push keys on your computer: `cd Backend`, then `python3 scripts/generate_vapid_keys.py`. Keep the three printed lines for the next step.
6. On render.com choose New, then Blueprint, and pick your repository. Render reads `render.yaml` and creates two services: `budget-buddy-api` (the server) and `budget-buddy` (the website). It asks for each value marked as needed. Fill in `DATABASE_URL`, `GEMINI_API_KEY`, `BREVO_API_KEY`, `EMAIL_FROM` and the three VAPID values. For now, enter any placeholder text for `FRONTEND_ORIGINS` and `API_BASE`.
7. Fix the "chicken and egg" problem. Each service needs the other's address, and you only learn those after both exist. Once both are created, copy their URLs from the Render dashboard, then:
   - On the website service (`budget-buddy`), set `API_BASE` to the API's URL, for example `https://budget-buddy-api.onrender.com`.
   - On the API service (`budget-buddy-api`), set `FRONTEND_ORIGINS` to the website's URL, for example `https://budget-buddy.onrender.com`.
   - Use `https://` and no slash at the end.
8. Redeploy both services (Manual Deploy, then Deploy latest commit). The site only learns the API address when it is built, so it must be rebuilt.
9. Set up a free pinger on uptimerobot.com or cron-job.org. Make it request the API's address (the `/` page) every 10 minutes. Without it the free server falls asleep, and reminders stop until someone visits.
10. Open your website URL and sign up to test.

The database tables are created and updated automatically each time the API starts. You do not run anything by hand.

## Changing the database

Do not edit tables by hand. Use Alembic, which keeps a numbered history of changes in `Backend/alembic/versions/`.

1. Change the model in `Backend/models/`. A brand-new model file must also be imported in `Backend/models/__init__.py`.
2. In the `Backend` folder, point `DATABASE_URL` at a throwaway SQLite file, never real data, and run `alembic revision --autogenerate -m "short description"`.
3. Open the new file in `alembic/versions/` and read it. It is a draft: it cannot tell a rename from a delete plus an add.
4. Commit the model change and the new migration file together.

The migration is applied automatically the next time the server starts, locally and live. A test fails if you change a model but forget the migration. The full explanation is at the top of `Backend/migrations_runner.py`.

## Security notes

- Passwords are hashed with bcrypt. Plain passwords are never stored.
- Login tokens last 30 minutes and are tied to the current password, so changing or resetting it logs out all other sessions.
- Rate limits protect login, sign-up, password reset, email codes and AI features.
- Every query is filtered by the logged-in user, so people only see their own data.
- Inputs have length and size limits (for example notes, names, passwords and amounts).
- The site loads no third-party scripts, fonts or trackers. Fonts, Tailwind and Chart.js are served from the repo.
- The built site adds a Content-Security-Policy that only allows its own files and the API. Both the site and the API also send security headers.
- API docs are hidden when `APP_ENV=production`.

## Known limitations

- Rate limits are kept in memory, and the reminder scheduler runs inside the server process. Run exactly one server process, or limits and reminders will misbehave.
- The free Render server sleeps after a while without traffic. Use the pinger from the deploy steps.
- Gemini is used on its free tier. It has usage limits, and Google may use what is sent to improve its products (this is explained on the Privacy page). Do not put sensitive details in receipts, voice entries or chat.
- Money is stored as floating-point numbers, which can give tiny rounding differences.
- The database does not stop a user from having two budgets for the same month.
- Only the web push channel is implemented. The Android and iOS delivery files are placeholders.

## Project layout

```
.
├── README.md
├── render.yaml                    Render Blueprint (API + website)
├── Backend/
│   ├── main.py                    App entry point, CORS, security headers
│   ├── database.py                Database connection
│   ├── migrations_runner.py       Runs Alembic migrations at startup
│   ├── alembic/                   Database migration history
│   ├── routes/                    API endpoints (expenses, budgets, auth, ...)
│   ├── services/                  The logic behind the endpoints (AI, email, push, export)
│   ├── models/                    Database tables
│   ├── schemas/                   Request and response shapes, input limits
│   ├── auth/                      Password hashing and login tokens
│   ├── scripts/                   generate_vapid_keys.py
│   ├── tests/                     Automated tests (pytest)
│   ├── requirements.txt           Python packages
│   └── .env.example               Template for your own .env
├── Frontend/
│   ├── HTML's/                    The pages, web app manifest, service worker
│   ├── Javascript's/              Page scripts (api.js talks to the API)
│   ├── css/                       Tailwind input and built app.css
│   ├── Assets/                    Logo, icons, fonts
│   ├── vendor/                    Self-hosted Chart.js
│   ├── build.js                   Builds the deployable dist/ folder
│   └── package.json               Build commands
└── stitch_budgetbuddy_ui_design_system/   Design mock-ups and style guide
```
