from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from models.user import User, PasswordResetToken
from models.school import School, Class, Subject
from models.academic import Assignment, Grade, SchedulePeriod
from models.conduct import ConductEvent
from models.library import Book, BookCheckout
from models.social import Group, group_members, Message, Activity, ActivityEnrollment, ActivityEvent, CommunityService
from models.ai_session import AISession, AIMessage
from models.notification import Notification
from models.daily_digest import DailyDigest
from models.sent_reminder import SentReminder
from models.meeting import Meeting
from models.nav_config import NavConfig
