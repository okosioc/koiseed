# -*- coding: utf-8 -*-
"""
    openai
    ~~~~~~~~~~~~~~

    OpenAI functions for SDK 1.x+.

    :copyright: (c) 2021 by weiminfeng.
    :date: 2024/5/16
"""
import time
import traceback

from openai import OpenAI, AzureOpenAI, OpenAIError


class OpenAISupport(object):
    """ This class is a wrapper of OpenAI client. """

    def __init__(self, app=None):
        self.app = app
        self.client = None
        self.api_key = None
        self.default_model = None
        self.endpoint = None
        self.api_version = None
        #
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """ Init from app. """
        self.app = app
        self.api_key = app.config['OPENAI_API_KEY']
        self.default_model = app.config['OPENAI_DEFAULT_MODEL']
        self.endpoint = app.config.get('OPENAI_ENDPOINT', '')
        self.api_version = app.config.get('OPENAI_API_VERSION')
        #
        if self.api_key:
            if 'azure' in self.endpoint:
                self.client = AzureOpenAI(
                    # Api versions defined in https://learn.microsoft.com/en-us/azure/ai-services/openai/reference#completions
                    # e.g, 2024-02-15-preview
                    api_version=self.api_version,
                    # Endpoint and key are defined in an Azure resource of OpenAI
                    # e.g, https://openai-instance-eastus2-01.openai.azure.com/
                    azure_endpoint=self.endpoint,
                    api_key=self.api_key,
                )
            else:
                self.client = OpenAI(
                    api_key=self.api_key,
                    # If you have a reverse proxy pointing to openAI, you can set the base_url but not using default value https://api.openai.com/v1
                    # e.g, https://openai.fengweimin.com/v1
                    base_url=self.endpoint or None,
                )

    def chat(self, messages, model=None):
        """ Return chatGPT response.

        :param messages: List of message, e.g. [{'role': 'system', 'content': 'You are a helpful assistant'}, {'role': 'user", 'content': 'Hello'}]
        :param model: Model name, e.g, gpt-3.5-turbo, gpt-4-turbo, gpt-4o, etc.

        NOTE:
        - If you are using Azure OpenAI, you should Use deployment name instead of model name under an Azure resource, which has configured the OpenAI model(e.g, gpt-4) and its version(e.g, turbo-2024-04-09)
          e.g, open-gpt4-turbo-01
        """
        # Chat completion demo, https://platform.openai.com/docs/guides/text-generation/chat-completions-api
        # Chat completion api, https://platform.openai.com/docs/api-reference/chat/create
        completion = self.client.chat.completions.create(
            model=model or self.default_model,
            messages=messages,
        )
        # print(completion.model_dump_json(indent=2))
        return completion.choices[0].message.content

    def chat_stream(self, messages, model=None):
        """ Yield chatGPT response by streaming.

        :param messages: List of message, e.g. [{'role': 'system', 'content': 'You are a helpful assistant'}, {'role': 'user", 'content': 'Hello'}]
        :param model: Model name, e.g, gpt-3.5-turbo, gpt-4-turbo, gpt-4o, etc.

        NOTE:
        - If you are using Azure OpenAI, you should Use deployment name instead of model name under an Azure resource, which has configured the OpenAI model(e.g, gpt-4) and its version(e.g, turbo-2024-04-09)
          e.g, open-gpt4-turbo-01
        """
        start_time = time.time()
        # Streaming, https://platform.openai.com/docs/api-reference/streaming
        # Chat completion demo, https://platform.openai.com/docs/guides/text-generation/chat-completions-api
        # Chat completion api, https://platform.openai.com/docs/api-reference/chat/create
        stream = self.client.chat.completions.create(
            model=model or self.default_model,
            messages=messages,
            stream=True,
        )
        #
        tokens = 0
        buffer = ''
        for chunk in stream:
            # Azure OpenAI will return blank choices at the beginning, just skip
            if not chunk.choices:
                continue
            # Note that the delta field is used here
            content = chunk.choices[0].delta.content
            tokens += 1
            if content is not None:
                buffer += content
                if content.endswith('\n'):
                    yield buffer
                    buffer = ''
                    # print(buffer)
        #
        if buffer:
            yield buffer
            # print(buffer)
        #
        yield '\n'
        elapsed_time = time.time() - start_time
        self.app.logger.info(f'Total tokens: {tokens}, Elapsed: {elapsed_time:.2f} seconds')

    def chat_sse(self, messages, model=None):
        """ Yield chatGPT response by server-sent events.

        Use server-sent events, FE needs to use EventSource to build a long connection to receive openAI's stream response.
        - EventSource only supports GET, https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events
        - Need to use sse.js to support POST，https://github.com/mpetazzoni/sse.js

        :param messages: List of message, e.g. [{'role': 'system', 'content': 'You are a helpful assistant'}, {'role': 'user", 'content': 'Hello'}]
        :param model: Model name, e.g, gpt-3.5-turbo, gpt-4-turbo, gpt-4o, etc.

        NOTE:
        - If you are using Azure OpenAI, you should Use deployment name instead of model name under an Azure resource, which has configured the OpenAI model(e.g, gpt-4) and its version(e.g, turbo-2024-04-09)
          e.g, open-gpt4-turbo-01
        """
        try:
            # Streaming, https://platform.openai.com/docs/api-reference/streaming
            # Chat completion demo, https://platform.openai.com/docs/guides/text-generation/chat-completions-api
            # Chat completion api, https://platform.openai.com/docs/api-reference/chat/create
            stream = self.client.chat.completions.create(
                model=model or self.default_model,
                messages=messages,
                stream=True,
            )
            yield 'data: start\n\n'
            # print('---------- start')
            for chunk in stream:
                # Azure OpenAI will return blank choices at the beginning, just skip
                if not chunk.choices:
                    continue
                #
                choice = chunk.choices[0]
                content = choice.delta.content
                if content:
                    # Seems sse.js will remove blank strings, so we need to replace to <br> here
                    content = content.replace('\n', '<br>')
                    yield f'data: {content}\n\n'
                    # print(content)
                #
                if choice.get('finish_reason') == 'stop':
                    yield 'data: stop\n\n'
                    # print('---------- stop')
        except OpenAIError:
            traceback.print_exc()
            yield 'event: error\ndata: chatgpt error\n\n'
