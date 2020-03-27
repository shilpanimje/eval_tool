#!/usr/bin/env python
'''
Script to read log and generate csv from log file
@author: Shilpa Nimje
'''

import json
import re
import pandas as pd
import os
from app.lib import client
from threading import Thread
import time
from app.lib import event
from app import models


LOCAL_FILE = os.getcwd() + '/log.txt'
REMOTE_FILE = '/var/log/custom-logs/log.txt'
FILENAME = LOCAL_FILE
CONFIG_DICT = ''
FLAG = False
CONFIG_FILE = os.getcwd() + '/config.txt'
ITERATOR_COUNT = 0
TOTAL_COUNT = 5


def generateLogTxtFile(configDict, csvFiles, iteration=None):
    """Function to run simultaneously tail command and upload csv operation"""
    global CONFIG_DICT
    CONFIG_DICT = configDict
    sshclient = client.startConnection(configDict)

    if not sshclient:
        return False

    tail = Thread(target=executeTail, args=(sshclient,))
    executetask = Thread(target=executeEvents, args=(configDict, csvFiles, iteration,))
    tail.start()
    executetask.start()
    executetask.join()
    tail.join()
    closeClientConnection(sshclient)
    # copy file from remote to local
    result = copyFile(iteration)
    if result:
        return True
    else:
        return False


def executeTail(sshclient):
    """Function to generate log.txt"""
    print("Start executing tail command")

    sshclient.exec_command("rm " + REMOTE_FILE)
    sshclient.exec_command("tail -f /var/log/container/eventmanager/eventmgr.log > " + REMOTE_FILE)
    time.sleep(30)
    if not FLAG:
        time.sleep(30)


def executeEvents(configDict, csvFiles, iteration):
    """Function to execute events"""
    global FLAG
    print("Start reading csv files")
    csvEventList = []
    if csvFiles:
        for csv in csvFiles:
            print("reading csv files")
            EventList = event.readAllEventsFromCsv(csv)
            csvEventList = csvEventList + EventList

    print("Start executing events script.")
    event.sendEvent(configDict, csvEventList, iteration)
    time.sleep(60)
    print("Finish event script execution.")
    FLAG = True
    print("Making flag true to close tail command connection")
    return True


def closeClientConnection(sshclient):
    """Function to close ssh connection"""
    print("closing connection")
    client.closeConnection(sshclient)


def getLogData():
    """Return log data to show on dashboard"""
    # Read contents
    logData = readTxtFile()
    return logData


def downloadCSV(data):
    """Function to load first when script runs"""
    if data:
        # Generate csv from data
        generateCSV(data)
        return os.getcwd() + '/log.csv'
    else:
        return False


def copyFile(iteration):
    """copy file from remote to local"""
    print("Copy log file from remote to local server.")
    if not os.path.isfile(FILENAME):
        ssh = client.startConnection(CONFIG_DICT)
        # open sftp connection to copy file
        sftp = ssh.open_sftp()
        # copy file from remote to local dir
        try:
            sftp.get(REMOTE_FILE, LOCAL_FILE)
            sftp.close()
            client.closeConnection(ssh)
            return True
        except OSError:
            # delete inserted data
            models.rollBackAlldata(iteration)
            client.closeConnection(ssh)
            return False
    else:
        print("Failed to create log file.")
        return False


def readTxtFile():
    """Read log file and proccess data to get the contents from file"""
    PROCESSING_DATA_LIST = []

    if not os.path.isfile(FILENAME):
        print("Given file does not exist")
        return False

    with open(FILENAME) as file:
        status = True
        while status:
            line = file.readline()
            if line:
                processingLine = getLineForProcessing(line)

                if processingLine is not None:
                    data = getProcessingDetails(processingLine)
                    # write position of current pointer in a data
                    data['position'] = file.tell()
                    # add status list for proccess in the same dictionary
                    findData(data)
                    # append dictionary to the final list
                    PROCESSING_DATA_LIST.append(data)
            else:
                status = False
    file.close()
    return PROCESSING_DATA_LIST


def getLineForProcessing(line):
    """Function to get line which contains character 'Processing'"""
    pos = re.search('- Processing', line)
    infoPos = re.search(' INFO ', line)
    if pos and infoPos:
        return line


