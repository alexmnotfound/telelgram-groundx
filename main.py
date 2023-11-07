import logging
import json
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from groundx import Groundx, ApiException
import openai

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


class TelegramBot:
    def __init__(self, config):
        self.token = config["telegram_bot_token"]
        self.groundx = Groundx(api_key=config["groundx_api_key"])
        self.openai_api_key = config["openai_api_key"]
        self.project_id = config["project_id"]
        openai.api_key = self.openai_api_key
        self.application = Application.builder().token(self.token).build()
        logger.info("TelegramBot initialized with provided configuration.")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.info(f"User {update.effective_user.id} started the conversation.")
        try:
            # Make sure that HTML tags are properly used or entities are escaped
            welcome_message = (
                "Hello there! I am your helpful assistant that holds knowledge regarding California Legals. "
                "Type anything you want to search and I'll look that up for you!"
            )
            await update.message.reply_html(welcome_message)
        except Exception as e:
            logger.exception("Failed to send start message to user.")
            # Consider having a fallback to plain text if HTML messages fail
            await update.message.reply_text("Hello! Type something you want to search between available information "
                                            "to start")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message_text = update.message.text
        logger.info(f"Received message from user {update.effective_user.id}: {message_text}")
        # Process any text that is not a command
        if not message_text.startswith('/'):
            await self.search_and_reply(update, message_text)

    async def search_and_reply(self, update: Update, query: str):
        logger.info(f"Searching GroundX for query: {query}")
        await update.message.reply_text("Searching for the information, please wait...")

        try:
            search_response = self.groundx.search.content(id=self.project_id, search={"query": query})

            # Check if the search response has results
            if search_response.body["search"]["count"] == 0:
                await update.message.reply_text(
                    "I couldn't find any information on that topic. Is there anything else I can help you with?")
                return

            maxInstructCharacters = 2000
            instruction = (
                "You are a helpful virtual assistant that answers questions using the content below. Your task is "
                "to create detailed answers to the questions by combining your understanding of the world with the "
                "content provided below. Do not share links.")

            results = search_response.body["search"]
            logger.info("---- INIT OF RAW RESPONSE ----")
            logger.info(search_response)
            logger.info("---- END OF RAW RESPONSE ----")

            llmText = ""
            for r in results["results"]:
                if "text" in r and len(r["text"]) > 0:
                    if len(llmText) + len(r["text"]) > maxInstructCharacters:
                        break
                    elif len(llmText) > 0:
                        llmText += "\n"
                    llmText += r["text"]
            logger.info("Content fetched successfully from GroundX.")

            content = """%s
                    ===
                    %s
                    ===
                    """ % (instruction, llmText)

            logger.info("----------------------")
            logger.info(content)
            logger.info("----------------------")

            logger.info("Sending content to OpenAI for completion.")
            completion = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": content,
                    },
                    {"role": "user", "content": query},
                ],
            )

            response_message = completion.choices[0].message.content if completion.choices else "No response available."
            await update.message.reply_text(response_message)
            logger.info("Response sent to user.")

            # Send another message asking if the user needs more help
            follow_up_message = "How else can I help you?."
            await update.message.reply_text(follow_up_message)

        except ApiException as e:
            logger.error(f"Error with GroundX API: {e}")
            await update.message.reply_text(f"Error with GroundX API: {e}")
        except openai.error.OpenAIError as e:
            logger.error(f"Error with OpenAI API: {e}")
            await update.message.reply_text(f"Error with OpenAI API: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            await update.message.reply_text(f"An unexpected error occurred: {e}")

    def run(self):
        self.application.add_handler(CommandHandler("start", self.start))
        # self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(MessageHandler(filters.TEXT, self.handle_message))
        logger.info("Starting Telegram bot polling.")
        self.application.run_polling()


if __name__ == '__main__':
    # Load configuration from a JSON file
    with open('./credentials.json') as config_file:
        config = json.load(config_file)

    # Initialize the bot with the configuration
    my_bot = TelegramBot(config)
    my_bot.run()
