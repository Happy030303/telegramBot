import os
import asyncio
import instaloader
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
import re

BOT_TOKEN  = "8735897869:AAHQilmIbYG6TYbCdchapc1lnkkQzGJ7Tqk"
CHANNEL_ID = -1003325805849

def download_instagram_video(url):
    match = re.search(r"/(reel|p)/([A-Za-z0-9_-]+)", url)
    if not match:
        raise ValueError(f"Invalid Instagram URL: {url}")

    shortcode = match.group(2)
    download_dir = f"downloads/{shortcode}"
    os.makedirs(download_dir, exist_ok=True)

    L = instaloader.Instaloader(
        dirname_pattern=download_dir,
        filename_pattern="{shortcode}",
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        post_metadata_txt_pattern=""
    )

    post = instaloader.Post.from_shortcode(L.context, shortcode)
    L.download_post(post, target=download_dir)

    for file in os.listdir(download_dir):
        if file.endswith(".mp4"):
            return os.path.join(download_dir, file)

    raise FileNotFoundError(f"Video not found for: {url}")


def cleanup(shortcode):
    download_dir = f"downloads/{shortcode}"
    if os.path.exists(download_dir):
        for file in os.listdir(download_dir):
            os.remove(os.path.join(download_dir, file))
        os.rmdir(download_dir)


async def download_and_send(context, url):
    match = re.search(r"/(reel|p)/([A-Za-z0-9_-]+)", url)
    shortcode = match.group(2) if match else None

    try:
        video_path = download_instagram_video(url)
        with open(video_path, "rb") as video_file:
            await context.bot.send_video(
                chat_id=CHANNEL_ID,
                video=video_file,
                caption="📸 Downloaded from Instagram"
            )
        print(f"✅ Done: {url}")
        return True, shortcode

    except Exception as e:
        print(f"❌ Failed: {url} → {e}")
        return False, shortcode


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.channel_post

    if not message or message.chat.id != CHANNEL_ID:
        return

    text = message.text or ""

    # Extract all instagram links — works with newline OR comma separated
    links = re.findall(r"https?://(?:www\.)?instagram\.com/(?:reel|p)/[A-Za-z0-9_-]+/?[^\s,]*", text)

    if not links:
        return

    total = len(links)
    print(f"📥 {total} Instagram link(s) received")

    status = await context.bot.send_message(
        CHANNEL_ID,
        f"⏳ Downloading {total} video(s)..."
    )

    # Download all videos simultaneously
    tasks = [download_and_send(context, url) for url in links]
    results = await asyncio.gather(*tasks)

    success = sum(1 for r, _ in results if r)
    failed = total - success

    # Cleanup all folders
    for _, shortcode in results:
        if shortcode:
            cleanup(shortcode)

    # Delete original link message
    await context.bot.delete_message(
        chat_id=CHANNEL_ID,
        message_id=message.message_id
    )

    # Show final status then delete after 3 seconds
    if failed == 0:
        await context.bot.edit_message_text(
            chat_id=CHANNEL_ID,
            message_id=status.message_id,
            text=f"✅ All {total} video(s) sent successfully!"
        )
    else:
        await context.bot.edit_message_text(
            chat_id=CHANNEL_ID,
            message_id=status.message_id,
            text=f"⚠️ {success}/{total} downloaded. {failed} failed."
        )

    await asyncio.sleep(3)
    await context.bot.delete_message(
        chat_id=CHANNEL_ID,
        message_id=status.message_id
    )


app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.CHANNEL, handle_message))
print("🤖 Bot is running...")
app.run_polling(allowed_updates=["channel_post"])