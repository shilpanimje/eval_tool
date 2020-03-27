#!/usr/bin/env python
"""
Script to create ssh connection and close ssh connection
@author: Sanjog Naik and Shilpa Nimje
"""

import re
import sys
import argparse

import csv

import datetime
import ssl
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim
from pyVim.task import WaitForTask

import paramiko
from xml.etree import ElementTree

import sys
import subprocess


# objList = {}
failedTasks = []


def getParameters(Parameters):
    return dict(x.split('=') for x in Parameters.split('&'))


def getObjName(Obj):
    newObj = str(Obj).replace("'", '')
    objectName = str(newObj).split(':')[1]
    return objectName.strip()


def getObjViewList(Content, Type):
    objView = Content.viewManager.CreateContainerView(Content.rootFolder, [Type], True)
    objList = objView.view
    objView.Destroy()
    return objList


def getObjRef(Content, Type, Name):
    myObj = None
    objList = getObjViewList(Content, Type)

    for obj in objList:
        if obj.name == Name:
            myObj = obj
            break
    return myObj


def connectVcenter(Properties):
    context = None
    if hasattr(ssl, '_create_unverified_context'):
        context = ssl._create_unverified_context()
    si = SmartConnect(host=Properties['host'],
                      user=Properties['user'],
                      pwd=Properties['password'],
                      port=Properties['port'],
                      sslContext=context)
    if not si:
        print("Cannot connect to specified host using specified username and password")
        sys.exit()

    return si


# Establish SSH connection.
def ssh(IP, Cmd,
        Username='Administrator@vsphere.local',
        Password='svtrfs29L@B'):

    # Define the pre-command to run on an OVC
    pre_cmd = 'source /var/tmp/build/bin/appsetup'

    # Build the final command to ssh with
    ssh_cmd = '{}; {}'.format(pre_cmd, Cmd)

    # Create a new  paramiko ssh object
    ssh_client = paramiko.SSHClient()

    # Automatically accept/add SSH keys
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # Try (and catch) to do the SSH stuff
    try:
        # Create an ssh connection
        ssh_client.connect(IP, username=Username, password=Password)

        # SSH and save the output
        ssh_stdin, ssh_stdout, ssh_stderr = ssh_client.exec_command(ssh_cmd)
    except Exception as exception_message:
        # Received an exception
        print('! Exception during SSH: [{}]'.format(exception_message))

        sys.exit(0)

    # Return the "correct" command output.  By default, return ssh_stdout, but
    # if ssh_stderr exists, then return that one instead of ssh_stdout.
    return_output = ssh_stdout.read()       # Read ssh_stdout, set as default
    ssh_stderr_read = ssh_stderr.read()     # Read ssh_stderr output
    if (ssh_stderr_read):                   # Check for ssh_stderr output
        # There is ssh_stderror output, so we will use it for the return value
        return_output = ssh_stderr_read

    return return_output


# Get the XML output of any svt command
def getSvtShowXml(ip, cmd):
    # Run the command and get the output
    cmd = '{} --output xml --timeout 1200'.format(cmd)
    xml = ssh(ip, cmd)

    return xml


def updateFailedTaskList(Task, Params, Msg, OpStatus):
    failedTask = {}
    failedTask['task'] = Task
    failedTask['params'] = Params
    failedTask['msg'] = Msg
    failedTasks.append(failedTask)
    OpStatus['Status'] = 'Failed'
    OpStatus['Msg'] = Msg


def renameFn(Properties, Type):
    task = Properties['task']
    params = getParameters(task['Parameters'])
    opStatus = {}

    # ===========================================================================
    # Connect to Vcenter
    # ===========================================================================
    si = connectVcenter(Properties)

    obj = getObjRef(si.content, Type, params['OldName'])
    if obj is None:
        msg = "A object named " + params['OldName'] + " could not be found"
        updateFailedTaskList(task['TaskName'], params, msg, opStatus)

    else:
        print(" Current name : %s" % obj.name)
        print(" Renaming from %s to %s..." % (obj.name, params['NewName']))

        try:
            WaitForTask(obj.Rename(params['NewName']))
            print(" Rename successful")
            opStatus['ObjectName'] = getObjName(obj)
            opStatus['Status'] = 'Passed'

        except Exception as e:
            updateFailedTaskList(task['TaskName'], params, e.msg, opStatus)

    # ===========================================================================
    # Disconnect Vcenter
    # ===========================================================================
    Disconnect(si)

    return opStatus


