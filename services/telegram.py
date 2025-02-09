import json
import os

import requests


class TelegramService:
    def __init__(self, tgoff):
        self.apiCredentials = dict()
        self.telegramApiFile = "telegram_api_credentials"
        self.tgoff = tgoff

    def load_api_credentials(self):
        """A function to load the telegram api credentials from the json file"""
        if not os.path.isfile(self.telegramApiFile):
            return

        with open(self.telegramApiFile) as file:
            self.apiCredentials = json.load(file)

    def save_api_credentials(self, apiCredentials):
        """A function to save the telegram api credentials into the telegramApiFile"""
        with open(self.telegramApiFile, 'w') as file:
            file.write(json.dumps(apiCredentials))

    def is_telegram_active(self):
        """A function to check if telegram is active, i.e. if the api credentials are present

        Returns
        -------
        bool
            True if telegram is active, False otherwise
        """
        return not self.tgoff and "chatid" in self.apiCredentials and "token" in self.apiCredentials

    def send_telegram_messages(self, messages):
        """A function to send messages to telegram

        Arguments
        ---------
        messages: list
            the list of messages to send

        Example usage
        -------------
        >>> self.send_telegram_messages(["message1", "message2"])
        """
        for msg in messages:
            try:
                request_url = "https://api.telegram.org/bot" + self.apiCredentials["token"] + "/sendMessage?chat_id=" + \
                              self.apiCredentials["chatid"] + "&text=" + msg
                requests.get(request_url)
            except Exception as e:
                print(f"Error sending message to telegram: {e}")
                continue
