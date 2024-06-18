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

from invoke import task as local_task

from paramiko import RSAKey
from fabric import task

from www import create_www
from www.commons import json_simplify, json_dumps, json_merge
from www.extensions import openai

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


@local_task
def ai(ctx):
    """ Invoke ai tools to generate static contents, i.e, json, images, etc. """
    if confirm('Are you sure to use ai tools such as chatGPT/StableDiffusion to gen static contents?'):
        # Read content of README.md
        with open('README.md') as f:
            readme = f.read()
            # if '# koiseed' in readme:
            #     print('# koiseed is found in README.md, Please make update readme file to describe your project')
            #     return
        # Print readme content
        print('\n----- README.md -----\n')
        print(readme)
        # Create
        app = create_www(runscripts=True)
        with app.app_context():
            # Generate static contents
            # Read each json files in www/templates/public
            directory = 'www/templates/pub-demo'
            demo_suffix = '.json'
            for fn in os.listdir(directory):
                if fn == 'post.json':
                # if fn.endswith(demo_suffix):
                    print(f'\n----- {fn} -----\n')
                    fg = os.path.join(directory, fn.replace(demo_suffix, '.jsonai'))
                    # if os.path.exists(fg):
                    #    print(f'file exists, skip')
                    #    continue
                    #
                    fp = os.path.join(directory, fn)
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
                        {'role': 'system', 'content': '你是一个网站开发助理'},
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