def RenameDatacenterFn(Properties):
    return renameFn(Properties, vim.Datacenter)


def RemoveDatastoreFn(Properties):
    task = Properties['task']
    params = getParameters(task['Parameters'])
    opStatus = {}

    # Extract values
    ovcIp = params['ovc']
    name = params['Name']

    # ===========================================================================
    # Connect to Vcenter
    # ===========================================================================
    si = connectVcenter(Properties)
    obj = getObjRef(si.content, vim.Datastore, params['Name'])

    if obj is None:
        msg = "A object named " + params['Name'] + " could not be found"
        updateFailedTaskList(task['TaskName'], params, msg, opStatus)
    else:
        try:
            # remove ate the datastores
            print('removing Datastores...')
            cmd = ('svt-datastore-delete'
                   ' --name {} --force'.format(name))

            # Execute the command
            print('Running this command: {}'.format(cmd))
            ssh_output = ssh(ovcIp, cmd)
            print(ssh_output)

        except Exception as e:
            print(" Exception--- %s" % e.msg)
            updateFailedTaskList(task['TaskName'], params, e.msg, opStatus)

    # ===========================================================================
    # Disconnect Vcenter
    # ===========================================================================
    Disconnect(si)

    return opStatus


def CreateDatastoreFn(Properties):
    task = Properties['task']
    params = getParameters(task['Parameters'])
    opStatus = {}

    # Extract values
    ovcIp = params['ovc']
    name = params['Name']
    policy = params['Policy']
    size = params['Size']
    datacenter = params['Datacenter']
    cluster = params['Cluster']

    # ===========================================================================
    # Connect to Vcenter
    # ===========================================================================
    si = connectVcenter(Properties)
    obj = getObjRef(si.content, vim.Datastore, name)
    # ===========================================================================
    # Disconnect Vcenter
    # ===========================================================================
    Disconnect(si)
    if obj is not None:
        msg = "A object named " + name + " already exists"
        updateFailedTaskList(task['TaskName'], params, msg, opStatus)
        return opStatus

    # Create the datastores
    print('Creating Datastores...')
    cmd = ('svt-datastore-create'
           ' --name {}'
           ' --policy {}'
           ' --size {}'
           ' --datacenter "{}"'
           ' --cluster "{}"'
           ' --timeout 1200'.format(name,
                        policy,
                        size,
                        datacenter,
                        cluster))

    # Execute the command
    print('Running this command: {}'.format(cmd))
    ssh_output = ssh(ovcIp, cmd)
    print(ssh_output)

    # ===========================================================================
    # Connect to Vcenter
    # ===========================================================================
    si = connectVcenter(Properties)
    obj = getObjRef(si.content, vim.Datastore, name)
    # ===========================================================================
    # Disconnect Vcenter
    # ===========================================================================
    Disconnect(si)
    if obj is not None:
        opStatus['ObjectName'] = getObjName(obj)
        opStatus['Status'] = 'Passed'
    else:
        msg = "A object named " + name + " doesn't exist"
        updateFailedTaskList(task['TaskName'], params, msg, opStatus)
    return opStatus


def RenameDatastoreFn(Properties):
    return renameFn(Properties, vim.Datastore)


def AddHostFn(Properties):
    return None


def RemoveHostFn(Properties):
    return None


def MigrateVmFn(Properties):
    return None


def MigrateDrsVmFn(Properties):
    return None


