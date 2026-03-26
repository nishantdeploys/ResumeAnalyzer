import re
import pdfplumber
from docx import Document
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = "8284212500:AAHOnu9qV8LjJAXITjeR192DWvsLJdyWfjE"

user_data_store = {}

# -------- Extract PDF --------
def extract_pdf(file_path):
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text.lower()

# -------- Extract DOCX --------
def extract_docx(file_path):
    doc = Document(file_path)
    return "\n".join([para.text for para in doc.paragraphs]).lower()

# -------- Extract Based on Type --------
def extract_text(file_path, file_name):
    if file_name.endswith(".pdf"):
        return extract_pdf(file_path)
    elif file_name.endswith(".docx"):
        return extract_docx(file_path)
    else:
        return None

# -------- Keywords --------
def extract_keywords(text):
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    return set(words)

# -------- Score --------
def calculate_score(resume, jd):
    resume_words = extract_keywords(resume)
    jd_words = extract_keywords(jd)

    matched = resume_words & jd_words

    skill_score = len(matched) * 2
    keyword_score = len(matched)

    total = len(jd_words) * 2 if jd_words else 1

    score = int(((skill_score + keyword_score) / total) * 100)

    missing = list(jd_words - resume_words)

    return min(score, 100), matched, missing

# -------- START --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        """👋 *Welcome to AI Resume Analyzer Bot*

📌 *How to use:*
1️⃣ Upload Resume (PDF / DOCX) 📄  
2️⃣ Paste Job Description 🧾  
3️⃣ Get Match Score + Suggestions 🎯  

👉 Send your resume to begin!
""",
        parse_mode="Markdown"
    )

# -------- HANDLE FILE --------
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.document.get_file()
    file_name = update.message.document.file_name.lower()

    if not (file_name.endswith(".pdf") or file_name.endswith(".docx")):
        await update.message.reply_text("❌ Only PDF or DOCX files are supported.")
        return

    path = f"resume_{update.effective_user.id}.{file_name.split('.')[-1]}"
    await file.download_to_drive(path)

    text = extract_text(path, file_name)

    if not text:
        await update.message.reply_text("❌ Could not read file.")
        return

    user_data_store[update.effective_user.id] = {"resume": text}

    await update.message.reply_text("✅ Resume uploaded!\n👉 Now paste Job Description")

# -------- HANDLE JD --------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in user_data_store:
        await update.message.reply_text("⚠️ Upload resume first.")
        return

    jd = update.message.text.lower()
    resume = user_data_store[user_id]["resume"]

    score, matched, missing = calculate_score(resume, jd)

    verdict = "✅ *Strong Match*" if score >= 70 else "❌ *Needs Improvement*"
    confidence = round(score * 0.9, 2)

    suggestions = "\n".join([f"- Add: {m}" for m in missing[:5]])

    response = f"""
📊 *Resume Analysis Report*

🎯 Match Score: *{score}%*
{verdict}

🎯 Confidence: *{confidence}%*

✅ *Top Matching Skills:*
{', '.join(list(matched)[:5]) if matched else 'None'}

❌ *Missing Skills:*
{', '.join(missing[:5]) if missing else 'None'}

💡 *Suggestions:*
{suggestions if suggestions else '- Improve formatting and add projects'}

🚀 *Tip:* Use action verbs like *Developed, Built, Led*
"""

    await update.message.reply_text(response, parse_mode="Markdown")

# -------- RUN --------
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

print("🚀 Bot running...")
app.run_polling(drop_pending_updates=True)