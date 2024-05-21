# -*- coding: utf-8 -*-
"""
    fabfile
    ~~~~~~~~~~~~~~

    Fab.

    :copyright: (c) 2016 by fengweimin.
    :date: 16/7/21
"""
import json
import os

from invoke import task as local_task

from paramiko import RSAKey
from fabric import task

from www import create_www
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
        print('\n----- END -----\n')
        # Create
        app = create_www(runscripts=True)
        with app.app_context():
            # Generate static contents
            # Read each json files in www/templates/public
            directory = 'www/templates/pub-demo'
            for fn in os.listdir(directory):
                if fn.endswith('.json'):
                    print(f'Processing {fn}...')
                    fp = os.path.join(directory, fn)
                    with open(fp, 'r', encoding='utf-8') as f:
                        data = f.read()
                    #
                    gpt_template = f'''下面是用来渲染我的jinja2模版的数据，用于网页的各个部分：
    
    {data}
    
    我将提供一个新网站的介绍，需要复用上述数据结构，请保持结构不变，仅替换title/subtitle/content等文本字段的内容，并满足如下要求：
    
    1. 保证生成的内容符合该介绍，且无需参考原始数据的内容
    2. 如果遇到lorom ipsum占位数据，保持不变
    3. 生成的内容应当与我提供的介绍是同一个语言
    4. 生成的内容以jinja2格式显示
    
    如果你明白了，请确认并等待新网站的介绍 ~
    '''
                    response = openai.chat_stream(messages=[
                        {'role': 'system', 'content': '你是一个网站开发助理'},
                        {'role': 'user', 'content': gpt_template},
                        {'role': 'assistant', 'content': '明白了，请提供新网站的介绍，以便我能够根据您提供的信息生成新的内容。'},
                        {'role': 'user', 'content': '''
    KoiSeed，基于数据结构及其视图，快速生成跨平台的种子项目。
    
    - 通过简单的方式定义业务所需的数据结构以及相互关系，无需考虑存储细节，支持主流数据库
    - 为数据结构定义直观的视图，可生成跨平台的种子项目，如网站、小程序、iOS和Android应用等
    - 生成的种子项目符合最佳实践且易于维护，并通过自动合并的机制实现了代码生成与定制开发的平衡                        
                            '''}
                    ],
                        # For Aruze OpenAI, use deployment name instead of model name
                        # model='open-gpt4-turbo-01')
                        # For OpenAI, use model directly
                        model='gpt-4o')
                    #
                    for content in response:
                        print(content, end='')
                    #
                    break
