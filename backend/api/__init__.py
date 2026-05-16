from flask import Blueprint

blueprint = Blueprint("api", __name__)

from api import auth, dashboard, homework, tests, schedule, grades, conduct, library, messages, ai
