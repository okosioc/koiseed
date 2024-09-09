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
from PIL import Image, ImageDraw, ImageFont

from paramiko import RSAKey
from fabric import task

from www import create_www
from www.commons import json_simplify, json_dumps, json_merge, json_update_by_path, resize_image
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


theme_settings = {
    'landkit': {
        'templates_folder': 'www/templates/pub-demo',  # 页面模版文件夹, 用来解析演示用的json数据并生成业务相关的json数据
        'icons_folder': 'www/static/landkit/assets/img/icons/duotone-icons',  # 独立图标的文件夹, 根据文案选择相关的图标
    }
}


@local_task(optional=['color'])
def ailogo(ctx, height=100, padding=10, color='#2c7be5'):
    """ Create text logo according to the SHORT_NAME in config.py. """
    app = create_www(runscripts=True)
    with app.app_context():
        #
        text = app.config['SHORT_NAME'] + '.'
        logo_path = os.path.join(app.root_path, 'static/img/logo.png')
        canvas_height = height
        text_height = canvas_height - padding * 2
        # Check if text contains chinese characters
        if re.search(r'[\u4e00-\u9fa5]', text):
            font_path = os.path.join(app.root_path, 'static/fonts/ShangShouJingDongTi-2.ttf')
            font = ImageFont.truetype(font_path, text_height)
        else:
            font_path = os.path.join(app.root_path, 'static/fonts/HelveticaNeue.ttc')
            font = ImageFont.truetype(font_path, text_height, index=4)  # HelveticaNeue Condensed Bold
        #
        bbox = font.getbbox(text)
        text_width = bbox[2] - bbox[0]
        canvas_width = text_width + 2 * padding
        # Use getmetrics() to calculate the real text height
        # - ascent: baseline to the top of the text
        # - descent: baseline to the bottom of the text
        ascent, descent = font.getmetrics()
        text_height = ascent + descent
        app.logger.info(f'Create logo for {text} with text size ({text_width}, {text_height}) in ({canvas_width}, {canvas_height}) at {logo_path} ')
        #
        image = Image.new('RGBA', (canvas_width, canvas_height), (255, 255, 255, 0))  # Transparent background
        draw = ImageDraw.Draw(image)
        #
        text_x = (canvas_width - text_width) // 2
        text_y = (canvas_height - text_height) // 2
        draw.text((text_x, text_y), text, font=font, fill=color)
        image.save(logo_path)


