import os

import openai


class GPT:
    KEY = os.environ.get("OPENAI_API_KEY")

    @staticmethod
    def __connect(message):
        openai.api_key = GPT.KEY
        chat_completion = (
            openai.ChatCompletion.create(model="gpt-3.5-turbo",
                                         messages=[{"role": "user",
                                                    "content": message}]))

        return chat_completion["choices"][0]["message"]["content"]

    @staticmethod
    def generate_post(post_title):
        if not isinstance(post_title, str):
            raise TypeError("post_title must be str")

        return GPT.__connect(f"generate a post body with this title:\n {post_title}")

    @staticmethod
    def summarize_post(post_body):
        if not isinstance(post_body, str):
            raise TypeError("post_title must be str")

        return GPT.__connect(f"summarize this post body\n {post_body}\n")

    @staticmethod
    def fix_grammar(post_body):
        if not isinstance(post_body, str):
            raise TypeError("post_title must be str")

        return GPT.__connect(f"fix grammar/typo of this post body: \n {post_body}\n")
