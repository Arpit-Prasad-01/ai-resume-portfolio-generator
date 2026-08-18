# AI-Assisted Resume Portfolio Generator

A Flask web app that converts a resume (PDF or TXT) into a clean, downloadable
portfolio webpage using the Gemini API.

**Group:** G55 (B.Tech CSE AIML)

---

## 1. Team / Contributors (G55)
- Arpit Prasad Sharma
- Eklavya Singh
- Ashwin Sharma
- Daksh Gautam
- Devkinandan Dubey

---

## 2. Project Overview

A user signs up, logs in, and uploads their resume. The app reads and cleans
the resume text, sends it to Gemini with a controlled prompt, receives
structured JSON back, and renders it into a portfolio page. The portfolio can
also be exported as a standalone `portfolio.html` file.

---

## 3. Tech Stack

| Technology | Purpose |
|---|---|
| Python / Flask | Web server, routing, session management |
| Gemini API (`gemini-3.7-flash`) | Extracts structured resume data |
| SQLite | Stores user accounts (signup/login) |
| pypdf | Extracts text from uploaded PDF resumes |
| HTML / CSS | Portfolio page rendering |

---

## 4. Setup Instructions

1. **Clone the repository**
```bash
   git clone <your-repo-url>
   cd resume-portfolio-generator/server
```

2. **Create a virtual environment (recommended)**
```bash
   python -m venv venv
   venv\Scripts\activate      # Windows
   source venv/bin/activate   # macOS/Linux
```

3. **Install dependencies**
```bash
   pip install -r requirements.txt
```

4. **Set up your API key**
   - Copy `.env.example` to `.env`
   - Get a free Gemini API key from [Google AI Studio](https://aistudio.google.com/)
   - Fill it in:
    GEMINI_API_KEY=your_actual_key_here


5. **Run the app**
```bash
   python app.py
```
   Visit `http://127.0.0.1:5000` in your browser.

---

## 5. Workflow

1. User signs up / logs in (SQLite-backed auth, password hashed with Werkzeug).
2. Logged-in user uploads a resume (`.pdf` or `.txt`) on the dashboard.
3. Flask extracts text (`pypdf` for PDFs) and cleans it (strips blank lines/extra spaces).
4. A controlled prompt + cleaned resume text is sent to the Gemini API.
5. Gemini returns structured JSON (name, headline, summary, skills, education,
   experience, projects, achievements, contact).
6. The JSON is safely parsed; missing fields default to empty values.
7. The data is stored server-side (keyed by user ID) and rendered into
   `result.html` as the portfolio page.
8. User can download the portfolio as a standalone `portfolio.html` — the
   CSS is inlined and the app's nav/buttons are stripped so it works as a
   clean, independent file.

---

## 6. Prompt Design

The prompt sent to Gemini explicitly instructs it to:
- Use **only** information present in the resume text.
- **Never invent** skills, experience, projects, achievements, companies,
  dates, or links.
- Return **only valid JSON** (no markdown, no extra explanation) with a
  fixed set of fields.
- Use empty strings/lists for any information not found in the resume.

This keeps the model's output predictable and directly parseable, and
minimizes the risk of fabricated content appearing in someone's portfolio.

---

## 7. Error Handling

| Case | Behavior |
|---|---|
| Missing/empty resume file | Clear error shown, request rejected |
| Resume text too short (<30 chars) | Rejected with a message |
| Missing `GEMINI_API_KEY` | Raises a configuration error, doesn't crash |
| Gemini API failure | Caught and shown as an error message |
| Invalid/non-JSON Gemini response | Caught, user asked to try again |
| Not logged in | Redirected to `/login` via `@login_required` |

---

## 8. Limitations & Hallucination Risks

- Gemini output is a **draft**. Even with strict prompting, the model can
  occasionally misread or slightly reword resume content — **always verify
  the generated portfolio against the original resume before sharing it.**
- Very unusual resume formats (heavy tables, columns, scanned/image-only
  PDFs) may extract poorly via `pypdf`, leading to incomplete sections.
- Portfolio data is stored **in-memory** (`portfolio_store` dict) on the
  server, not persisted to a database — it resets if the server restarts.
- No rate-limiting on the Gemini API calls; heavy concurrent use could hit
  API quota limits.

---

## 9. Responsible AI & Privacy

- Do not upload resumes containing passwords, government ID numbers, or
  financial details — this project is for demonstration/testing purposes.
- Never commit the real `.env` file or API key to GitHub (`.gitignore`
  already excludes it).
- Gemini is never called from client-side JavaScript — all calls happen
  server-side so the API key is never exposed to the browser.

---

## 10. AI Usage Log

| AI Tool Used | Prompt/Request | What It Generated | What Was Changed/Corrected |
|---|---|---|---|
| ChatGPT / Gemini | Fix session storage bug in `/generate` and `/download` | Replaced session-based storage with server-side `portfolio_store` dict | Verified data persists correctly for larger resumes; added cleanup on logout |
| ChatGPT / Gemini | Fix standalone downloaded portfolio missing CSS | Inlined `style.css` content into the downloaded `portfolio.html` | Verified the exported file renders correctly with no live server running |

---

## 11. Project Structure

resume-portfolio-generator/
  server/
    app.py
    requirements.txt
    .env.example
    .gitignore
    templates/
      home.html
      signup.html
      login.html
      index.html
      result.html
      about.html
    static/
      style.css
    README.md

