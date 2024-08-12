# -*- coding: utf-8 -*-
"""
    fabfile
    ~~~~~~~~~~~~~~

    Fab.

    :copyright: (c) 2016 by fengweimin.
    :date: 16/7/21
"""
import json
import re
import os
import random

from invoke import task as local_task

from paramiko import RSAKey
from fabric import task

from www import create_www
from www.commons import json_simplify, json_dumps, json_merge, json_update_by_path
from www.extensions import openai, comfyui

# Multi hosts
# host, e.g, webusr@192.168.0.1:9527
# connect_kwargs, e.g, {'password': 'xxx'} or {'key_filename': 'instance/webusr.key'} or {'pkey': paramiko.RSAKey.from_private_key_file('~/.ssh/webusr')}
hosts = [
    {'host': 'FIXME', 'connect_kwargs': {'password': 'FIXME'}}
]

# Use instance package to overwrite hosts
try:
    from instance.fabenv import *
except ImportError:
    pass

# project deploy folder
project_folder = '/appl/projects/koiseed'


@task(hosts=hosts)
def deploy(ctx):
    """ Check newest version and confirm if needed to deploy. """
    with ctx.cd(project_folder):
        ctx.run('git fetch')
        print('\n----- Newest Version -----\n')
        ctx.run('git log origin/main -1')
        print('\n----- Current Version -----\n')
        ctx.run('git log -1')
        ctx.run('git status')

        if confirm('\n- Are you sure to deploy?'):
            ctx.run('git pull')
            ctx.run('. venv/bin/activate')
            #
            pid_file = 'wsgi.pid'
            if ctx.run(f'test -f {pid_file}', warn=True).failed:
                ctx.run(f'gunicorn wsgi:www --threads 3 -p {pid_file} -b 0.0.0.0:6060 -D --timeout 300 --log-file www/logs/gunicorn.log')
            else:
                ctx.run(f'kill -HUP `cat {pid_file}`')
            #
            ctx.run(f'cat {pid_file}')


def confirm(question, assume_yes=True):
    """ Ask user a yes/no question and return their response as a boolean. """
    # Set up suffix
    if assume_yes:
        suffix = "Y/n"
    else:
        suffix = "y/N"
    # Loop till we get something we like
    while True:
        # Ask
        response = input("{0} [{1}] ".format(question, suffix))
        response = response.lower().strip()  # Normalize
        # Default
        if not response:
            return assume_yes
        # Yes
        if response in ["y", "yes"]:
            return True
        # No
        if response in ["n", "no"]:
            return False
        # Didn't get empty, yes or no, so complain and loop
        err = "I didn't understand you. Please specify '(y)es' or '(n)o'."
        print(err)


@local_task
def seed(ctx):
    """ Invoke pyseed to gen blueprints for registered models. """
    if confirm('Are you sure to use pyseed to gen blueprints for registered models?'):
        ctx.run('pyseed gen')


@local_task(optional=['folder', 'file', 'suffix'])
def ai0(ctx, file=None, folder='www/templates/pub-demo', suffix='.json'):
    """ Invoke AI tools to generate page content for specified page, i.e, index-basic.json -> index-basic.ai.json. """
    if not confirm('Are you sure to gen page content(s)?'):
        return
    # Read content of README.md
    with open('README.md') as f:
        readme = f.read()
        # if '# koiseed' in readme:
        #     print('# koiseed is found in README.md, Please make update readme file to describe your project')
        #     return
    # Print readme content
    print('----- README.md -----')
    print(readme)
    #
    ai_suffix = '.ai' + suffix
    app = create_www(runscripts=True)
    with app.app_context():
        # Generate page content for each json file in specified folder
        for fn in os.listdir(folder):
            #
            if not fn.endswith(suffix) and not fn.endswith(ai_suffix):
                continue
            #
            print(f'----- {fn} -----')
            if file and file != fn:
                print(f'Skip as file name not match: {file}')
                continue
            #
            fg = os.path.join(folder, fn.replace(suffix, ai_suffix))
            # if os.path.exists(fg):
            #    print(f'file exists, skip')
            #    continue
            #
            fp = os.path.join(folder, fn)
            with open(fp, 'r', encoding='utf-8') as f:
                demo_data = f.read()
            # 从json提取文本字段, 从而减少gpt的生成内容
            demo_json = json.loads(demo_data)
            simple_json = json_simplify(demo_json)
            #
            if fn.startswith('index-'):
                gpt_template = f'''下面是用来渲染我的jinja2模版的json数据，用于网页的各个部分：

{simple_json}

我将提供一个新网站的介绍，请生成符合该介绍的json数据，并满足如下要求：

1. 保证生成的内容符合该介绍，且无需参考原始数据的内容
2. 保持json结构不变，并生成合法的json数据
3. 生成的内容应当与我提供的介绍是同一个语言，只有tag字段可以使用对应的英文

如果你明白了，请确认并等待新网站的介绍 ~
'''
            else:
                gpt_template = f'''下面是用来渲染我的jinja2模版的json数据，用于网页的各个部分：
                    
{simple_json}                        

我将提供一个新网站的介绍，你只需根据该介绍的语言进行翻译即可：

1. 保持原始数据的意思不变，无需参考新网站的介绍
2. 保持json结构不变，并生成合法的json数据

如果你明白了，请确认并等待新网站的介绍 ~
'''
            #
            print(gpt_template)
            response = openai.chat_stream(messages=[
                {'role': 'system', 'content': '你是一个网站开发'},
                {'role': 'user', 'content': gpt_template},
                {'role': 'assistant', 'content': '明白了，请提供新网站的介绍'},
                {'role': 'user', 'content': '''锦鲤模型，专注于大模型的实际应用
- 针对具体的应用场景，选择合适的大模型，实现并开源了最小可行产品
- 您可以在线体验这些应用，或下载源代码自行二次开发，或联系我们量身定制
'''
                 }
            ])
            #
            content = ''
            for chunk in response:
                print(chunk, end='')
                content += chunk
            #
            json_pattern = re.compile(r"```json(.*?)```", re.DOTALL)
            json_match = json_pattern.search(content)
            # TODO: retry if no json content found or invalid json content
            if not json_match:
                print('No json content found, try to retry')
                break
            #
            response_data = json_match.group(1).strip()
            try:
                response_json = json.loads(response_data)
            except json.JSONDecodeError as e:
                print('Invalid json content, try to retry')
                break
            # Consolidate back to demo_json and save to file .jsonai
            json_merge(demo_json, response_json)
            with open(fg, 'w', encoding='utf-8') as f:
                f.write(json_dumps(demo_json, pretty=True))


