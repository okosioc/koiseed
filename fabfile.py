# -*- coding: utf-8 -*-
"""
    fabfile
    ~~~~~~~~~~~~~~

    Fab.

    :copyright: (c) 2016 by fengweimin.
    :date: 16/7/21
"""

from paramiko import RSAKey
from fabric import task

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
