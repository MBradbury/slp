#!/usr/bin/env python

from __future__ import print_function

import xml.dom.minidom
import sys, subprocess

if len(sys.argv) != 2:
    raise RuntimeError("Usage {} <username>".format(sys.argv[0]))

username = sys.argv[1]

qstat_output = subprocess.check_output('qstat -x', shell=True)

dom = xml.dom.minidom.parseString(qstat_output)

jobs = dom.getElementsByTagName('Job')

def fakeqstat(joblist):
    for job in joblist:
        job_id = job.getElementsByTagName('Job_Id')[0].childNodes[0].data
        job_name = job.getElementsByTagName('Job_Name')[0].childNodes[0].data
        job_state = job.getElementsByTagName('job_state')[0].childNodes[0].data

        job_owner = job.getElementsByTagName('Job_Owner')[0].childNodes[0].data

        if username in job_owner:
            print(job_id, job_state, job_name)     

fakeqstat(jobs)
