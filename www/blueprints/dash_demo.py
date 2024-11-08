""" dash-demo module. """
import os
import re

from datetime import datetime
from bson import ObjectId

from flask import Blueprint, render_template, current_app, redirect, request, abort, jsonify, url_for
from flask_login import current_user
from py3seed import populate_model, populate_search

from core.models import DemoPostStatus, DemoPost, DemoUser, DemoProject, DemoTask, DemoProjectDashboard, DemoTeam
from www.commons import get_id, get_ids, auth_permission, admin_permission, json_dumps

dash_demo = Blueprint('dash-demo', __name__, url_prefix='/dash-demo')


@dash_demo.route('/post-list')
@auth_permission
def post_list():
    """ 文章列表. """
    page, sort = request.args.get('p', 1, lambda x: int(x) if x.isdigit() else 1), [('create_time', -1)]
    search, condition = populate_search(request.args, DemoPost)
    current_app.logger.info(f'Try to search demo post by {condition}, sort by {sort}')
    demo_posts, pagination = DemoPost.search(condition, page, sort=sort)
    #
    return render_template('dash-demo/post-list.html',
                           search=search, pagination=pagination, demo_posts=demo_posts)


@dash_demo.route('/post-list-delete-demo-posts', methods=('POST',))
@auth_permission
def post_list_delete_demo_posts():
    """ 删除文章列表. """
    ids_ = get_ids(int)
    current_app.logger.info(f'Try to delete demo post(s) with ids {ids_}')
    total_deleted = 0
    for id_ in ids_:
        existing = DemoPost.find_one(id_)
        if not existing:
            continue
        #
        if existing.delete():
            total_deleted += 1
    #
    if total_deleted == 0:
        return jsonify(error=1, message='Delete zero demo post!')
    #
    return jsonify(error=0, message=f'Deleted {total_deleted} demo post(s).')


@dash_demo.route('/post-edit')
@auth_permission
def post_edit():
    """ 文章编辑. """
    args, preloads = [], {}
    id_ = get_id(int)
    if id_:
        demo_post = DemoPost.find_one(id_)
        if not demo_post:
            abort(404)
    else:
        demo_post = DemoPost()
    #
    return render_template('dash-demo/post-edit.html', demo_post=demo_post, args=args, **preloads)


@dash_demo.route('/post-edit-upcreate', methods=('POST',))
@auth_permission
def post_edit_upcreate():
    """ 保存文章编辑. """
    req_demo_post = populate_model(request.form, DemoPost)
    id_ = get_id(int)
    current_app.logger.info(f'Try to save demo post with id {id_}: {req_demo_post}')
    #
    if not id_:
        #
        req_demo_post.author = current_user
        if req_demo_post.status == DemoPostStatus.PUBLISHED:
            req_demo_post.publish_time = datetime.now()
        #
        req_demo_post.save()
        id_ = req_demo_post.id
        current_app.logger.info(f'Successfully create demo post {id_}')
    else:
        existing = DemoPost.find_one(id_)
        if not existing:
            abort(404)
        #
        existing.title = req_demo_post.title
        existing.subtitle = req_demo_post.subtitle
        existing.tags = req_demo_post.tags
        existing.cover = req_demo_post.cover
        existing.featured = req_demo_post.featured
        existing.status = req_demo_post.status
        existing.content = req_demo_post.content
        #
        if existing.status == DemoPostStatus.PUBLISHED:
            existing.publish_time = datetime.now()
        #
        existing.update_time = datetime.now()
        existing.save()
        current_app.logger.info(f'Successfully update demo post {id_}')
    #
    return jsonify(error=0, message='Save demo post successfully.', id=id_)


@dash_demo.route('/post-preview')
@auth_permission
def post_preview():
    """ 文章预览. """
    id_ = get_id(int)
    demo_post = DemoPost.find_one(id_)
    if not demo_post:
        abort(404)
    #
    return render_template('dash-demo/post-preview.html', demo_post=demo_post)


@dash_demo.route('/project-list')
@auth_permission
def project_list():
    """ 项目管理. """
    page, sort = request.args.get('p', 1, lambda x: int(x) if x.isdigit() else 1), [('create_time', -1)]
    search, condition = populate_search(request.args, DemoProject)
    current_app.logger.info(f'Try to search demo project by {condition}, sort by {sort}')
    demo_projects, pagination = DemoProject.search(condition, page, sort=sort)
    #
    return render_template('dash-demo/project-list.html',
                           search=search, pagination=pagination, demo_projects=demo_projects)