def RelocateVmFn(Properties):
    task = Properties['task']
    params = getParameters(task['Parameters'])
    opStatus = {}

    # ===========================================================================
    # Connect to Vcenter
    # ===========================================================================
    si = connectVcenter(Properties)
    obj = getObjRef(si.content, vim.VirtualMachine, params['VmName'])
    if obj is None:
        msg = "A object named " + params['VmName'] + " could not be found"
        print(msg)
        updateFailedTaskList(task['TaskName'], params, msg, opStatus)
    else:
        Flag=True
        while Flag:
            Flag=False
            try:
                if ('Host' in params) and ('Datastore' in params):
                    Hostobj = getObjRef(si.content, vim.HostSystem, params['Host'])
                    DSobj = getObjRef(si.content, vim.Datastore, params['Datastore'])

                    if (Hostobj is None) or (DSobj is None):
                        msg = "A object named " + params['Host'] + " or " + params['Datastore'] + " could not be found"
                        print(msg)
                        updateFailedTaskList(task['TaskName'], params, msg, opStatus)
                        break

                    print(" Relocating VM %s to %s, %s..." % (obj.name, params['Host'], params['Datastore']))
                    relocate_spec = vim.vm.RelocateSpec(host=Hostobj, datastore=DSobj)
                    WaitForTask(obj.Relocate(relocate_spec))
                    print(" Relocation successful")
                    opStatus['ObjectName'] = getObjName(obj)
                    opStatus['Status'] = 'Passed'
                else:
                    msg = "Incomplete parameter specified. Need either host or datastore information to relocate VM"
                    updateFailedTaskList(task['TaskName'], params, msg, opStatus)

            except Exception as e:
                msg = "Failed to relocate VM"
                updateFailedTaskList(task['TaskName'], params, msg, opStatus)

    # ===========================================================================
    # Disconnect Vcenter
    # ===========================================================================
    Disconnect(si)
    return opStatus


# def create_dummy_vm(Properties,name, service_instance, vm_folder, resource_pool, datastore):
#     task = Properties['task']
#     params = getParameters(task['Parameters'])
#     opStatus = {}
#     nic_type = 'E1000'
#     vm_name = params['VmName']
#     net_name = params['Network']
#     datastore = params['Datastore']
#     datastore_path = '[' + datastore + '] ' + vm_name
#     devices = []
#
#     vmx_file = vim.vm.FileInfo(logDirectory=None,
#                                snapshotDirectory=None,
#                                suspendDirectory=None,
#                                vmPathName=datastore_path)
#
#     config = vim.vm.ConfigSpec(name=vm_name, memoryMB=1024, numCPUs=1,
#                                files=vmx_file, guestId='rhel6_64Guest',
#                                version='vmx-09', deviceChange=devices)
#
#     print("Creating VM %s" % (vm_name))
#     task = vm_folder.CreateVM_Task(config=config, pool=resource_pool)
#     tasks.wait_for_tasks(service_instance, [task])


def CreateVmFn(Properties):
    task = Properties['task']
    params = getParameters(task['Parameters'])
    opStatus = {}

    name = params['VmName']
    network = params['Network']
    datastore = params['Datastore']
    host = params['Host']
    ova = params['Ova']

    # ===========================================================================
    # Connect to Vcenter
    # ===========================================================================
    si = connectVcenter(Properties)
    obj = getObjRef(si.content, vim.VirtualMachine, name)
    # ===========================================================================
    # Disconnect Vcenter
    # ===========================================================================
    Disconnect(si)
    if obj is not None:
        msg = "A object named " + name + " already exists"
        updateFailedTaskList(task['TaskName'], params, msg, opStatus)
        return opStatus

    # Generate the command
    cmd = ['ovftool',
           '--machineOutput',
           '--noSSLVerify',
           '--name={}'.format(name),
           '--network={}'.format(network),
           '--datastore={}'.format(datastore),
           ova,
           'vi://{}:{}@{}?ip={}'.format(Properties['user'],
                                        Properties['password'],
                                        Properties['host'],
                                        host)]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)

    for line in iter(proc.stdout.readline, b''):
        print(line.rstrip())

    print("VM Created")

    # ===========================================================================
    # Connect to Vcenter
    # ===========================================================================
    si = connectVcenter(Properties)
    obj = getObjRef(si.content, vim.VirtualMachine, name)
    # ===========================================================================
    # Disconnect Vcenter
    # ===========================================================================
    Disconnect(si)
    if obj is not None:
        opStatus['ObjectName'] = getObjName(obj)
        opStatus['Status'] = 'Passed'
    else:
        msg = "A object named " + name + " doesn't exist"
        updateFailedTaskList(task['TaskName'], params, msg, opStatus)
    return opStatus