def _aijson(app, fn, simple_json):
    """ Get valid json from GPT with retry mechanism. """
    attempts = 3
    for attempt in range(1, attempts + 1):
        #
        if fn.startswith('index-') or fn.startswith('portfolio-'):
            gpt_template = f'''下面是用来渲染我的jinja2模版的json数据，用于网页的各个部分, 如hero用于页头、intro用于介绍业务内容、test是客户点评、portfolio是作品集、action是行动号召等等：
    
{simple_json}

我将提供一个新网站的介绍，请生成符合该介绍的json数据，并满足如下要求：

1. 保证生成的内容符合该介绍，且无需参考原始数据的内容
2. 保持json结构不变，例如，对象字段应包含一样的键，数组字段应该有同样的长度
3. 生成的内容应当与我提供的介绍是同一个语言，只有tag字段可以使用对应的英文
4. 生成的内容如果有客户信息或者作品集信息，可以使用虚构的数据

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
        app.logger.info(gpt_template)
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
        print('gpt> ', end='')
        for chunk in response:
            print(chunk, end='')
            content += chunk
        #
        json_pattern = re.compile(r"```json(.*?)```", re.DOTALL)
        json_match = json_pattern.search(content)
        if not json_match:
            app.logger.warning(f'Attempt {attempt} failed because of no json content returned')
            continue
        #
        response_data = json_match.group(1).strip()
        try:
            response_json = json.loads(response_data)
            return response_json
        except json.JSONDecodeError as e:
            app.logger.warning(f'Attempt {attempt} failed because of invalid json content returned')
            continue
    # If all attempts failed, return None
    return None


@local_task(optional=['theme', 'file', 'suffix'])
def aitext(ctx, file=None, theme='landkit', suffix='.json'):
    """ Invoke AI tools to generate page content for specified page, i.e, index-basic.json -> index-basic.ai.json. """
    if not confirm('Are you sure to gen text for page content(s)?'):
        return
    # Read content of README.md
    with open('README.md') as f:
        readme = f.read()
        # if '# koiseed' in readme:
        #     print('# koiseed is found in README.md, Please make update readme file to describe your project')
        #     return
    #
    updated = []
    ai_suffix = '.ai' + suffix
    theme_setting = theme_settings[theme]
    templates_folder = theme_setting['templates_folder']
    #
    app = create_www(runscripts=True)
    with app.app_context():
        # Print readme content
        app.logger.info('----- README.md -----')
        app.logger.info(readme)
        # Generate page content for each json file in specified folder
        for fn in os.listdir(templates_folder):
            # Only works for json files, and skip ai generated json files, i.e, .ai.json
            if not fn.endswith(suffix) or fn.endswith(ai_suffix):
                continue
            #
            app.logger.info(f'----- {fn} -----')
            if file and file != fn:
                app.logger.info(f'Skip as file name not match: {file}')
                continue
            #
            fg = os.path.join(templates_folder, fn.replace(suffix, ai_suffix))
            # if os.path.exists(fg):
            #    print(f'file exists, skip')
            #    continue
            #
            fp = os.path.join(templates_folder, fn)
            with open(fp, 'r', encoding='utf-8') as f:
                demo_data = f.read()
            # 从json提取文本字段, 从而减少gpt的生成内容
            demo_json = json.loads(demo_data)
            simple_json = json_simplify(demo_json)
            response_json = _aijson(app, fn, simple_json)
            if not response_json:
                app.logger.warning(f'Skip as failed to generate content for {fn}')
                continue
            # Consolidate back to demo_json and save to file .ai.json
            json_merge(demo_json, response_json)
            with open(fg, 'w', encoding='utf-8') as f:
                f.write(json_dumps(demo_json, pretty=True))
            #
            updated.append(fn)
    #
    app.logger.info(f'Totally {len(updated)} files updated: {updated}')


@local_task(optional=['theme', 'file', 'suffix'])
def aiimage(ctx, file=None, theme='landkit', suffix='.json'):
    """ Invoke AI tools to generate images from generated page content. """
    if not confirm('Are you sure to gen images for page content(s)?'):
        return
    #
    # Prepare
    #
    ai_suffix = '.ai' + suffix
    # (pre_prompt, app_prompt, negative_prompt, steps, cfg, width, height) for different media types
    comfyui_settings = {
        'illustration': (
            'a flat illustration with minimalist style, blue tones, white background',
            'trending on artstation, popular on dribbble',
            'lowres, error, cropped, worst quality, low quality, jpeg artifacts, out of frame, watermark, signature, text\ndeformed, ugly, mutilated, disfigured, extra limbs, extra fingers, extra arms, mutation, bad proportions, malformed limbs, mutated hands, fused fingers, long neck',
            6,  # steps
            4,  # cfg
            1024,  # width
            768,  # height
        ),
        'photo': (
            'realistic photo',
            'high detailed skin, skin pores, intricate design, film grain, dslr, HDR, 64k',
            'lowres, error, cropped, worst quality, low quality, jpeg artifacts, out of frame, watermark, signature, text\ndeformed, ugly, mutilated, disfigured, extra limbs, extra fingers, extra arms, mutation, bad proportions, malformed limbs, mutated hands, fused fingers, long neck\nillustration, painting, drawing, art, sketch',
            4,  # steps
            2,  # cfg
            1024,  # width
            1024,  # height
        ),
    }
    theme_setting = theme_settings[theme]
    templates_folder = theme_setting['templates_folder']
    icons_folder = theme_setting.get('icons_folder')
    icons = []
    if icons_folder:
        for r, _, fs in os.walk(icons_folder):
            for f in fs:
                icons.append(os.path.relpath(os.path.join(r, f), icons_folder))
    #
    app = create_www(runscripts=True)
    with app.app_context():
        # Generate media for each page content file in specified folder
        for fn in os.listdir(templates_folder):
            # Only works for ai generated json files
            if not fn.endswith(ai_suffix):
                continue
            #
            app.logger.info(f'----- {fn} -----')
            if file and file != fn:
                app.logger.info(f'Skip as file name not match: {file}')
                continue
            #
            fp = os.path.join(templates_folder, fn)
            with open(fp, 'r', encoding='utf-8') as f:
                page_data = f.read()
            #
            page_json = json.loads(page_data)
            #
            # ChatGPT4o generation
            #
            app.logger.info(f'--- Analyze Page Content ---')
            groups_for_generation = {
                'illustration': [],  # [(path, demo/current image, related content), ...]
                'photo': [],
                'icon': [],
            }
            # You can comment out a type to skip generation for that type
            if not icons:
                groups_for_generation.pop('icon')

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
                                    app.logger.info(f'Warning: unsupport image type for {vv}')
                                    continue
                                #
                                if it in groups_for_generation:
                                    groups_for_generation[it].append([f'{path_}.{k}[{ii}]', vv, related_content_])
                        else:
                            for ii, vv in enumerate(v):
                                if isinstance(vv, dict):
                                    _iterate(vv, f'{path_}.{k}[{ii}]')
                    elif isinstance(v, str):
                        if k == 'image':
                            it = _guess_image_type(v)
                            if not it:
                                app.logger.info(f'Warning: unsupport image type for {v}')
                                continue
                            #
                            if it in groups_for_generation:
                                groups_for_generation[it].append([f'{path_}.{k}', v, related_content_])
                        elif k == 'icon':
                            if 'icon' in groups_for_generation:
                                groups_for_generation['icon'].append([f'{path_}.{k}', v, related_content_])

            #
            _iterate(page_json)
            #
            updated = 0
            for image_type, images_for_generation in groups_for_generation.items():
                app.logger.info(f'--- Prompt for {image_type} ---')
                # Invoke ChatGPT4o to generate prompt
                generated_prompts = []
                for ig in images_for_generation:
                    related_content = ig[2]
                    app.logger.info(f'Image {ig[0]}: {ig[1]} with related content: {related_content}')
                    if not related_content:
                        app.logger.info('Skip as no related content found')
                        continue
                    #
                    if image_type == 'icon':
                        response = openai.chat_stream(messages=[
                            {'role': 'system', 'content': f'''你是一个网站的图标设计专家，已经设计了很多图标，下面每行表示一个图标，包含了类别和名字：