@dash_demo.route('/project-detail')
@auth_permission
def project_detail():
    """ 项目详情. """
    id_ = get_id(int)
    demo_project = DemoProject.find_one(id_)
    if not demo_project:
        abort(404)
    #
    return render_template('dash-demo/project-detail.html', demo_project=demo_project)


@dash_demo.route('/project-edit')
@auth_permission
def project_edit():
    """ 项目编辑. """
    args, preloads = [], {}
    id_ = get_id(int)
    if id_:
        demo_project = DemoProject.find_one(id_)
        if not demo_project:
            abort(404)
    else:
        demo_project = DemoProject()
    #
    demo_users, demo_users_pagination = DemoUser.search({}, projection=['avatar', 'name', 'status', 'roles', 'email', 'phone', 'create_time'], sort=[('create_time', -1)])
    current_app.logger.info(f'Preloaded {len(demo_users)} demo users')
    preloads.update({'demo_users': demo_users, 'demo_users_pagination': dict(demo_users_pagination), })
    #
    return render_template('dash-demo/project-edit.html', demo_project=demo_project, args=args, **preloads)


@dash_demo.route('/project-edit-upcreate', methods=('POST',))
@auth_permission
def project_edit_upcreate():
    """ 保存项目编辑. """
    req_demo_project = populate_model(request.form, DemoProject)
    id_ = get_id(int)
    current_app.logger.info(f'Try to save demo project with id {id_}: {req_demo_project}')
    #
    if not id_:
        req_demo_project.save()
        id_ = req_demo_project.id
        current_app.logger.info(f'Successfully create demo project {id_}')
    else:
        existing = DemoProject.find_one(id_)
        if not existing:
            abort(404)
        #
        existing.title = req_demo_project.title
        existing.description = req_demo_project.description
        existing.status = req_demo_project.status
        existing.value = req_demo_project.value
        existing.start = req_demo_project.start
        existing.end = req_demo_project.end
        existing.percent = req_demo_project.percent
        existing.members = req_demo_project.members
        existing.files = req_demo_project.files
        existing.activities = req_demo_project.activities
        #
        existing.update_time = datetime.now()
        existing.save()
        current_app.logger.info(f'Successfully update demo project {id_}')
    #
    return jsonify(error=0, message='Save demo project successfully.', id=id_)


@dash_demo.route('/project-edit-search-demo-users', methods=('POST',))
@auth_permission
def project_edit_search_demo_users():
    """ 查找用户. """
    page, sort = request.form.get('p', 1, lambda x: int(x) if x.isdigit() else 1), [('create_time', -1)]
    search, condition = populate_search(request.form, DemoUser)
    current_app.logger.info(f'Try to search demo user at page {page} by {condition}, sort by {sort}')
    demo_users, pagination = DemoUser.search(condition, page, projection=['avatar', 'name', 'status', 'roles', 'email', 'phone', 'create_time'], sort=sort)
    return jsonify(error=0, message='Search demo user successfully.', pagination=dict(pagination), demo_users=demo_users)


@dash_demo.route('/index-project')
@auth_permission
def index_project():
    """ 项目仪表盘. """
    # NOTE: 目前是实时扫描数据并整合为一个仪表盘数据, 实际应用中应该是是使用定时任务来生成
    dpd = DemoProjectDashboard()
    # Metric x4
    demo_projects = DemoProject.find()
    demo_users = DemoUser.find()
    #
    dpd.active_projects_count = len(demo_projects)
    dpd.active_projects_value = sum(map(lambda x: x.value, demo_projects))
    dpd.members_count = len(demo_users)
    dpd.tasks_count = sum(map(lambda x: len(x.tasks), demo_projects))
    # Table
    dpd.active_projects = demo_projects
    # Timeline
    recent_activities = []
    for p in demo_projects:
        recent_activities.extend(p.activities)
    #
    recent_activities.sort(key=lambda x: x.time, reverse=True)
    dpd.recent_activities = recent_activities[:10]
    #
    return render_template('dash-demo/index-project.html', demo_project_dashboard=dpd)


@dash_demo.route('/task-detail')
@auth_permission
def task_detail():
    """ 任务详情. """
    id_ = get_id(int)
    demo_task = DemoTask.find_one(id_)
    if not demo_task:
        abort(404)
    #
    return render_template('dash-demo/task-detail.html', demo_task=demo_task)


