# -*- coding: utf-8 -*-
"""
    common
    ~~~~~~~~~~~~~~

    公用的数据结构.

    :copyright: (c) 2021 by weiminfeng.
    :date: 2022/11/1
"""

from typing import List, ForwardRef

from py3seed import BaseModel, ModelField as Field, Format, MongoModel, register


class Series(BaseModel):
    """ 序列, 适用于各种线图/柱状图/饼图的绘制. """
    title: str = Field(title='标题')
    total: float = Field(default=.0, title='数值的和')
    names: List[str] = Field(required=False, title='各元素的名字')
    values: List[float] = Field(required=False, title='各元素对应的数值')
    unit: str = Field(required=False, title='单位')


class Action(BaseModel):
    """ 动作. """
    icon: str = Field(required=False, title='图标')
    title: str = Field(required=False, title='标题')
    remarks: str = Field(required=False, title='备注')
    url: str = Field(title='转跳地址或交互脚本')  # e.g, /dashboard or javascript:coming();
    cls: str = Field(required=False, title='样式')


@register
class Block(MongoModel):
    """ 页面版块, 仅包含内容. """
    key: str = Field(title='key')  # 用于查询, 方便页面模版引用指定版块的内容
    #
    icon: str = Field(required=False, title='图标')
    tag: str = Field(required=False, title='标签')
    tags: List[str] = Field(required=False, title='标签列表')
    #
    title: str = Field(required=False, title='标题')
    subtitle: str = Field(required=False, title='子标题')
    content: str = Field(required=False, format_=Format.TEXTAREA, title='内容')
    remarks: str = Field(required=False, title='备注')
    author: str = Field(required=False, title='作者')
    avatar: str = Field(required=False, title='头像')
    #
    image: str = Field(required=False, format_=Format.IMAGE, title='图片')
    images: List[str] = Field(required=False, format_=Format.IMAGE, title='图片列表')
    #
    val: float = Field(required=False, title='数值')
    vals: List[float] = Field(required=False, title='数值列表')
    unit: str = Field(required=False, title='单位')
    #
    hide: bool = Field(default=False, title='是否隐藏')  # 默认显示
    url: str = Field(required=False, title='转跳地址')
    cls: str = Field(required=False, title='样式')
    color: str = Field(required=False, title='颜色')
    role: str = Field(required=False, title='角色', description='能访问此版块的角色')
    action: Action = Field(required=False, title='动作')
    actions: List[Action] = Field(required=False, title='动作列表')
    #
    hide_children: bool = Field(default=False, title='是否隐藏子版块')  # 默认显示
    children: List[ForwardRef('Block')] = Field(required=False, title='子版块')
    #
    __indexes__ = [
        {'fields': ['key'], 'unique': True},
    ]
