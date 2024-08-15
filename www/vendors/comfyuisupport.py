# -*- coding: utf-8 -*-
"""
    comfysupport
    ~~~~~~~~~~~~~~

    ComfyUI Api support.
    https://github.com/comfyanonymous/ComfyUI

    :copyright: (c) 2021 by weiminfeng.
    :date: 2024/8/8
"""

import json
import requests
import uuid
import io
import os
from urllib.parse import urlencode
from PIL import Image

from contextlib import closing
from websocket import create_connection


class ComfyUISupport(object):
    """ ComfyUI Api support. """

    def __init__(self, app=None):
        self.app = app
        self.server = None
        self.folder = None
        self.client_id = None
        #
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """ Init from app. """
        self.app = app
        self.server = app.config.get('COMFYUI_SERVER')
        self.folder = app.config.get('COMFYUI_FOLDER')
        # Connect if server is set
        if self.server:
            self.client_id = str(uuid.uuid4())

    def queue_prompt(self, prompt):
        """ Send a prompt to the server.

        Server code, https://github.com/comfyanonymous/ComfyUI/blob/master/server.py#L482
        """
        p = {'prompt': prompt, 'client_id': self.client_id}
        data = json.dumps(p).encode('utf-8')
        resp = requests.post(f'http://{self.server}/prompt', data=data)
        return resp.json()

    def get_image(self, filename, subfolder, folder_type):
        """ Get image.

        Server code, https://github.com/comfyanonymous/ComfyUI/blob/master/server.py#L281
        """
        data = {'filename': filename, 'subfolder': subfolder, 'type': folder_type}
        url_values = urlencode(data)
        resp = requests.get(f'http://{self.server}/view?{url_values}')
        return resp.content

    def get_history(self, prompt_id):
        """ Get history of a specified prompt id.

        Server code, https://github.com/comfyanonymous/ComfyUI/blob/master/server.py#L469
        """
        resp = requests.get(f'http://{self.server}/history/{prompt_id}')
        return resp.json()

    def generate_images(self, prompt):
        """ Render images using prompt and wait for response.

        Socket-client sample:
        - https://websocket-client.readthedocs.io/en/latest/examples.html#using-websocket-client-with-with-statements
        ComfyUI code samples:
        - https://github.com/comfyanonymous/ComfyUI/blob/master/script_examples/websockets_api_example_ws_images.py
        - https://9elements.com/blog/hosting-a-comfyui-workflow-via-api/
        """
        # Queue prompt
        prompt_id = self.queue_prompt(prompt)['prompt_id']
        self.app.logger.info(f'Queue prompt with id {prompt_id}')
        # TODO: Auto retry on websocket._exceptions.WebSocketTimeoutException:
        # Open websocket
        with closing(create_connection(f'ws://{self.server}/ws?clientId={self.client_id}', timeout=30)) as conn:
            # Tracking progress
            node_ids = list(prompt.keys())
            finished_nodes = []
            # TODO: Support timeout
            while True:
                out = conn.recv()
                if isinstance(out, str):
                    message = json.loads(out)
                    if message['type'] == 'progress':
                        data = message['data']
                        current_step = data['value']
                        self.app.logger.info(f'Sampler: {current_step}/{data["max"]} steps done')
                    if message['type'] == 'execution_cached':
                        data = message['data']
                        for itm in data['nodes']:
                            if itm not in finished_nodes:
                                finished_nodes.append(itm)
                                self.app.logger.info(f'Progess: {len(finished_nodes)}/{len(node_ids)} tasks done')
                    if message['type'] == 'executing':
                        data = message['data']
                        if data['node'] not in finished_nodes:
                            finished_nodes.append(data['node'])
                            self.app.logger.info(f'Progess: {len(finished_nodes)}/{len(node_ids)} tasks done')
                        # Execution is done
                        if data['node'] is None and data['prompt_id'] == prompt_id:
                            break
                else:
                    continue
        # Get images
        output_images = []
        history = self.get_history(prompt_id)[prompt_id]
        # NOTE: In your comfyui prompt, there should be only one save/preview image node, or all images will be savee
        for node_id in history['outputs']:
            node_output = history['outputs'][node_id]
            if 'images' in node_output:
                for image in node_output['images']:
                    if image['type'] == 'output':
                        fn, ft = image['filename'], image['type']
                        image_data = self.get_image(fn, image['subfolder'], ft)
                        output_data = {'image_data': image_data, 'file_name': fn, 'type': ft}
                        output_images.append(output_data)
        #
        if not output_images:
            self.app.logger.info('No images found')
            return None
        # Save image to static folder
        self.app.logger.info(f'Genereated {len(output_images)} images')
        ret = []
        for i, itm in enumerate(output_images):
            fn = itm['file_name']
            try:
                #
                key = f'static/{self.folder}/{prompt_id}/{fn}'
                path = os.path.join(self.app.root_path, key)
                parent = os.path.dirname(path)
                if not os.path.exists(parent):
                    os.makedirs(parent)
                #
                image = Image.open(io.BytesIO(itm['image_data']))
                image.save(path)
                self.app.logger.info(f'Saved {path}')
                #
                ret.append('/' + key)
            except Exception as e:
                self.app.logger.info(f'Failed to save image {fn}: {e}')
                return None
        #
        return ret
