from flask import Blueprint, render_template

bp = Blueprint('pages', __name__)


@bp.get('/')
@bp.get('/upload')
@bp.get('/result')
@bp.get('/history')
def page():
    return render_template('placeholder.html')
