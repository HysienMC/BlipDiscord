from chatterbot import ChatBot
from chatterbot.trainers import ChatterBotCorpusTrainer

# Create and train the chatbot
chatbot = ChatBot(
    'DiscordBot',
    storage_adapter='chatterbot.storage.SQLStorageAdapter',
    logic_adapters=[
        'chatterbot.logic.BestMatch',
        'chatterbot.logic.MathematicalEvaluation',  # Allows simple math calculations
    ],
    database_uri='sqlite:///database.db'  # Save conversations in a database for learning
)

trainer = ChatterBotCorpusTrainer(chatbot)
trainer.train('chatterbot.corpus.english')  # Train on the English corpus

# Function to get AI response
def get_ai_response(user_message):
    return chatbot.get_response(user_message)
