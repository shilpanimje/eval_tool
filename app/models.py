"""
@author: Shilpa Nimje
"""

from app import db
from datetime import datetime


# log table
class Logs(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    csv_task_name = db.Column(db.String(255))
    params = db.Column(db.String(255))
    object_name = db.Column(db.String(255))
    csv_task_status = db.Column(db.String(255))
    log_id = db.Column(db.Integer, unique=True)
    task = db.Column(db.String(255))
    event = db.Column(db.String(255))
    status = db.Column(db.String(255))
    details = db.Column(db.String(255))
    processed_time = db.Column(db.Float)
    delivered_time = db.Column(db.Float)
    queued_time = db.Column(db.Float)
    processed_datetime = db.Column(db.String)
    delivered_datetime = db.Column(db.String)
    queued_datetime = db.Column(db.String)
    iteration = db.Column(db.Integer)

    def __init__(
            self,
            csv_task_name,
            params,
            object_name,
            csv_task_status,
            log_id,
            task,
            event,
            status,
            details,
            processed_time,
            delivered_time,
            queued_time,
            processed_datetime,
            delivered_datetime,
            queued_datetime,
            iteration
    ):
        self.csv_task_name = csv_task_name
        self.params = params
        self.object_name = object_name
        self.csv_task_status = csv_task_status
        self.log_id = log_id
        self.task = task
        self.event = event
        self.status = status
        self.details = details
        self.processed_time = processed_time
        self.delivered_time = delivered_time
        self.queued_time = queued_time
        self.processed_datetime = processed_datetime
        self.delivered_datetime = delivered_datetime
        self.queued_datetime = queued_datetime
        self.iteration = iteration


# ietration table
class Iterations(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    iteration_no = db.Column(db.Integer)
    start_date = db.Column(db.String)
    updated_date = db.Column(db.String)

    def __init__(
            self,
            iteration_no,
            start_date,
            updated_date
    ):
        self.iteration_no = iteration_no
        self.start_date = start_date
        self.updated_date = updated_date


def truncateTable():
    """delete all data from table if exist"""
    data = Logs.query.all()

    if data:
        for i in data:
            if i:
                db.session.delete(i)
                db.session.commit()
    return True


def getAllData(iteration=None):
    """get all data from table for specific iteration"""

    query = "SELECT * FROM logs WHERE csv_task_status = '{status}' AND iteration = {iteration}".format(
        status='passed', iteration=iteration)
    data = db.engine.execute(query).fetchall()

    return data


def getAllIterationsData():
    """get all data from table for all iterations"""
    query = "SELECT * FROM logs WHERE csv_task_status = '{status}'".format(
        status='passed')
    data = db.engine.execute(query).fetchall()

    return data


def getDataForReport():
    """get all data from table"""
    query = "SELECT event, count(event) as samples, min(delivered_time) as min_delivered_time_in_ms, " \
            "max(delivered_time) as max_delivered_time_in_ms, avg(delivered_time) as avg_delivered_time_in_ms, " \
            "min(queued_time) as min_queued_time_in_ms, max(queued_time) max_queued_time_in_ms, avg(queued_time) " \
            "as avg_queued_time_in_ms FROM logs WHERE event != '' AND status NOT LIKE '%Skipped%' GROUP BY event"
    data = db.engine.execute(query).fetchall()
    dataList = []
    for item in data:
        dataList.append([
            item[0],
            item[1],
            item[2],
            item[3],
            item[4],
            item[5],
            item[6],
            item[7]
        ])

    return dataList


def getAllSkippedEvets():
    """Get all skipped events"""
    query = "SELECT event, status FROM logs WHERE event != ''"
    data = db.engine.execute(query).fetchall()
    count = 0
    events = []
    for item in data:
        if 'Skipped' in item[1]:
            events.append(item[0])
            count = count + 1
    return dict(
        eventList=events,
        totalSkipped=count
    )


def getAllSkippedTasks():
    """Get all skipped tasks"""
    query = "SELECT task, status FROM logs WHERE task != ''"
    data = db.engine.execute(query).fetchall()
    count = 0
    tasks = []
    for item in data:
        if 'Skipped' in item[1]:
            tasks.append(item[0])
            count = count + 1
    return dict(
        taskList=tasks,
        totalSkipped=count
    )


def saveEventStatusData(data):
    """Save data after execute event"""
    # save data to log table
    logs = Logs(
        csv_task_name=data.get('task_name'),
        params=data.get('params'),
        object_name=data.get('object_name'),
        csv_task_status=data.get('status').lower(),
        log_id=None,
        task='',
        event='',
        status='',
        details='',
        processed_time=0,
        delivered_time=0,
        queued_time=0,
        processed_datetime='',
        delivered_datetime='',
        queued_datetime='',
        iteration=data.get('iteration', 1))

    db.session.add(logs)
    db.session.commit()


def updateEventData(id, logData):
    """Update event details"""
    query = "SELECT * FROM logs WHERE id = {id}".format(id=id)
    data = db.engine.execute(query).fetchall()
    if data:
        msTime = calculateTime(logData)

        updateQuery = "UPDATE logs SET " \
                      " log_id = {log_id}, " \
                      " task = '{task}'," \
                      " event = '{event}', " \
                      " status = '{status}', " \
                      " details = '{details}'," \
                      " processed_time = {processed_time}, " \
                      " delivered_time = {delivered_time}, " \
                      " queued_time = {queued_time}, " \
                      " processed_datetime = '{processed_datetime}', " \
                      " delivered_datetime = '{delivered_datetime}', " \
                      " queued_datetime = '{queued_datetime}' " \
                      " WHERE id = {id}".format(
                        log_id=logData.get("id"),
                        task=logData.get('task', ''),
                        event=logData.get("event", ''),
                        status=", ".join(logData.get("status_list", '')),
                        details=logData.get("details", ''),
                        processed_time=msTime.get("proccessed_time_in_ms"),
                        delivered_time=msTime.get("delivered_time_in_ms"),
                        queued_time=msTime.get("queued_time_in_ms"),
                        processed_datetime=msTime.get("processed_datetime"),
                        delivered_datetime=msTime.get("delivered_datetime"),
                        queued_datetime=msTime.get("queued_datetime"),
                        id=id)

        db.engine.execute(updateQuery)
        db.session.commit()


def calculateTime(data):
    """calculate time in milisecond"""
    delivered_time_in_ms = 0
    queued_time_in_ms = 0
    proccessed_time_in_ms = 0
    processed_datetime = None
    delivered_datetime = None
    queued_datetime = None

    # calculate time in ms
    if validatedateFormat(data.get('proccessed_datetime')):
        proccessed_time = datetime.strptime(data.get('proccessed_datetime'), '%Y-%m-%d %H:%M:%S')
        proccessed_time_in_ms = proccessed_time.timestamp() * 1000 + int(data.get('proccessed_ms'))
        processed_datetime = datetime.strptime(data.get('proccessed_datetime'), '%Y-%m-%d %H:%M:%S')

    # calculate delivered time in ms
    if data.get('delivered_datetime'):
        if validatedateFormat(data.get('delivered_datetime')) and validatedateFormat(data.get('proccessed_datetime')):
            delivered_time = datetime.strptime(data.get('delivered_datetime'), '%Y-%m-%d %H:%M:%S') - datetime.strptime(
                data.get('proccessed_datetime'), '%Y-%m-%d %H:%M:%S')
            delivered_time_in_ms = delivered_time.total_seconds() * 1000
            delivered_time_in_ms = delivered_time_in_ms + int(data.get('delivered_ms'))
            delivered_datetime = datetime.strptime(data.get('delivered_datetime'), '%Y-%m-%d %H:%M:%S')

    # calculate queued time in ms
    if data.get('queued_datetime'):
        if validatedateFormat(data.get('delivered_datetime')) and validatedateFormat(data.get('queued_datetime')):
            queued_time = datetime.strptime(data.get('delivered_datetime'), '%Y-%m-%d %H:%M:%S') - datetime.strptime(
                data.get('queued_datetime'), '%Y-%m-%d %H:%M:%S')
            queued_time_in_ms = queued_time.total_seconds() * 1000
            queued_time_in_ms = queued_time_in_ms + int(data.get('queued_ms'))
            queued_datetime = datetime.strptime(data.get('queued_datetime'), '%Y-%m-%d %H:%M:%S')

    return dict(
        proccessed_time_in_ms=proccessed_time_in_ms,
        delivered_time_in_ms=delivered_time_in_ms,
        queued_time_in_ms=queued_time_in_ms,
        processed_datetime=processed_datetime,
        delivered_datetime=delivered_datetime,
        queued_datetime=queued_datetime
    )


def getFailedEventList():
    """get all data from table"""
    query = "SELECT * FROM logs WHERE csv_task_status = '{status}'".format(status='failed')
    data = db.engine.execute(query).fetchall()
    return data


def validatedateFormat(date):
    """Validate date format"""
    if date:
        try:
            datetime.strptime(date, '%Y-%m-%d %H:%M:%S')
            return True
        except ValueError:
            return False
    else:
        return False


# -------------------------------------------------------
# Table iterations function start here
# ------------------------------------------------------


def saveIterationsData():
    # save data to iterations table
    iterations_data = Iterations(
        iteration_no=1,
        start_date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        updated_date=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )
    db.session.add(iterations_data)
    db.session.commit()


def updateIterationsData(iteration=None):
    # update data to iterations table
    data = getIterationsData()
    if data and iteration is not None:
        updateQuery = "UPDATE iterations SET " \
                      " iteration_no = {iteration}, " \
                      " updated_date = '{updated_date}' " \
                      " WHERE id = {id}".format(
                        iteration=iteration,
                        updated_date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        id=data[0][0],
                        )

        db.engine.execute(updateQuery)
        db.session.commit()


def getIterationsData():
    query = "SELECT * FROM  iterations "
    data = db.engine.execute(query).fetchall()
    return data


def truncateIterationData():
    """delete all data from table if exist"""
    data = Iterations.query.all()

    if data:
        for i in data:
            if i:
                db.session.delete(i)
                db.session.commit()
    return True


def rollBackAlldata(iteration):
    """rollback all data"""
    if iteration:
        # delete Iterations table data
        if iteration > 1:
            updateIterationsData(iteration - 1)
        else:
            truncateIterationData()

        # delete iteration data from log  table
        data = getAllData(iteration)
        if data:
            for i in data:
                if i:
                    query = "DELETE FROM logs WHERE id={id}".format(id=i[0])
                    db.engine.execute(query)

