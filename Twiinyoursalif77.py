import sqlite3
import os
import yt_dlp
from datetime import datetime

from telegram import Update
from telegram.ext import (
ApplicationBuilder,
CommandHandler,
MessageHandler,
ContextTypes,
filters
)

from openai import OpenAI

TOKEN = os.getenv("TOKEN")
OPENAI_KEY = os.getenv("OPENAI_KEY")

OWNER_ID=7395844524

client=OpenAI(api_key=OPENAI_KEY)

SYSTEM_PROMPT="""
انت صديق سعودي طبيعي.
تكلم بعفوية.

اذا سألك احد من صنعك قل:

أنا من تطوير عمي ياسر 👑
snap : scr7y
"""

# DATABASE

conn=sqlite3.connect("bot.db",check_same_thread=False)
cursor=conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS logs(
id INTEGER PRIMARY KEY AUTOINCREMENT,
user_id TEXT,
name TEXT,
username TEXT,
type TEXT,
content TEXT,
time TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS memory(
user_id TEXT,
role TEXT,
content TEXT
)
""")

conn.commit()

# SAVE LOG

def save_log(user,msg_type,content):

    name=user.full_name or "بدون اسم"
    username=user.username or "لايوجد"

    cursor.execute(
    "INSERT INTO logs(user_id,name,username,type,content,time) VALUES(?,?,?,?,?,?)",
    (
    user.id,
    name,
    username,
    msg_type,
    content,
    str(datetime.now())
    )
    )

    conn.commit()

# START

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
"هلا 👋 ارسل رسالة او صورة او فيديو او فويس"
)

# USERS

async def users(update:Update,context:ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id!=OWNER_ID:
        return

    cursor.execute("SELECT COUNT(DISTINCT user_id) FROM logs")

    count=cursor.fetchone()[0]

    await update.message.reply_text(f"👥 المستخدمين: {count}")

# CONVERSATIONS

async def conversations(update:Update,context:ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id!=OWNER_ID:
        return

    cursor.execute("""
    SELECT user_id,name,username,type,content
    FROM logs
    ORDER BY id DESC
    LIMIT 50
    """)

    rows=cursor.fetchall()

    for row in rows:

        user_id=row[0]
        name=row[1]
        username=row[2]
        msg_type=row[3]
        content=row[4]

        header=f"""
👤 الاسم : {name}
🔗 اليوزر : @{username}
🆔 الايدي : {user_id}
"""

        if msg_type=="text":

            await update.message.reply_text(
            header + f"\n💬 رسالة المستخدم:\n{content}"
            )

        elif msg_type=="bot":

            await update.message.reply_text(
            header + f"\n🤖 رد البوت:\n{content}"
            )

        elif msg_type=="photo":

            await update.message.reply_photo(
            photo=content,
            caption=header + "\n🖼 صورة مرسلة"
            )

        elif msg_type=="video":

            await update.message.reply_video(
            video=content,
            caption=header + "\n🎥 فيديو مرسل"
            )

        elif msg_type=="voice":

            await update.message.reply_voice(
            voice=content,
            caption=header + "\n🎤 فويس مرسل"
            )

# CHAT

async def chat(update:Update,context:ContextTypes.DEFAULT_TYPE):

    user=update.effective_user
    text=update.message.text

    save_log(user,"text",text)

    messages=[
    {"role":"system","content":SYSTEM_PROMPT},
    {"role":"user","content":text}
    ]

    response=client.chat.completions.create(
    model="gpt-4o-mini",
    messages=messages
    )

    reply=response.choices[0].message.content

    save_log(user,"bot",reply)

    await update.message.reply_text(reply)

# PHOTO

async def photo(update:Update,context:ContextTypes.DEFAULT_TYPE):

    user=update.effective_user

    photo_id=update.message.photo[-1].file_id

    save_log(user,"photo",photo_id)

    file=await context.bot.get_file(photo_id)

    image_url=file.file_path

    prompt="""
المستخدم أرسل صورة.

علق عليها كأنك صديق سعودي طبيعي.
"""

    response=client.responses.create(
    model="gpt-4.1-mini",
    input=[{
    "role":"user",
    "content":[
    {"type":"input_text","text":prompt},
    {"type":"input_image","image_url":image_url}
    ]
    }]
    )

    reply=response.output_text

    save_log(user,"bot",reply)

    await update.message.reply_text(reply)

# VIDEO

async def video(update:Update,context:ContextTypes.DEFAULT_TYPE):

    user=update.effective_user

    video_id=update.message.video.file_id

    save_log(user,"video",video_id)

    await update.message.reply_text("وصلني الفيديو 👍")

# VOICE

async def voice(update:Update,context:ContextTypes.DEFAULT_TYPE):

    user=update.effective_user

    voice_id=update.message.voice.file_id

    save_log(user,"voice",voice_id)

    file=await update.message.voice.get_file()

    await file.download_to_drive("voice.ogg")

    audio=open("voice.ogg","rb")

    transcript=client.audio.transcriptions.create(
    model="gpt-4o-mini-transcribe",
    file=audio
    )

    text=transcript.text

    messages=[
    {"role":"system","content":SYSTEM_PROMPT},
    {"role":"user","content":text}
    ]

    response=client.chat.completions.create(
    model="gpt-4o-mini",
    messages=messages
    )

    reply=response.choices[0].message.content

    save_log(user,"bot",reply)

    await update.message.reply_text(reply)

    os.remove("voice.ogg")

# RUN

app=ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start",start))
app.add_handler(CommandHandler("users",users))
app.add_handler(CommandHandler("conversations",conversations))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,chat))
app.add_handler(MessageHandler(filters.PHOTO,photo))
app.add_handler(MessageHandler(filters.VIDEO,video))
app.add_handler(MessageHandler(filters.VOICE,voice))

print("Bot running...")

app.run_polling()
