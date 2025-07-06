import os
import telebot
from flask import Flask, request
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

from io import BytesIO

TOKEN = os.getenv("BOT_TOKEN")  # Set this in your environment
bot = telebot.TeleBot(TOKEN)
app = Flask(name)

# Default watermark text (you can extend to make dynamic later)
watermark_text = "CONFIDENTIAL"

# ➕ Create watermark PDF page
def create_watermark(text):
    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)
    can.setFont("Helvetica", 40)
    can.setFillColorRGB(0.6, 0.6, 0.6, alpha=0.3)
    can.saveState()
    can.translate(300, 500)
    can.rotate(45)
    can.drawCentredString(0, 0, text)
    can.restoreState()
    can.save()
    packet.seek(0)
    return PdfReader(packet)

# 🛠 Apply watermark to uploaded PDF
def apply_watermark(input_pdf, watermark_pdf):
    writer = PdfWriter()
    watermark_page = watermark_pdf.pages[0]
    for page in input_pdf.pages:
        page.merge_page(watermark_page)
        writer.add_page(page)

    output = BytesIO()
    writer.write(output)
    output.seek(0)
    return output

# 🤖 When a user sends a PDF
@bot.message_handler(content_types=['document'])
def handle_pdf(message):
    file_info = bot.get_file(message.document.file_id)
    downloaded = bot.download_file(file_info.file_path)
    input_pdf = PdfReader(BytesIO(downloaded))
    watermark = create_watermark(watermark_text)
    watermarked_pdf = apply_watermark(input_pdf, watermark)

    bot.send_document(message.chat.id, watermarked_pdf, visible_file_name="watermarked.pdf")

# ✅ Webhook endpoint for Render
@app.route(f"/{TOKEN}", methods=['POST'])
def webhook():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return '', 200

# 🌐 Root route
@app.route("/", methods=["GET"])
def index():
    return "Bot is running!"

# 🚀 Start
if name == "main":
    bot.remove_webhook()
    bot.set_webhook(url=f"https://your-app-name.onrender.com/{TOKEN}")  # Replace with your app's domain
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
