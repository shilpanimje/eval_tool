"""
@author: Shilpa Nimje
"""

from app import app, db, sched
from flask import Flask, render_template, request, jsonify, redirect, session, url_for, flash
from app.lib import proccesscsv
import json
from app import models
from app.lib import event
from werkzeug import secure_filename
import os
import pandas as pd
from datetime import datetime
from datetime import timedelta


UPLOAD_FOLDER = os.getcwd() + '/uploads'
ALLOWED_EXTENSIONS = set(['csv'])
DELAY = 5
START_TIME = datetime.now() + timedelta(minutes=1)
START_TIME = datetime.strftime(START_TIME, '%Y-%m-%d %H:%M:%S')
END_TIME = datetime.now() + timedelta(days=3)
END_TIME = datetime.strftime(END_TIME, '%Y-%m-%d %H:%M:%S')


@app.route('/', methods=['GET', 'POST'])
def homes():
    """Index page"""
    data = models.getAllIterationsData()
    if data:
        return render_template('index.html', show_dialog=True)
    else:
        # truncate iteration data
        models.truncateIterationData()
        # truncate all data when it comes to home page
        models.truncateTable()
        # delete log file if exist
        proccesscsv.deleteFile()
        proccesscsv.deleteCsvFiles()
        return render_template('index.html', show_dialog=False)


@app.route('/delete', methods=['GET'])
def delete():
    # truncate iteration data
    models.truncateIterationData()
    # truncate all data when it comes to home page
    models.truncateTable()
    # delete log file if exist
    proccesscsv.deleteFile()
    proccesscsv.deleteCsvFiles()
    return redirect('/')


@app.route('/show_log', methods=['GET', 'POST'])
def show_log():
    """function to show log"""
    data = models.getAllIterationsData()
    failedData = models.getFailedEventList()
    eventList = []
    failedDataList = []
    if data:
        for item in data:
            if item.log_id is not None:
                eventList.append([item.log_id, item.event, item.status])
    else:
        eventList.append(['No Records.', '', ''])
    df = pd.DataFrame(eventList, columns=['Log ID', 'EVENT', 'STATUS'])
    df.index = df.index + 1

    if failedData:
        for item in failedData:
            failedDataList.append([item.csv_task_name, item.csv_task_status])
    else:
        failedDataList.append(['No Records.', ''])
    df2 = pd.DataFrame(failedDataList, columns=['EVENT', 'STATUS'])
    df2.index = df2.index + 1

    return render_template('show_log.html', eventTable=df, failedData=df2)


@app.route('/exportlog', methods=['POST'])
def exportlog():
    data = models.getAllIterationsData()
    path = proccesscsv.downloadCSV(data)
    return json.dumps(path)


@app.route('/generate-events', methods=['POST'])
def generate_events():
    if request.method == 'POST':
        files = request.files.getlist('events_file[]')
        vcenterIP = request.form.get('vcenter_ip')
        vcenterUsername = request.form.get('vcenter_username')
        vcenterPassword = request.form.get('vcenter_password')
        mvaIP = request.form.get('mva_ip')
        mvaUsername = request.form.get('mva_username')
        mvaPassword = request.form.get('mva_password')

        if not files or not vcenterIP or not vcenterUsername or not vcenterPassword or not mvaIP or not mvaUsername or not mvaPassword:
            error = 'Please enter all required fields.'
            return render_template('index.html', error=error)
        count = 1
        filenames = []

        for file in files:
            if file.filename == '':
                error = 'Please select file for events.'
                return render_template('index.html', error=error)

            if allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                count = count + 1
                new_name = os.path.join(UPLOAD_FOLDER, 'event_file_'+str(count)+'.csv')
                os.rename(os.path.join(UPLOAD_FOLDER, filename), new_name)
                filenames.append(new_name)

        # create config dict
        configDict = dict(
            vcenterIP=vcenterIP,
            vcenterUsername=vcenterUsername,
            vcenterPassword=vcenterPassword,
            mvaIP=mvaIP,
            mvaUsername=mvaUsername,
            mvaPassword=mvaPassword
        )

        print("Start writing config file.")
        proccesscsv.writeConfigFile(json.dumps(configDict), json.dumps(filenames))
        print("start executing csv files")
        result = proccesscsv.executeAll(iteration=1)
        if result:
            return redirect(url_for('show_log'))


@app.route('/generate_report', methods=['POST', 'GET'])
def generate_report():
    """Generate report for logs"""
    totalSkippedEvents = models.getAllSkippedEvets()
    itemList = []
    data = models.getDataForReport()
    columns = pd.MultiIndex.from_tuples([
        ('', 'event'),
        ('', 'samples'),
        ('delivered_time (ms)', 'min'),
        ('delivered_time (ms)', 'max'),
        ('delivered_time (ms)', 'avg'),
        ('queued_time (ms)', 'min'),
        ('queued_time (ms)', 'max'),
        ('queued_time (ms)', 'avg'),
        ])
    df = pd.DataFrame(data, columns=columns)
    df.index = df.index + 1
    df_skipped_event = pd.DataFrame(totalSkippedEvents['eventList'], columns=['Event Name'])
    df_skipped_event.index = df_skipped_event.index + 1
    return render_template(
        'report.html',
        data=df,
        skippedEvent=totalSkippedEvents['totalSkipped'],
        skippedEventTable=df_skipped_event)


@app.route('/verify_new_data', methods=['POST'])
def verify_new_data():
    """Function to check if new data available in database"""
    iteration_data = models.getIterationsData()
    log_file_exists = proccesscsv.checkLogFileExist()
    if iteration_data and log_file_exists:
        return json.dumps({'iteration': iteration_data[0][1], 'status': True})
    else:
        return json.dumps({'status': False})


# ----------------------------------------------------------------------------------------------------------
# scheduler for csv execution
# ---------------------------------------------------------------------------------------------------------
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ----------------------------------------------------------------------------------------------------------
# scheduler for csv execution
# ---------------------------------------------------------------------------------------------------------
@sched.scheduled_job('interval', minutes=DELAY, start_date=START_TIME, end_date=END_TIME)
def do_repeat():
    print("------------------------STARTING SCHEDULER------------")
    print("START_TIME: " + str(START_TIME))
    print("END_TIME: " + str(END_TIME))
    iteration_data = models.getIterationsData()
    log_file_exists = proccesscsv.checkLogFileExist()

    # if 1st iteration is available in database then do execute incrementing 1st iteration
    if iteration_data and log_file_exists:
        iteration = iteration_data[0][1] + 1
        print("-------------------STARTING NEW ITERATION-------------------")
        print("ITERATION: " + str(iteration))
        result = proccesscsv.executeAll(iteration)
        if result:
            print("ITERATION: " + str(iteration) + " COMPLETED")
        else:
            print("ITERATION: " + str(iteration) + " FAILED")
    else:
        print("Please wait.... Start date not updated yet.")

