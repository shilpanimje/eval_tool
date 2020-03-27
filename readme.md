#Overview


##What is Eval Tool?
Eval Tool is python based web application which is used to generate real events on vcenter taking input as a csv file and vcenter credentials.

 

##How it will help us?
Eval Tool will help us to generate real events on vcenter without any manual efforts.



##Before Eval Tool scenario
Login to the Vcenter and generate events on specific VM or datastore or any cluster. Then to check the log of these generated events we need to go to the MVA log and check for these events whether generated events are in delivered state or queued state or in processing state. This whole process takes manual efforts and  is time consuming.

 

##After Eval Tool scenario
Eval tool will do all these steps for us and will show list of each events from logs with status.

 

#Prerequisites
pyvmomi
pandas
flask
flask_sqlalchemy
apscheduler
paramiko
virtualenv


#Installation Guide
You'll need Python 3.x and pip installed on your machine.

Don't know what pip is? Click here to check installation of pip.

 

Download the E-VAL Tool repository from here.

 

Install all required modules using command: pip install <package_name>


#List of Events Supported
	
RenameVm
PowerOnVm
PowerOffVm
RelocateVm
RenameDatacenter
CloneVm
DeployVm
RemoveVm
RenameDatastore
RemoveDatastore
RegisterVm

#Features of E-VAl Tool
Generate real events on vcenter.
Scheduler is one of the important feature which is used for long run. In scheduler you can provide start date, end date and interval. As per our requirement we can change interval, start date and end date.

#Input Data to generate real Events
You will need below input data for E-VAL Tool run

--Vcenter host IP, Vcenter username and Vcenter password
--MVA host from same Vcenter, MVA username and MVA password
--Mutiple csv file


#How to run E-VAL Tool
1.Steps to run E-VAL Tool

2.open putty session and login to MVA. Check custom-logs folder is available in /var/log folder
    Commands to check available files and folders 
    cd /var/log 
    ls

3.If custom-logs folder not available in folder /var/log then use below commands to create folder from root
    sudo chmod -R 777 /var/log
    cd /var/log
    sudo mkdir custom-logs
    sudo chmod -R 777 /var/log/custom-logs

4.close putty session

5.Open command prompt where you have E-VAL Tool Repository

6.Type below commands to start E-VAL Tool
    env\Scripts\activate
    python run.py

7.Copy host with port from command line and open in a browser. First page will load.

 
 CONFLUENCE PAGE: https://confluence.simplivt.local:8443/pages/viewpage.action?pageId=52404339