@local_task(optional=['folder', 'file', 'suffix'])
def ai1(ctx, file=None, folder='www/templates/pub-demo', suffix='.json'):
    """ Invoke AI tools to generate medias, i.e, image/icon/video, from generated page content. """
    if not confirm('Are you sure to gen medias for page content(s)?'):
        return
    #
    # Prepare
    #
    ai_suffix = '.ai' + suffix
    # (pre_prompt, app_prompt, negative_prompt, steps, cfg) for different media types
    comfyui_settings = {
        'illustration': (
            'flat simple minimalist cute illustration, blue theme, isolated on white background',
            'trending on artstation, popular on dribbble, illustration by airbnb',
            'lowres, error, cropped, worst quality, low quality, jpeg artifacts, out of frame, watermark, signature\ndeformed, ugly, mutilated, disfigured, text, extra limbs, extra fingers, extra arms, mutation, bad proportions, malformed limbs, mutated hands, fused fingers, long neck',
            6,  # steps
            4,  # cfg
        ),
        'photo': (
            'realistic photo',
            'highly detailed glossy eyes, high detailed skin, skin pores, intricate design, film grain, dslr, HDR, 64k',
            'disfigured, ugly, bad, immature, cartoon, anime, 3d, painting, b&w',
            4,  # steps
            2,  # cfg
        )
    }
    #
    app = create_www(runscripts=True)
    with app.app_context():
        # Generate media for each page content file in specified folder
        for fn in os.listdir(folder):
            # Only works for ai generated json files
            if not fn.endswith(ai_suffix):
                continue
            #
            print(f'----- {fn} -----')
            if file and file != fn:
                print(f'Skip as file name not match: {file}')
                continue
            #
            fp = os.path.join(folder, fn)
            with open(fp, 'r', encoding='utf-8') as f:
                page_data = f.read()
            #
            page_json = json.loads(page_data)
            #
            # ChatGPT4o generation
            #
            print(f'--- Analyze Page Content ---')
            groups_for_generation = {
                'illustration': [],  # [(path, demo/current image, related content), ...]
                'photo': [],
            }

            def _guess_image_type(image_url):
                """ Guess image type from image url. """
                if 'illustration' in image_url:
                    return 'illustration'
                if 'photo' in image_url:
                    return 'photo'
                #
                return None

            def _iterate(d, path_=''):
                """ Iterate json data to find image fields. """
                for k, v in d.items():
                    related_content_ = ''
                    for related_field in ('title', 'subtitle', 'content'):
                        if d.get(related_field):
                            related_content_ += d[related_field] + '\n'
                    #
                    related_content_ = related_content_.rstrip('\n')
                    #
                    if isinstance(v, dict):
                        _iterate(v, f'{path_}.{k}')
                    elif isinstance(v, list):
                        if k == 'images':
                            for ii, vv in enumerate(v):
                                it = _guess_image_type(vv)
                                if not it:
                                    print(f'Error: unknown image type for {vv}')
                                    continue
                                #
                                groups_for_generation[it].append([f'{path_}.{k}[{ii}]', vv, related_content_])
                        else:
                            for ii, vv in enumerate(v):
                                if isinstance(vv, dict):
                                    _iterate(vv, f'{path_}.{k}[{ii}]')
                    elif isinstance(v, str):
                        if k == 'image':
                            it = _guess_image_type(v)
                            if not it:
                                print(f'Error: unknown image type for {v}')
                                continue
                            #
                            groups_for_generation[it].append([f'{path_}.{k}', v, related_content_])

            #
            _iterate(page_json)
            #
            updated = 0
            for image_type, images_for_generation in groups_for_generation.items():
                print(f'--- Prompt Generation for {image_type} ---')
                # Invoke ChatGPT4o to generate prompt
                generated_prompts = []
                for ig in images_for_generation:
                    related_content = ig[2]
                    print(f'Image {ig[0]}: {ig[1]} with related content: {related_content}')
                    if not related_content:
                        print('Skip as no related content found')
                        continue
                    #
                    response = openai.chat_stream(messages=[
                        {'role': 'system', 'content': '你是一个网站设计专家'},
                        {'role': 'user', 'content': f'''我将提供一两句文案，请根据文案设计一个简洁的画面，让网站的用户能够更加直观的理解该文案，并满足如下要求：
    
1. 只需包含具体的人物和环境，返回一句英文的简单的描述即可
2. 人物和环境的描述尽可能简单明了，不超过3人，环境不超过5个物件

下面是已有的描述，请避免生成类似的描述，且不使用已经出现过的人物和物件：

{'；'.join(generated_prompts)}

'''},
                        {'role': 'assistant', 'content': '明白了，请提供文案'},
                        {'role': 'user', 'content': related_content}
                    ])
                    content = ''
                    for chunk in response:
                        print(chunk, end='')
                        content += chunk
                    #
                    generated_prompts.append(content.strip())
                #
                comfyui_setting = comfyui_settings[image_type]
                pre_prompt = comfyui_setting[0]
                app_prompt = comfyui_setting[1]
                negative_prompt = comfyui_setting[2]
                schedule_prompt = ''
                for i, prompt in enumerate(generated_prompts):
                    schedule_prompt += f'"{i}": "{prompt}",\n'
                #
                schedule_prompt = schedule_prompt.rstrip(',\n')
                print(f'positive prompt: {pre_prompt}\n{schedule_prompt}\n{app_prompt}')
                print(f'negative prompt: {negative_prompt}')
                #
                # ComfyUI generation
                #
                print(f'--- ComfyUI Generation for {image_type} ---')
                # Load comfyui prompt template from file
                # 对comfyui的json文件的要求:
                # 1. 没有多余节点, 否则无法正确显示自行进度
                # 2. 可以直接在测试环境部署使用, 方便调试
                # 3. 节点序号不能随意更改, 下面更新内容的时候需要根据节点序号来更新
                # 4. 由于comfyui有些字段的内容诸如模型的名字等依赖于本地的文件名, 因此应当尽可能保证线上和各个测试环境的统一
                with open(os.path.join(app.root_path, 'ai/comfyui-api-sdxl-batch-with-aligned-style.json'), 'r', encoding='utf-8') as f:
                    comfyui_prompt = json.load(f)
                #
                comfyui_prompt['3']['inputs']['seed'] = random.randint(1000000000, 9999999999)
                comfyui_prompt['3']['inputs']['steps'] = comfyui_setting[3]
                comfyui_prompt['3']['inputs']['cfg'] = comfyui_setting[4]
                comfyui_prompt['5']['inputs']['batch_size'] = len(generated_prompts)
                comfyui_prompt['7']['inputs']['text'] = negative_prompt
                comfyui_prompt['9']['inputs']['filename_prefix'] = image_type
                comfyui_prompt['12']['inputs']['text'] = schedule_prompt
                comfyui_prompt['12']['inputs']['max_frames'] = len(generated_prompts)
                comfyui_prompt['12']['inputs']['pre_text'] = pre_prompt
                comfyui_prompt['12']['inputs']['app_text'] = app_prompt
                #
                generated_images = comfyui.generate_images(comfyui_prompt)
                if not generated_images:
                    print(f'Skip as no images generated')
                    continue
                #
                if len(generated_images) != len(images_for_generation):
                    print(f'Error: images count not match')
                    continue
                #
                print(f'--- Update Content ---')
                for i, ig in enumerate(images_for_generation):
                    path = ig[0][1:]
                    generated_image = generated_images[i]
                    print(f'Update page content {path} -> {generated_image}')
                    json_update_by_path(page_json, path, generated_image)  # Note: path starts with '.'
                    updated += 1
            #
            print(f'Totally {updated} images updated')
            if updated > 0:
                with open(fp, 'w', encoding='utf-8') as f:
                    f.write(json_dumps(page_json, pretty=True))