def CloneVmFn(Properties):
    task = Properties['task']
    params = getParameters(task['Parameters'])
    opStatus = {}

    # ===========================================================================
    # Connect to Vcenter
    # ===========================================================================
    si = connectVcenter(Properties)
    obj = getObjRef(si.content, vim.VirtualMachine, params['SourceVm'])
    destination_host = getObjRef(si.content, vim.HostSystem, params['Host'])
    dc = getObjRef(si.content, vim.Datacenter, params['Datacenter'])

    if obj is None:
        msg = "A object named " + params['SourceVm'] + " could not be found"
        updateFailedTaskList(task['TaskName'], params, msg, opStatus)

    elif destination_host is None:
        msg = "A object named " + params['Host'] + " could not be found"
        updateFailedTaskList(task['TaskName'], params, msg, opStatus)

    elif dc is None:
        msg = "A object named " + params['Datacenter'] + " could not be found"
        updateFailedTaskList(task['TaskName'], params, msg, opStatus)

    else:
        try:
            print(" Cloning the VM %s" % obj.name)
            rs = vim.VirtualMachineRelocateSpec()
            cs = vim.VirtualMachineCloneSpec()
            target_folder = dc.vmFolder

            rs.host = destination_host
            cs.location = rs
            cs.powerOn = False
            print ("Clone initiated...")
            WaitForTask(obj.CloneVM_Task(target_folder, params['VmName'], cs))
            print(" Virtual Machine %s has been cloned successfully" % params['VmName'])

            opStatus['ObjectName'] = getObjName(obj)
            opStatus['Status'] = 'Passed'

        except Exception as e:
            msg = "Failed to clone VM"
            updateFailedTaskList(task['TaskName'], params, msg, opStatus)
    # ===========================================================================
    # Disconnect Vcenter
    # ===========================================================================
    Disconnect(si)

    return opStatus


def DeployVmFn(Properties):
    task = Properties['task']
    params = getParameters(task['Parameters'])
    opStatus = {}

    # ===========================================================================
    # Connect to Vcenter
    # ===========================================================================
    si = connectVcenter(Properties)

    obj = getObjRef(si.content, vim.VirtualMachine, params['Template'])

    destination_host = getObjRef(si.content, vim.HostSystem, params['Host'])
    dc = getObjRef(si.content, vim.Datacenter, params['Datacenter'])
    cluster = getObjRef(si.content, vim.ClusterComputeResource, params['Cluster'])

    if obj is None:
        msg = "A object named " + params['Template'] + " could not be found"
        updateFailedTaskList(task['TaskName'], params, msg, opStatus)

    elif destination_host is None:
        msg = "A object named " + params['Host'] + " could not be found"
        updateFailedTaskList(task['TaskName'], params, msg, opStatus)

    elif dc is None:
        msg = "A object named " + params['Datacenter'] + " could not be found"
        updateFailedTaskList(task['TaskName'], params, msg, opStatus)

    elif cluster is None:
        msg = "A object named " + params['Cluster'] + " could not be found"
        updateFailedTaskList(task['TaskName'], params, msg, opStatus)

    else:
        try:
            print(" Deploying the VM %s" % obj.name)
            rs = vim.VirtualMachineRelocateSpec()
            cs = vim.VirtualMachineCloneSpec()
            target_folder = dc.vmFolder
            rs.host = destination_host
            rs.pool = cluster.resourcePool
            cs.location = rs
            cs.powerOn = False
            print ("Deploy initiated...")
            WaitForTask(obj.CloneVM_Task(target_folder, params['VmName'], cs))
            print(" Virtual Machine %s has been Deployed successfully" % params['VmName'])

            opStatus['ObjectName'] = getObjName(obj)
            opStatus['Status'] = 'Passed'

        except Exception as e:
            updateFailedTaskList(task['TaskName'], params, e.msg, opStatus)
    # ===========================================================================
    # Disconnect Vcenter
    # ===========================================================================
    Disconnect(si)

    return opStatus


def RegisterVmFn(Properties):
    task = Properties['task']
    params = getParameters(task['Parameters'])
    opStatus = {}

    # ===========================================================================
    # Connect to Vcenter
    # ===========================================================================
    si = connectVcenter(Properties)

    cluster = getObjRef(si.content, vim.ClusterComputeResource, params['Cluster'])
    dc = getObjRef(si.content, vim.Datacenter, params['Datacenter'])
    ds = getObjRef(si.content, vim.Datastore, params['Datastore'])

    if dc is None:
        msg = "A object named " + params['Datacenter'] + " could not be found"
        updateFailedTaskList(task['TaskName'], params, msg, opStatus)

    elif cluster is None:
        msg = "A object named " + params['Cluster'] + " could not be found"
        updateFailedTaskList(task['TaskName'], params, msg, opStatus)

    elif ds is None:
        msg = "A object named " + params['Datastore'] + " could not be found"
        updateFailedTaskList(task['TaskName'], params, msg, opStatus)

    else:
        try:
            print(" Registering the VM %s" % params['VmName'])
            str = ('[{}]{}/{}.vmx'.format(params['Datastore'],params['VmName'],params['VmName']))
            print("Register initiated....")
            WaitForTask(dc.vmFolder.RegisterVM_Task( str, asTemplate=False, pool=cluster.resourcePool))
            print(" Virtual Machine %s has been registered successfully" % params['VmName'])

            # opStatus['ObjectName'] = getObjName(obj)
            opStatus['Status'] = 'Passed'

        except Exception as e:
            updateFailedTaskList(task['TaskName'], params, e.msg, opStatus)
    # ===========================================================================
    # Disconnect Vcenter
    # ===========================================================================
    Disconnect(si)

    return opStatus


