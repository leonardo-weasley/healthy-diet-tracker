"""HTML 页面路由。

只负责渲染模板；所有数据由 ``app/static/js`` 调用 ``/api/v1/*`` 获取，
因此这里不访问数据库、不调用服务层（00 §C.1）。
"""

from flask import Blueprint, render_template

bp = Blueprint('pages', __name__)


@bp.get('/')
def index():
    return render_template('index.html')


@bp.get('/upload')
def upload():
    return render_template('upload.html')


@bp.get('/result')
def result():
    return render_template('result.html')


@bp.get('/history')
def history():
    return render_template('history.html')
