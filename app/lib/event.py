#!/usr/bin/env python
"""
Script to read log and generate csv from log file
@author: Shilpa Nimje
"""
import csv
from app import models
from app.lib import proccesscsv
from app.lib.realEventGen import RealEventGen


# ===========================================================================
# EVENT MAPPING DICTIONARY
# ===========================================================================
EVENT_DICT = dict(
    PowerOffVm='VmPoweredOffEvent',
    PowerOnVm='VmPoweredOnEvent',
    RenameVm='VmRenamedEvent',
    RemoveVm='VmRemovedEvent',
    RelocateVm='VmMigratedEvent',
    CreateVm='VmCreatedEvent',
    CloneVm='VmClonedEvent',
    DeployVm='VmDeployedEvent',
    RegisterVm='VmRegisteredEvent',
    RenameDatacenter='DatacenterRenamedEvent',
    CreateDatastore='DatastoreCreatedEvent',
    RenameDatastore='DatastoreRenamedEvent',
    RemoveDatastore='DatastoreRemovedEvent',
    MigrateVm='VmMigratedEvent',
)


def readAllEventsFromCsv(csvFilePath):
    """Read Csv and save into list"""
    eventList = []
    with open(csvFilePath) as csv_file:
        next(csv_file)
        csv_reader = csv.reader(csv_file, delimiter=',')
        for row in csv_reader:
            eventList.append({'task_name': row[0], 'params': row[1]})
    return eventList


def sendEvent(configDict, eventList, iteration):
    """Send event and get return responce"""
    execution_flag = False
    for item in eventList:
        task = {'TaskName': item.get('task_name'), 'Parameters': item.get('params')}
        try:
            data = executeEvent(configDict, task)
            execution_flag = True
        except Exception as e:
            execution_flag = False
            data = ''
            print("Unable to send event to Vcenter. Error: " + str(e))

        if data:
            inputparams = dict(
                task_name=item.get('task_name'),
                params=item.get('params'),
                object_name=data.get('ObjectName', None),
                status=data.get('Status'),
                iteration=iteration,
            )

            saveData(inputparams)
    if execution_flag:
        if iteration == 1:
            # save iteration no in iterations table
            models.saveIterationsData()
        else:
            # update iteration no in iterations table
            models.updateIterationsData(iteration=iteration)
    return True


def executeEvent(configDict, task):
    """execute real event"""
    realEventGenObject = RealEventGen(
        host=configDict.get('vcenterIP'),
        user=configDict.get('vcenterUsername'),
        passwd=configDict.get('vcenterPassword'),
        port=443)

    return realEventGenObject.executeTask(task)


def saveData(inputparams):
    """save data"""
    models.saveEventStatusData(inputparams)


def validateData(iteration=None):
    """Function to validate csv with log file"""
    print("validation start......")
    data = models.getAllData(iteration)

    logData = proccesscsv.getLogData()

    finalList = []
    for item in data:
        for log in logData:
            if log.get('event'):
                # validate task name
                taskValidation = validateTaskName(item.csv_task_name, log.get('event'))
                if log.get('event') == 'DatacenterRenamedEvent':
                    # validate entitiy name
                    objectValidation = validateEntities(item.params, log.get('details'))
                else:
                    # validate object name
                    objectValidation = validateObject(item.object_name, log.get('details'))

                if taskValidation and objectValidation:
                    # append to the final list
                    finalList.append(log)
                    # update details in database
                    updateDetails(item.id, log)
                    # remove from final list
                    logData.remove(log)
                    break
    print("validation ends......")
    return finalList


def validateTaskName(csvTaskname, logTaskName):
    """validate task name and return True/False"""
    if EVENT_DICT[csvTaskname.strip()] == logTaskName.strip():
        return True
    else:
        return False


def validateObject(objectName, details):
    """validate object Name and return True/False"""
    result = details.find(objectName)
    if result != -1:
        return True
    else:
        return False


def validateEntities(params, details):
    """validate entieis and return True/False"""
    data = params.split("&")
    oldName = data[0].split('=')
    newName = data[1].split('=')

    res1 = details.find(oldName[1])
    res2 = details.find(newName[1])

    if res1 != -1 and res2 != -1:
        return True
    else:
        return False


def updateDetails(id, logData):
    """Update Details for existing added events"""
    if id and logData:
        models.updateEventData(id, logData)


def start_schedular():
    iteration_data = models.getIterationsData()

    # if 1st ietration is avilable in database then do execute incrementing 1st iteration
    if iteration_data:
        iteration = iteration_data[0][1] + 1
        print("-------------------Starting New Iteration-------------------")
        print("ITERATION: " + str(iteration))
        proccesscsv.executeAll(iteration)
        data = models.getAllData(iteration)
