import os

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from log_config import setup_logging
from repository import PollRepository, Day
import logging

setup_logging()

logger = logging.getLogger(__name__)

# Load environment variables from the .env file
load_dotenv()

# Get the API key from the .env file
API_KEY = os.getenv("API_KEY")
assert API_KEY is not None

poll_repo = PollRepository()

all_hours = [
    "11:00",
    "12:00",
    "13:00",
    "14:00",
    "15:00",
    "16:00",
    "17:00",
    "18:00",
    "19:00",
    "20:00",
    "21:00",
    "22:00",
    "23:00",
]


def get_day_name(day: Day):
    if day == Day.saturday:
        return "<b>СУББОТА</b>"
    else:
        return "<b>ВОСКРЕСЕНЬЕ</b>"


def get_poll_text(day: Day, group_name: str):
    day_name = get_day_name(day)
    return f"{day_name}\nПривет, выбери свободное время для {group_name} по МСК:"


def get_base_buttons(group_id: int) -> dict[str, str]:
    buttons: list[tuple[str, str]] = [
        *[(str(group_id) + "$" + hour, hour + " МСК") for hour in all_hours],
        (str(group_id) + "$submit", "готово"),
    ]
    return {key: val for key, val in buttons}


# Define the poll command
async def start_poll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("/poll")

    # Get the username of the user who triggered the command
    assert update.message is not None
    assert update.message.from_user is not None
    assert update.effective_chat is not None
    assert update.effective_chat.title is not None

    if 'kraken' in update.message.text:
        prefix = '🦀'
    else:
        prefix = ''

    user_username = update.message.from_user.username

    # Set the group chat ID to send results later
    group_chat_id = update.effective_chat.id
    group_name = update.effective_chat.title

    # Get all group members (admins for now, you can expand to all members if needed)
    group_members = await context.bot.get_chat_administrators(chat_id=group_chat_id)

    if poll_repo.poll_exists(group_chat_id):
        await update.message.reply_text(f"{prefix} Sorry @{user_username}, опрос уже начался.")
        return

    poll = poll_repo.new_poll(group_chat_id, update.message.from_user.id, group_name)

    # Create an inline keyboard (buttons)
    keyboard = [
        [InlineKeyboardButton(text, callback_data=key)]
        for key, text in get_base_buttons(group_chat_id).items()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    group_user_ids = set()
    # Send buttons to each member in the group
    for member in group_members:
        user_id = member.user.id

        group_user_ids.add(user_id)

        # Send the poll privately to each user
        await context.bot.send_message(
            chat_id=user_id,
            text=get_poll_text(Day.saturday, poll.group_name),
            reply_markup=reply_markup,
        )

    poll.set_pending_users(group_user_ids)

    # Notify the group that the poll has been sent
    await update.message.reply_text(f"{prefix} Спрашиваю пацанов и девчонок...")


async def clear_poll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("/clearpoll")

    assert update.message is not None
    assert update.message.from_user is not None
    assert update.effective_chat is not None

    # Set the group chat ID to send results later
    group_chat_id = update.effective_chat.id

    poll_repo.clear_current_poll(group_chat_id)

    # Notify the group that the poll has been sent
    await update.message.reply_text("Очистил")


# Handle button press (callback query)
async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    assert query is not None
    assert query.data is not None

    user_id = query.from_user.id

    group_id_str, response = query.data.split("$")
    group_id = int(group_id_str)

    poll = poll_repo.get_poll(group_id)

    day = poll.get_wip_day(user_id)

    if response == "submit":
        poll.set_poll_ready(user_id, day)

        if poll.all_users_ready():
            await send_poll_results(context, group_id)

        if day == Day.saturday:
            day = Day.sunday
            base_buttons = get_base_buttons(group_id)
            new_keyboard = []
            for key, text in base_buttons.items():
                new_keyboard.append([InlineKeyboardButton(text, callback_data=key)])
            await query.edit_message_text(
                text=get_poll_text(day, poll.group_name),  # New message text
                reply_markup=InlineKeyboardMarkup(new_keyboard),  # Updated keyboard
            )
        else:
            await query.edit_message_text(text="Спасибо")

        return

    user_vote: set[str] = poll.get_vote(user_id, day)

    if response.startswith("-"):
        user_vote.remove(response[1:])
    else:
        user_vote.add(response)

    poll.update_vote(user_id, user_vote, day)

    await query.answer()

    base_buttons = get_base_buttons(group_id)
    new_keyboard = []
    for key, text in base_buttons.items():
        group_id, hour = key.split("$")
        if hour in user_vote:
            text = "✔ " + text
            key = group_id + "$-" + hour

        new_keyboard.append([InlineKeyboardButton(text, callback_data=key)])
    await query.edit_message_text(
        text=get_poll_text(day, poll.group_name),  # New message text
        reply_markup=InlineKeyboardMarkup(new_keyboard),  # Updated keyboard

        parse_mode="html",
    )

async def send_poll_results(context: ContextTypes.DEFAULT_TYPE, group_id: int):
    poll = poll_repo.get_poll(group_id)
    result_text = "Результаты\n"

    all_votes = poll.get_all_votes()

    for day in [Day.saturday, Day.sunday]:
        day_name = get_day_name(day)
        common_hours = set(all_hours)

        detailed_report = ""
        for user_id, response in all_votes[day]:
            user_info = await context.bot.get_chat(user_id)
            username = user_info.username or user_info.first_name
            detailed_report += f"{username}: {", ".join(sorted(response))}\n"
            if response:
                common_hours &= response

        if common_hours:
            formatted_hours = ", ".join(sorted(common_hours))
        else:
            formatted_hours = "🕒😢💔"
        result_text += f"{day_name}\nОбщие часы: {formatted_hours}\n<tg-spoiler>{detailed_report}</tg-spoiler>"

    await context.bot.send_message(chat_id=poll.group_chat_id, text=result_text, parse_mode="html")


# Add this new handler for the remind command
async def remind_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("/remind")

    # Ensure the message and user triggering the command are not None
    assert update.message is not None
    assert update.message.from_user is not None
    assert update.effective_chat is not None

    # Get the username of the user who triggered the command
    user_username = update.message.from_user.username

    # Set the group chat ID
    group_chat_id = update.effective_chat.id

    # Check if a poll exists
    if not poll_repo.poll_exists(group_chat_id):
        await update.message.reply_text(f"Sorry @{user_username}, no active poll.")
        return

    poll = poll_repo.get_poll(group_chat_id)

    # Get pending users who haven't voted yet
    pending_users = poll.get_pending_users()

    if not pending_users:
        await update.message.reply_text("Все уже проголосовали!")
        return

    # Fetch usernames of the pending users
    pending_usernames = []
    for user_id in pending_users:
        user_info = await context.bot.get_chat(user_id)
        username = user_info.username or user_info.first_name
        pending_usernames.append(f"@{username}")

    # Send a message with the list of users who haven't voted yet
    pending_usernames_text = ", ".join(pending_usernames)
    await update.message.reply_text(f"Еще не ответили: {pending_usernames_text}")

async def repeat_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("/repeat_results")

    # Ensure the message and user triggering the command are not None
    assert update.message is not None
    assert update.message.from_user is not None
    assert update.effective_chat is not None

    # Get the username of the user who triggered the command
    user_username = update.message.from_user.username

    # Set the group chat ID
    group_chat_id = update.effective_chat.id

    # Check if a poll exists
    if not poll_repo.poll_exists(group_chat_id):
        await update.message.reply_text(f"Sorry @{user_username}, no active poll.")
        return
    
    await send_poll_results(context, group_chat_id)


if __name__ == "__main__":
    logger.info("Start application")
    # Initialize the bot with the API key
    application = ApplicationBuilder().token(API_KEY).build()

    application.add_handler(CommandHandler("poll", start_poll))
    application.add_handler(CommandHandler("release_kraken", start_poll))
    application.add_handler(CommandHandler("clearpoll", clear_poll))
    application.add_handler(CommandHandler("remind", remind_users))
    application.add_handler(CommandHandler("repeat_results", repeat_results))

    # Handle callback data for buttons
    application.add_handler(CallbackQueryHandler(handle_button))

    # Start the bot
    application.run_polling()