{chr(10).join(icons)}                          
                            '''},
                            {'role': 'user', 'content': f'''我将提供一两句文案，请根据文案从上述图标中选择一个合适的，并满足如下要求：

1. 从中选择一个图标并直接返回，不能凭空生成不存在的图标
2. 选中的图标能够恰当的体现文案的意思即可

下面是已经选择的图标，请勿重复选择：

{'；'.join(generated_prompts)}
                            
'''},
                            {'role': 'assistant', 'content': '明白了，请提供文案'},
                            {'role': 'user', 'content': related_content}
                        ])
                    else:
                        response = openai.chat_stream(messages=[
                            {'role': 'system', 'content': '你是一个网站设计专家'},
                            {'role': 'user', 'content': f'''我将提供一两句文案，请根据文案设计一个简洁的画面，让网站的用户能够更加直观的理解该文案，并满足如下要求：
    
1. 只需包含具体的人物和环境，返回一句英文的简单的描述即可
2. 人物和环境的描述尽可能简单明了，不超过3人，环境不超过5个物件

下面是已有的描述，请避免生成类似的描述，即不使用已经出现过的人物和物件, 也更换不同的环境：

{'；'.join(generated_prompts)}

'''},
                            {'role': 'assistant', 'content': '明白了，请提供文案'},
                            {'role': 'user', 'content': related_content}
                        ])
                    # Consolidate response stream
                    content = ''
                    print('gpt> ', end='')
                    for chunk in response:
                        print(chunk, end='')
                        content += chunk
                    #
                    content = content.strip().strip("\"").strip("'")  # 返回描述时有可能会带上引号
                    generated_prompts.append(content)
                #
                # ComfyUI generation or Icon selection
                #
                if not generated_prompts:
                    app.logger.info(f'Skip as no prompt generated')
                    continue
                #
                app.logger.info(f'--- Generate for {image_type} ---')
                if image_type == 'icon':
                    generated_images = []
                    # TODO: Hard code icon base folder here, different themes may have different icon sets
                    for i, prompt in enumerate(generated_prompts):
                        app.logger.info(f'{i}: {prompt}')
                        generated_images.append((f'/static/landkit/assets/img/icons/duotone-icons/{prompt}', None))
                else:
                    # Load comfyui icon template from file
                    comfyui_setting = comfyui_settings[image_type]
                    pre_prompt = comfyui_setting[0]
                    app_prompt = comfyui_setting[1]
                    negative_prompt = comfyui_setting[2]
                    schedule_prompt = ''
                    for i, prompt in enumerate(generated_prompts):
                        schedule_prompt += f'"{i}": "{prompt}",\n'
                    #
                    schedule_prompt = schedule_prompt.rstrip(',\n')
                    app.logger.info(f'positive prompt: {pre_prompt}\n{schedule_prompt}\n{app_prompt}')
                    app.logger.info(f'negative prompt: {negative_prompt}')
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
                    comfyui_prompt['5']['inputs']['width'] = comfyui_setting[5]
                    comfyui_prompt['5']['inputs']['height'] = comfyui_setting[6]
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
                        app.logger.info(f'Skip as no images generated')
                        continue
                    #
                    if len(generated_images) != len(images_for_generation):
                        app.logger.info(f'Error: images count not match')
                        continue
                #
                # Update Page Content
                #
                app.logger.info(f'--- Update Content ---')
                for i, ig in enumerate(images_for_generation):
                    path = ig[0][1:]  # Remove leading '.', this path is used to update json content, i.e, 'a.b[0]'
                    current_url = ig[1]
                    gen_url, gen_path = generated_images[i]  # This path is full file path of the generated image
                    app.logger.info(f'Update page content {path} -> {gen_url}')
                    # Check if any special handling needed
                    # i.e, if path endswith size=440x660 means we need to resize the generated image to 440x660
                    if '?' in current_url:
                        option = current_url.split('?')[1]
                        # Use regex to extract width and height
                        m = re.search(r'size=(\d+)x(\d+)', option)
                        if m:
                            width, height = int(m.group(1)), int(m.group(2))
                            # Resize image to widthxheight
                            resize_image(gen_path, gen_path, '!', width, height, 'c')
                            # Append option to gen_url
                            gen_url += '?' + option
                    #
                    json_update_by_path(page_json, path, gen_url)
                    updated += 1
            #
            app.logger.info(f'Totally {updated} images updated')
            if updated > 0:
                with open(fp, 'w', encoding='utf-8') as f:
                    f.write(json_dumps(page_json, pretty=True))
