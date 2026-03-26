import os
import json
import logging
import asyncio
import tempfile
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters, ConversationHandler
)
import pdfplumber
from google import genai  #
from resume_generator import generate_resume

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# States
JD, RESUME, FORMAT = range(3)

# Initialize Gemini Client
# It will automatically pick up the GEMINI_API_KEY from environment variables
client = genai.Client() 

# ── helpers ──────────────────────────────────────────────────────────────────

def extract_text_from_pdf(file_path: str) -> str:
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
    return text.strip()

def extract_text_from_docx(file_path: str) -> str:
    from docx import Document
    doc = Document(file_path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

def analyze_resume(jd: str, resume_text: str) -> dict:
    prompt = f"""You are an expert resume reviewer and career coach.
    
    Analyze the resume against the job description and respond with valid JSON:
    {{
      "score": <integer 1-10>,
      "score_breakdown": {{
        "skills_match": <integer 1-10>,
        "experience_relevance": <integer 1-10>,
        "keywords_match": <integer 1-10>,
        "overall_presentation": <integer 1-10>
      }},
      "strengths": ["string"],
      "gaps": ["string"],
      "recommendations": ["string"],
      "missing_keywords": ["string"],
      "improved_summary": "string",
      "candidate_name": "string",
      "candidate_email": "string",
      "candidate_phone": "string",
      "candidate_location": "string",
      "skills": ["string"],
      "experience": [
        {{"title": "string", "company": "string", "duration": "string", "bullets": ["string"]}}
      ],
      "education": [
        {{"degree": "string", "institution": "string", "year": "string"}}
      ],
      "certifications": ["string"]
    }}"""

    # Using Gemini 3 Flash for fast, cost-effective analysis
    response = client.models.generate_content(
        model="gemini-3-flash-preview", 
        contents=[f"JOB DESCRIPTION:\n{jd}\n\nRESUME:\n{resume_text}", prompt],
        config={
            'response_mime_type': 'application/json', # Native JSON enforcement
        }
    )
    
    return json.loads(response.text) # Gemini returns raw JSON string

def format_analysis_message(analysis: dict) -> str:
    score = analysis.get("score", 0)
    emoji = "🔴" if score <= 4 else "🟡" if score <= 6 else "🟢"
    bd = analysis.get("score_breakdown", {})
    strengths = "\n".join(f"  ✅ {s}" for s in analysis.get("strengths", []))
    gaps = "\n".join(f"  ❌ {g}" for g in analysis.get("gaps", []))
    recs = "\n".join(f"  💡 {r}" for r in analysis.get("recommendations", []))
    keywords = ", ".join(analysis.get("missing_keywords", []))

    msg = f"""
{emoji} *Resume Score: {score}/10*

📊 *Score Breakdown:*
  • Skills Match: {bd.get('skills_match', 'N/A')}/10
  • Experience Relevance: {bd.get('experience_relevance', 'N/A')}/10
  • Keywords Match: {bd.get('keywords_match', 'N/A')}/10
  • Presentation: {bd.get('overall_presentation', 'N/A')}/10

✅ *Strengths:*
{strengths}

❌ *Gaps Found:*
{gaps}

💡 *Recommendations to Improve:*
{recs}

🔑 *Missing Keywords to Add:*
{keywords}
"""
    return msg.strip()

# ── Handlers (Unchanged from original logic, just referencing Gemini) ──

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "👋 *Welcome to ResumeIQ Bot (Powered by Gemini 3)!*\n\n"
        "Paste the *Job Description* to begin.",
        parse_mode="Markdown"
    )
    return JD

async def receive_jd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["jd"] = update.message.text
    await update.message.reply_text("✅ JD saved! Now upload your *resume* (PDF/DOCX).", parse_mode="Markdown")
    return RESUME

async def receive_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = update.message.document
    if not file: return RESUME
    
    fname = file.file_name.lower()
    await update.message.reply_text("⏳ Gemini is analyzing your resume...")

    tg_file = await file.get_file()
    with tempfile.NamedTemporaryFile(suffix=os.path.splitext(fname)[1], delete=False) as tmp:
        tmp_path = tmp.name
    await tg_file.download_to_drive(tmp_path)

    try:
        resume_text = extract_text_from_pdf(tmp_path) if fname.endswith(".pdf") else extract_text_from_docx(tmp_path)
        analysis = analyze_resume(context.user_data["jd"], resume_text)
        context.user_data["analysis"] = analysis
        await update.message.reply_text(format_analysis_message(analysis), parse_mode="Markdown")
        
        keyboard = [
            [InlineKeyboardButton("📄 ATS", callback_data="fmt_ats"), InlineKeyboardButton("📝 Modern", callback_data="fmt_modern")],
            [InlineKeyboardButton("🎨 Creative", callback_data="fmt_creative"), InlineKeyboardButton("📋 Classic", callback_data="fmt_classic")],
            [InlineKeyboardButton("❌ Skip", callback_data="fmt_skip")]
        ]
        await update.message.reply_text("Choose a format for your optimized resume:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return FORMAT
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("⚠️ Something went wrong. Try /start again.")
        return ConversationHandler.END
    finally:
        if os.path.exists(tmp_path): os.unlink(tmp_path)

async def handle_format(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "fmt_skip": return ConversationHandler.END
    
    chosen = query.data.replace("fmt_", "")
    await query.edit_message_text(f"⏳ Generating your *{chosen.upper()}* resume...")
    
    try:
        pdf_path = generate_resume(context.user_data["analysis"], context.user_data["jd"], chosen)
        with open(pdf_path, "rb") as f:
            await query.message.reply_document(document=f, filename=f"Optimized_Resume_{chosen}.pdf")
        os.unlink(pdf_path)
    except Exception as e:
        await query.message.reply_text(f"⚠️ PDF Error: {e}")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return ConversationHandler.END

def main():
    app = Application.builder().token(os.environ.get("TELEGRAM_BOT_TOKEN")).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            JD: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_jd)],
            RESUME: [MessageHandler(filters.Document.ALL, receive_resume)],
            FORMAT: [CallbackQueryHandler(handle_format, pattern="^fmt_")]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(conv_handler)
    app.run_polling()

if __name__ == "__main__":
    main()
