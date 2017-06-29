#!/usr/bin/env python
from __future__ import print_function

import os
import sys
import subprocess
import xml.dom.minidom

def fakeqstat(username, joblist):
    for job in joblist:
        job_id = job.getElementsByTagName('Job_Id')[0].childNodes[0].data
        job_name = job.getElementsByTagName('Job_Name')[0].childNodes[0].data
        job_state = job.getElementsByTagName('job_state')[0].childNodes[0].data

        job_owner = job.getElementsByTagName('Job_Owner')[0].childNodes[0].data

        if username in job_owner:
            print(job_id, job_state, job_name)

def main(username):
    qstat_output = subprocess.check_output('qstat -x', shell=True)

    dom = xml.dom.minidom.parseString(qstat_output)

    jobs = dom.getElementsByTagName('Job')

    fakeqstat(username, jobs)


if __name__ == '__main__':
    # The caller can specify a username if they wish,
    # or we can do the sensible thing and guess they want
    # to find info out about their own jobs
    try:
        username = sys.argv[1]
    except IndexError:
        username = os.environ['USER']

    main(username)
