import os, json, re, io, sqlite3
from flask import Flask, render_template, request, session, send_file, redirect, url_for, render_template_string
from dotenv import load_dotenv
import google.generativeai as genai
from pypdf import PdfReader
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

# Aapke list_models.py ke mutabiq standard flash model use karein
MODEL_NAME = "gemini-3.7-flash"

app = Flask(__name__)
app.secret_key = "resume-portfolio-secret-key-2026"
DB_FILE = "users.db"

REQUIRED_FIELDS = ["name", "headline", "summary", "skills", "education",
                   "experience", "projects", "achievements", "contact"]

# ---------- In-memory portfolio store ----------
# Session cookies have a ~4KB size limit, and a full resume JSON (skills +
# experience + projects + achievements) can easily exceed that. Storing it
# in the session would silently fail to save on larger resumes. Instead we
# keep it in a simple server-side dict keyed by user_id.
# NOTE: this resets on server restart. For persistence across restarts,
# move this into a SQLite table instead.
portfolio_store = {}

# ---------- Database setup ----------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

def login_required(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper

# ---------- Auth routes ----------
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            return render_template("signup.html", error="All fields are required.")

        conn = sqlite3.connect(DB_FILE)
        existing = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        if existing:
            conn.close()
            return render_template("signup.html", error="Email already registered. Please login.")

        password_hash = generate_password_hash(password)
        conn.execute("INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                     (name, email, password_hash))
        conn.commit()
        conn.close()

        return redirect(url_for("login"))

    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = sqlite3.connect(DB_FILE)
        user = conn.execute("SELECT id, name, password_hash FROM users WHERE email=?", (email,)).fetchone()
        conn.close()

        if not user or not check_password_hash(user[2], password):
            return render_template("login.html", error="Invalid email or password.")

        session["user_id"] = user[0]
        session["user_name"] = user[1]
        return redirect(url_for("generator_page"))

    return render_template("login.html")

@app.route("/logout")
def logout():
    # Clean up this user's stored portfolio data along with the session
    portfolio_store.pop(session.get("user_id"), None)
    session.clear()
    return redirect(url_for("home"))

# ---------- Generator routes (protected) ----------
@app.route("/generator")
@login_required
def generator_page():
    return render_template("index.html", user_name=session.get("user_name"))

@app.route("/about")
def about():
    return render_template("about.html")

def extract_text(file):
    filename = file.filename.lower()
    if filename.endswith(".pdf"):
        reader = PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text
    else:
        return file.read().decode("utf-8", errors="ignore")

def clean_text(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)

def build_prompt(resume_text):
    return f"""
You are a resume parser. Use ONLY the information present in the resume text below.
Do NOT invent skills, experience, projects, achievements, companies, dates, or links.
If information is missing, leave it as an empty string "" or empty list [].

Return ONLY valid JSON, no markdown, no explanation, with EXACTLY these fields:
{{
  "name": "", "headline": "", "summary": "",
  "skills": ["skill1"], "education": ["degree - institution - year"],
  "experience": ["role - company - duration: description"],
  "projects": ["title: description"], "achievements": ["achievement1"],
  "contact": "email | phone | linkedin | github"
}}

Resume text:
\"\"\"{resume_text}\"\"\"
"""

def call_gemini(prompt):
    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set in .env")
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel(MODEL_NAME)
    response = model.generate_content(prompt)
    raw = response.text.strip()
    raw = re.sub(r"^```json|```$", "", raw, flags=re.MULTILINE).strip()
    return raw

def parse_json_safely(raw_text):
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        return None
    for field in REQUIRED_FIELDS:
        if field not in data:
            data[field] = "" if field not in ["skills", "education", "experience", "projects", "achievements"] else []
    return data

@app.route("/generate", methods=["POST"])
@login_required
def generate():
    file = request.files.get("resume_file")

    if not file or file.filename == "":
        return render_template("index.html", error="Please upload a resume file (.txt or .pdf).", user_name=session.get("user_name"))

    try:
        raw_text = extract_text(file)
    except Exception as e:
        return render_template("index.html", error=f"Could not read file: {e}", user_name=session.get("user_name"))

    resume_text = clean_text(raw_text)

    if not resume_text or len(resume_text) < 30:
        return render_template("index.html", error="Resume text is missing or too short.", user_name=session.get("user_name"))

    prompt = build_prompt(resume_text)

    try:
        raw_response = call_gemini(prompt)
    except Exception as e:
        return render_template("index.html", error=f"Gemini API error: {e}", user_name=session.get("user_name"))

    data = parse_json_safely(raw_response)
    if data is None:
        return render_template("index.html", error="Gemini returned invalid JSON. Please try again.", user_name=session.get("user_name"))

    # Store server-side (keyed by user_id) instead of in the session cookie,
    # since the cookie has a ~4KB limit that a full resume JSON can exceed.
    portfolio_store[session["user_id"]] = data
    return render_template("result.html", data=data)

@app.route("/download")
@login_required
def download():
    data = portfolio_store.get(session["user_id"])
    if not data:
        return render_template("index.html", error="No portfolio to download. Please generate one first.", user_name=session.get("user_name"))

    # Render template as string
    html_content = render_template("result.html", data=data)

    # INLINE THE CSS: "/static/style.css" only resolves while the file is
    # served by this Flask app. Once downloaded and opened standalone
    # (double-click, no server running), that link breaks and the page
    # looks unstyled. So we read style.css and embed it directly.
    css_path = os.path.join(app.root_path, "static", "style.css")
    try:
        with open(css_path, "r", encoding="utf-8") as f:
            css_content = f.read()
        html_content = html_content.replace(
            '<link rel="stylesheet" href="/static/style.css">',
            f"<style>\n{css_content}\n</style>"
        )
    except FileNotFoundError:
        pass

    # DOWNLOAD HONE WALI FILE SE NAVBAR / BUTTONS KO HIDE KARNE KA LOGIC:
    clean_html = html_content.replace(
        '<nav class="home-nav"', '<nav style="display: none !important;"'
    )

    buffer = io.BytesIO(clean_html.encode("utf-8"))
    return send_file(buffer, as_attachment=True, download_name="portfolio.html", mimetype="text/html")

if __name__ == "__main__":
    app.run(debug=True)