def PowerOnVmFn(Properties):
    task = Properties['task']
    params = getParameters(task['Parameters'])
    opStatus = {}

    # ===========================================================================
    # Connect to Vcenter
    # ===========================================================================
    si = connectVcenter(Properties)

    obj = getObjRef(si.content, vim.VirtualMachine, params['VmName'])
    if obj is None:
        msg = "A object named " + params['VmName'] + " could not be found"
        updateFailedTaskList(task['TaskName'], params, msg, opStatus)

    else:
        print(" Powering on the VM %s" % obj.name)


        try:
            WaitForTask(obj.PowerOn())
            print(" PowerOnVm successful")
            opStatus['ObjectName'] = getObjName(obj)
            opStatus['Status'] = 'Passed'

        except Exception as e:
            updateFailedTaskList(task['TaskName'], params, e.msg, opStatus)

    # ===========================================================================
    # Disconnect Vcenter
    # ===========================================================================
    Disconnect(si)

    return opStatus


def PowerOnDrsVmFn(Properties):
    return None


def PowerOffVmFn(Properties):
    task = Properties['task']
    params = getParameters(task['Parameters'])
    opStatus = {}

    # ===========================================================================
    # Connect to Vcenter
    # ===========================================================================
    si = connectVcenter(Properties)

    obj = getObjRef(si.content, vim.VirtualMachine, params['VmName'])
    if obj is None:
        msg = "A object named " + params['VmName'] + " could not be found"
        updateFailedTaskList(task['TaskName'], params, msg, opStatus)

    else:
        print(" Powering off the VM %s" % obj.name)


        try:
            WaitForTask(obj.PowerOff())
            print(" PowerOffVm successful")
            opStatus['ObjectName'] = getObjName(obj)
            opStatus['Status'] = 'Passed'
        except Exception as e:
            updateFailedTaskList(task['TaskName'], params, e.msg, opStatus)

    # ===========================================================================
    # Disconnect Vcenter
    # ===========================================================================
    Disconnect(si)

    return opStatus


def RemoveVmFn(Properties):
    task = Properties['task']
    params = getParameters(task['Parameters'])
    opStatus = {}

    # ===========================================================================
    # Connect to Vcenter
    # ===========================================================================
    si = connectVcenter(Properties)
    obj = getObjRef(si.content, vim.VirtualMachine, params['VmName'])
    if obj is None:
        msg = "A object named " + params['VmName'] + " could not be found"
        updateFailedTaskList(task['TaskName'], params, msg, opStatus)
    else:
        try:
            if obj.runtime.powerState == vim.VirtualMachinePowerState.poweredOn:
                print(" Powering off the VM %s" % obj.name)
                WaitForTask(obj.PowerOff())
                print(" PowerOffVm successful")
            print(" Removing the VM %s" % obj.name)
            WaitForTask(obj.Destroy_Task())
            print(" RemoveVm successful")

            opStatus['ObjectName'] = getObjName(obj)
            opStatus['Status'] = 'Passed'

        except Exception as e:
            print(" Exception--- %s" % e.msg)
            updateFailedTaskList(task['TaskName'], params, e.msg, opStatus)

    # ===========================================================================
    # Disconnect Vcenter
    # ===========================================================================
    Disconnect(si)

    return opStatus


def RenameVmFn(Properties):
    return renameFn(Properties, vim.VirtualMachine)


def ReconfigureClusterFn(Properties):
    return None


def DisableDrsFn(Properties):
    return None


def EnableDrsFn(Properties):
    return None


