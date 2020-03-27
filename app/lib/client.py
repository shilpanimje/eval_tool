#!/usr/bin/env python
"""
Script to create ssh connection and close ssh connection
@author: Shilpa Nimje
"""

import paramiko


def startConnection(configDict):
    '''
    CREATE SSH CONNECTION
    '''
    ssh = paramiko.client.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(configDict.get('mvaIP'), username=configDict.get('mvaUsername'), password=configDict.get('mvaPassword'))
    return ssh


def closeConnection(ssh):
    '''
    close ssh connection
    '''
    ssh.close()
