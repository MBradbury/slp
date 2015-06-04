#!/usr/bin/env python

from __future__ import print_function

import xml.dom.minidom
import sys, subprocess

if len(sys.argv) != 2:
    raise RuntimeError("Usage my-qstat-apocrita.py <username>")

username = sys.argv[1]

qstat_output = subprocess.check_output('qstat -xml -r', shell=True)

dom = xml.dom.minidom.parseString(qstat_output)

jobs = dom.getElementsByTagName('job_info')
run = jobs[0]

runjobs = run.getElementsByTagName('job_list')

def fakeqstat(joblist):
    for job in joblist:
        jobname = job.getElementsByTagName('JB_name')[0].childNodes[0].data
        jobown = job.getElementsByTagName('JB_owner')[0].childNodes[0].data
        jobstate = job.getElementsByTagName('state')[0].childNodes[0].data
        jobnum = job.getElementsByTagName('JB_job_number')[0].childNodes[0].data
        
        jobtime = 'not set'
        if jobstate == 'r' :
            jobtime = job.getElementsByTagName('JAT_start_time')[0].childNodes[0].data
        elif(jobstate == 'dt'):
            jobtime = job.getElementsByTagName('JAT_start_time')[0].childNodes[0].data
        else:
            jobtime = job.getElementsByTagName('JB_submission_time')[0].childNodes[0].data

        if username in jobown:
            print(jobnum, '\t', jobown.ljust(16), '\t', jobname.ljust(16), '\t', jobstate, '\t', jobtime)

fakeqstat(runjobs)
