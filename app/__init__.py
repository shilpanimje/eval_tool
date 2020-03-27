"""
@author: Shilpa Nimje
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os
from apscheduler.schedulers.background import BackgroundScheduler

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'very secrete key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'logdatabase.db')
db = SQLAlchemy(app)
sched = BackgroundScheduler(daemon=True)

app.config.from_object(__name__)
from app import views
sched.start()