def RenameDatacenterDescription():
    msg= '''Task : RenameDatacenter
        OldName : Existing name of Datacenter
        NewName : New name of Datacenter'''
    return(msg)


def CreateDatastoreDescription():
    msg = '''Task : CreateDatastore
        Name       : Name of the Datastore
        Policy     : Policy Name
        Size       : Size of datastore in bytes
        Datacenter : Datacenter Name
        Cluster    : Cluster Name'''
    return(msg)

def RenameDatastoreDescription():
    msg= '''Task : RenameDatastore
        OldName : Existing name of Datastore
        NewName : New name of Datastore'''
    return(msg)

def AddHostDescription():
    return "\r\nIn AddHostDescription"

def MigrateVmDescription():
    return "\r\nIn MigrateVmDescription"

def VmMigratedDescription():
    return "\r\nIn VmMigratedDescription"

def MigrateDrsDescription():
    return "\r\nIn MigrateDrsDescription"


def RelocateVmDescription():
    msg='''Task : Relocate VM
        VmName : Name of the VM which needs to be relocated
        Host   : Destination Host where VM needs to be relocated'''
    return(msg)


def VmRelocatedDescription():
    return "\r\nIn VmRelocatedDescription"


def VmMigratedacrossHMSDescription():
    return "\r\nIn VmMigratedacrossHMSDescription"


def CreateVmDescription():
    return "\r\nIn CreateVmDescription"


def CloneVmDescription():
    msg='''Task : Clone VM
        VmName      : Name of the new VM created
        SourceVm    : Name of the VM which needs to be cloned
        Host        : Host where new VM has to be created
        Datancenter : Datacenter where new VM has to be created'''
    return(msg)


def DeployVmDescription():
    msg ='''Task : Deploy VM
    VmName        : Name of the deployed VM(New VM)
    Template      : Name of VM Template
    Cluster       : Name of the Cluster where VM needs to be deployed
    Datacenter    : Name of the Datacenter where VM needs to be deployed
    Host          : Host where VM needs to be deployed'''
    return(msg)


def RegisterVmDescription():
    msg ='''Task : Register VM
    VmName        : Name of the deployed VM(New VM)
    Cluster       : Name of the Cluster where VM needs to be deployed
    Datacenter    : Name of the Datacenter where VM needs to be deployed
    Datastore     : Datastore where unregistered VM is present'''
    return(msg)


def PowerOnVmDescription():
    msg = '''Task : Power ON VM
        VM Name : Name of the VM which needs to be powered ON'''
    return(msg)


def PowerOffVmDescription():
    msg = '''Task : Power OFF VM
        VM Name : Name of the VM which needs to be powered OFF'''
    return(msg)


def RemoveVmDescription():
    msg= '''Task   : Remove VM
        VmName :  Name of the VM which needs to be removed'''
    return(msg)


def RenameVmDescription():
    msg ='''Task : Rename VM
        OldName : Existing name of VM
        NewName : New name of VM'''
    return(msg)

def ReconfigureClusterDescription():
    return "\r\nIn ReconfigureClusterDescription"

def DisbleDrsDescription():
    return "\r\nIn DisbleDrsDescription"

def EnableDrsDescription():
    return "\r\nIn EnableDrsDescription"

def TaskDescription():
    return "\r\nIn TaskDescription"

def ChangeCustomFieldValueDescription():
    return "\r\nIn ChangeCustomFieldValueDescription"


