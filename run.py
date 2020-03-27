#! /usr/bin/env python
"""
@author: Shilpa Nimje
"""

from app import app, db, sched
db.create_all()
# start schedular for script
app.run(debug=True, host="0.0.0.0", port=5005, use_reloader=False)
