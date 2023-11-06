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

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_html(
            rf"Hello there! I am your helpul assitant that holds knowledge regarding California Legals."
            rf" Type 'search <query>' to start!"
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message_text = update.message.text
        if message_text.lower().startswith('search'):
            query = message_text[7:]  # Remove 'search ' from the message
            await self.search_and_reply(update, query)

    async def search_and_reply(self, update: Update, query: str):
        try:
            search_response = self.groundx.search.content(id=self.project_id, search={"query": query})
            llmText = "\n".join(r["text"] for r in search_response.body["search"]["results"] if "text" in r)
            completion = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant. Answer the question using the information provided."
                    },
                    {"role": "user", "content": query},
                ],
            )
            response_message = completion.choices[0].message.content if completion.choices else "No response available."
            await update.message.reply_text(response_message)
        except ApiException as e:
            await update.message.reply_text(f"Error with GroundX API: {e}")
        except openai.error.OpenAIError as e:
            await update.message.reply_text(f"Error with OpenAI API: {e}")
        except Exception as e:
            await update.message.reply_text(f"An unexpected error occurred: {e}")

    def run(self):
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.run_polling()

if __name__ == '__main__':
    # Load configuration from a JSON file
    with open('config.json') as config_file:
        config = json.load(config_file)

    # Initialize the bot with the configuration
    my_bot = TelegramBot(config)
    my_bot.run()