SupportedTasksList = { "RenameDatacenter": [RenameDatacenterFn, RenameDatacenterDescription],
              "CreateDatastore": [CreateDatastoreFn, CreateDatastoreDescription],
              "RenameDatastore": [RenameDatastoreFn, RenameDatastoreDescription],
              "RemoveDatastore": [RemoveDatastoreFn, ''],
              # "AddHost": [AddHostFn, AddHostDescription],
              # "RemoveHost": [RemoveHostFn, RemoveHostDescription],
              "MigrateVm": [MigrateVmFn, MigrateVmDescription],
              # #"VmMigrated": [VmMigratedFn, VmMigratedDescription],
              # "MigrateDrsVm": [MigrateDrsVmFn, MigrateDrsVmDescription],
              "RelocateVm": [RelocateVmFn, RelocateVmDescription],
              # #"VmRelocated": [VmRelocatedFn, VmRelocatedDescription],
              # #"VmMigratedAccrossHMS": [VmMigratedAccrossHMSFn, VmMigratedAccrossHMSDescription],
              "CreateVm": [CreateVmFn, CreateVmDescription],                                      # Only supported on DVM because of dependency on Ovftool
              "CloneVm": [CloneVmFn, CloneVmDescription],
              "DeployVm": [DeployVmFn, DeployVmDescription],
              "RegisterVm": [RegisterVmFn, RegisterVmDescription],
              "PowerOnVm": [PowerOnVmFn, PowerOnVmDescription],
              # "PowerOnDrsVm": [PowerOnDrsVmFn, PowerOnDrsVmDescription],
              "PowerOffVm" : [PowerOffVmFn, PowerOffVmDescription],
              "RemoveVm": [RemoveVmFn, RemoveVmDescription],
              "RenameVm": [RenameVmFn, RenameVmDescription],
              # "ReconfigureCluster": [ReconfigureClusterFn, ReconfigureClusterDescription],
              # "DisableDrs": [DisableDrsFn, DisableDrsDescription],
              # "EnableDrs": "[EnableDrsFn, EnableDrsDescription],
              # #"Task": [TaskFn, TaskDescription],
              # "ChangeCustomFieldValue": [ChangeCustomFieldValueFn, ChangeCustomFieldValueDescription],
              }

'''
def ExecuteTask(Properties):
    task = Properties['task']
    print("\n\nExecuting Task : %s" % task['TaskName'])
    SupportedTasksList[task['TaskName']][0](Properties)
'''

'''
def main():
    properties = {}

    args = GetArgs()

    # ===========================================================================
    # Read all tasks from the given csv file
    # ===========================================================================
    if not len(args.file):
        print("No file specified")
        sys.exit()

    tasksList = readTasksFile(args.file)
    if not tasksList:
        print("No tasks specified in file")
        sys.exit()

    properties['host'] = args.host
    properties['user'] = args.user
    properties['password'] = args.password
    properties['port'] = args.port

    # ===========================================================================
    # Post sequential events
    # ===========================================================================
    for task in tasksList:
        properties['task'] = task
        ExecuteTask(properties)

    print("\n%s" % ('*' * 90))
    print("\nExecution completed\n Failed Tasks : %d" % len(failedTasks))
    print("\n%s" % ('*' * 90))
    for t in failedTasks:
        print("\n Task : ", t['task'])
        print(" Parameters : ", t['params'])
        print(" Description : %s\n" % t['msg'])

    if len(failedTasks) != 0:
        print("\n%s" % ('*' * 90))
'''


# Establish SSH connection.
def ssh(IP, Cmd,
        Username='Administrator@vsphere.local',
        Password='svtrfs29L@B'):

    # Define the pre-command to run on an OVC
    pre_cmd = 'source /var/tmp/build/bin/appsetup'

    # Build the final command to ssh with
    ssh_cmd = '{}; {}'.format(pre_cmd, Cmd)

    # Create a new  paramiko ssh object
    ssh_client = paramiko.SSHClient()

    # Automatically accept/add SSH keys
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # Try (and catch) to do the SSH stuff
    try:
        # Create an ssh connection
        ssh_client.connect(IP, username=Username, password=Password)

        # SSH and save the output
        ssh_stdin, ssh_stdout, ssh_stderr = ssh_client.exec_command(ssh_cmd)
    except Exception as exception_message:
        # Received an exception
        print('! Exception during SSH: [{}]'.format(exception_message))

        sys.exit(0)

    # Return the "correct" command output.  By default, return ssh_stdout, but
    # if ssh_stderr exists, then return that one instead of ssh_stdout.
    return_output = ssh_stdout.read()       # Read ssh_stdout, set as default
    ssh_stderr_read = ssh_stderr.read()     # Read ssh_stderr output
    if (ssh_stderr_read):                   # Check for ssh_stderr output
        # There is ssh_stderror output, so we will use it for the return value
        return_output = ssh_stderr_read

    return return_output


class RealEventGen():
    def __init__(self, host, user, passwd, port):
        self.properties = {}
        self.properties['host'] = host
        self.properties['user'] = user
        self.properties['password'] = passwd
        self.properties['port'] = port

    def executeTask(self, task):
        self.properties['task'] = task
        print("\n\nExecuting Task : %s" % task['TaskName'])
        return SupportedTasksList[task['TaskName']][0](self.properties)