def getProcessingDetails(processingLine):
    """Function to get the processing details"""
    processingDetailsList = {}
    # split processing line to get all VM details
    details = processingLine.split('{')
    processingDetailsList['details'] = '{' + details[-1]

    # split to get datetime with miliseconds
    proccessingTime = processingLine.split('Z', 1)
    proccessingTimeDetails = proccessingTime[0].split(',')

    # append date time for task event proccessed
    processingDetailsList['proccessed_datetime'] = proccessingTimeDetails[0].strip() if \
        proccessingTimeDetails[0] else ''
    processingDetailsList['proccessed_ms'] = proccessingTimeDetails[1].strip() if \
        int(proccessingTimeDetails[1]) else 0

    # split processing line to get process details
    data = processingLine.split(',')

    # split other details on the basis of character ':'
    otherData = data[1].split(':')

    # get processing id from data
    if otherData[1]:
        dataForId = otherData[1].split('- Processing')
        processingDetailsList['id'] = ''.join([id for id in dataForId[1].strip() if id.isdigit()])
    if 'TaskEvent' not in otherData:
        processingDetailsList['event'] = otherData[2].strip() if otherData[2] else ''
    else:
        processingDetailsList['task'] = otherData[3].strip() if otherData[3] else ''

    return processingDetailsList


def findData(data):
    """ Function to find id in a contents and check status flow"""
    processStatus = ['Processing']
    delivered_datetime = ''
    queued_datetime = ''
    queued_milisecond = 0
    delivered_milisecond = 0
    with open(FILENAME) as file:
        file.seek(data['position'], 0)
        status = True
        while status:
            line = file.readline()
            if line:
                status = True
                pos = re.search(data['id'], line)
                if pos:
                    if re.search('Skipped', line):
                        processStatus.append('Skipped')
                    elif re.search('Queued', line):
                        # extract queue time
                        splitlist = line.split('Z', 1)
                        queueList = splitlist[0].split(',')
                        queued_datetime = queueList[0].strip() if queueList[0] else ''
                        queued_milisecond = int(queueList[1].strip()) if queueList[1] else 0
                        processStatus.append('Queued')
                    elif re.search('Delivered', line):
                        # extract delivered time
                        splitlist = line.split('Z', 1)
                        deliveredList = splitlist[0].split(',')
                        delivered_datetime = deliveredList[0].strip() if deliveredList[0] else ''
                        delivered_milisecond = int(deliveredList[1].strip()) if int(deliveredList[1]) else 0
                        processStatus.append('Delivered')
            else:
                status = False
    data['status_list'] = processStatus
    data['delivered_datetime'] = delivered_datetime
    data['queued_datetime'] = queued_datetime
    data['delivered_ms'] = delivered_milisecond
    data['queued_ms'] = queued_milisecond
    file.close()


def generateCSV(logData):
    """Generate csv from proccessed data"""
    dataForCsv = []

    if logData:
        for data in logData:
            dataDict = dict(
                LOG_ID=data[5],
                event=data[7],
                status=data[8],
                details=data[9],
                processed_datetime=data[13],
                delivered_datetime=data[14],
                queued_datetime=data[15]
            )
            dataForCsv.append(dataDict)

        # set the order of columns
        column_order = ['LOG_ID', 'event', 'details', 'status', 'processed_datetime',
                        'delivered_datetime', 'queued_datetime']
        df = pd.DataFrame(dataForCsv)
        df[column_order].to_csv('log.csv', index=False)
    print("Done. CSV Generated")
    return True


def deleteFile():
    read_config()
    filepath = os.getcwd() + '/log.txt'
    csvFilePath = os.getcwd() + '/log.csv'

    if os.path.isfile(filepath):
        os.remove(filepath)

    if os.path.isfile(csvFilePath):
        os.remove(csvFilePath)

    return True


def deleteCsvFiles():
    data = read_config()
    if data:
        for file in data[1]:
            if os.path.isfile(file):
                os.remove(file)
    return True


def checkLogFileExist():
    filepath = os.getcwd() + '/log.txt'
    if os.path.isfile(filepath):
        return True
    else:
        return False


def date_diff_in_Seconds(dt2, dt1):
    timedelta = dt2 - dt1
    return timedelta.days * 24 * 3600 + timedelta.seconds


def writeConfigFile(configDict, filename):
    f = open(CONFIG_FILE, 'w')
    f.write(json.dumps(configDict) + '\n')
    f.write(filename)
    f.close()


def executeAll(iteration=None):
    """Execute all threds"""
    # delete Log File
    deleteFile()
    # read config file
    data = read_config()

    if data:
        print("execute events..")
        result = generateLogTxtFile(json.loads(data[0]), data[1], iteration=iteration)
        time.sleep(40)
        if result:
            print("Validate data..")
            event.validateData(iteration=iteration)
            time.sleep(20)
            return True
        else:
            print("File not found. Failed to do validation.")
            return False
    else:
        return False


def read_config():
    # read config file
    with open(CONFIG_FILE) as fp:
        data = [json.loads(line.strip()) for line in fp]
    return data