@dash_demo.route('/task-edit')
@auth_permission
def task_edit():
    """ 任务编辑. """
    args, preloads = [], {}
    id_ = get_id(int)
    if id_:
        demo_task = DemoTask.find_one(id_)
        if not demo_task:
            abort(404)
    else:
        demo_task = DemoTask()
        #
        if 'project_id' in request.args:
            project_id = int(request.args.get('project_id'))
            demo_task.project = DemoProject.find_one(project_id)
            args.append(('project_id', project_id))
    #
    demo_users, demo_users_pagination = DemoUser.search({}, projection=['avatar', 'name', 'status', 'roles', 'email', 'phone', 'create_time'], sort=[('create_time', -1)])
    current_app.logger.info(f'Preloaded {len(demo_users)} demo users')
    preloads.update({'demo_users': demo_users, 'demo_users_pagination': dict(demo_users_pagination), })
    #
    return render_template('dash-demo/task-edit.html', demo_task=demo_task, args=args, **preloads)


@dash_demo.route('/task-edit-upcreate', methods=('POST',))
@auth_permission
def task_edit_upcreate():
    """ 保存任务编辑. """
    req_demo_task = populate_model(request.form, DemoTask)
    id_ = get_id(int)
    current_app.logger.info(f'Try to save demo task with id {id_}: {req_demo_task}')
    #
    if not id_:
        req_demo_task.save()
        id_ = req_demo_task.id
        current_app.logger.info(f'Successfully create demo task {id_}')
    else:
        existing = DemoTask.find_one(id_)
        if not existing:
            abort(404)
        #
        existing.title = req_demo_task.title
        existing.status = req_demo_task.status
        existing.content = req_demo_task.content
        existing.start = req_demo_task.start
        existing.end = req_demo_task.end
        existing.user = req_demo_task.user
        #
        existing.update_time = datetime.now()
        existing.save()
        current_app.logger.info(f'Successfully update demo task {id_}')
    #
    return jsonify(error=0, message='Save demo task successfully.', id=id_)


@dash_demo.route('/team-profile')
@auth_permission
def team_profile():
    """ 团队设置. """
    preloads = {}
    id_ = get_id(int)
    demo_team = DemoTeam.find_one(id_)
    if not demo_team:
        abort(404)
    #
    return render_template('dash-demo/team-profile.html', demo_team=demo_team, **preloads)


@dash_demo.route('/team-profile-update', methods=('POST',))
@auth_permission
def team_profile_update():
    """ 保存团队设置. """
    req_demo_team = populate_model(request.form, DemoTeam)
    id_ = get_id(int)
    current_app.logger.info(f'Try to save demo team with id {id_}: {req_demo_team}')
    #
    existing = DemoTeam.find_one(id_)
    if not existing:
        abort(404)
    #
    existing.name = req_demo_team.name
    existing.code = req_demo_team.code
    existing.remarks = req_demo_team.remarks
    existing.logo = req_demo_team.logo
    #
    existing.update_time = datetime.now()
    existing.save()
    current_app.logger.info(f'Successfully update demo team {id_}')
    #
    return jsonify(error=0, message='Save demo team successfully.', id=id_)


@dash_demo.route('/team-members')
@auth_permission
def team_members():
    """ 团队成员. """
    id_ = get_id(int)
    demo_team = DemoTeam.find_one(id_)
    if not demo_team:
        abort(404)
    #
    return render_template('dash-demo/team-members.html', demo_team=demo_team)


@dash_demo.route('/user-profile')
@auth_permission
def user_profile():
    """ 用户设置. """
    preloads = {}
    id_ = get_id(int)
    demo_user = DemoUser.find_one(id_)
    if not demo_user:
        abort(404)
    #
    return render_template('dash-demo/user-profile.html', demo_user=demo_user, **preloads)


@dash_demo.route('/user-profile-update', methods=('POST',))
@auth_permission
def user_profile_update():
    """ 保存用户设置. """
    req_demo_user = populate_model(request.form, DemoUser)
    id_ = get_id(int)
    current_app.logger.info(f'Try to save demo user with id {id_}: {req_demo_user}')
    #
    existing = DemoUser.find_one(id_)
    if not existing:
        abort(404)
    #
    existing.name = req_demo_user.name
    existing.phone = req_demo_user.phone
    existing.intro = req_demo_user.intro
    existing.avatar = req_demo_user.avatar
    #
    existing.update_time = datetime.now()
    existing.save()
    current_app.logger.info(f'Successfully update demo user {id_}')
    #
    return jsonify(error=0, message='Save demo user successfully.', id=id_)


@dash_demo.route('/index')
@auth_permission
def index():
    """ Dash index. """
    return redirect(url_for('dash-demo.index_project'))


@dash_demo.route('/profile')
@auth_permission
def profile():
    """ User profile page. """
    return redirect(url_for('dash-demo.user_profile', id=current_user.id))
