#!/usr/bin/python
import xml.dom.minidom
import os, sys, string

if len(sys.argv) != 2:
        raise RuntimeError("Usage my-qstat.py <username>")

username = sys.argv[1]


f = os.popen('qstat -x')

dom=xml.dom.minidom.parse(f)

jobs = dom.getElementsByTagName('Job')

def fakeqstat(joblist):
        for r in joblist:
                id = r.getElementsByTagName('Job_Id')[0].childNodes[0].data
                name = r.getElementsByTagName('Job_Name')[0].childNodes[0].data
                state = r.getElementsByTagName('job_state')[0].childNodes[0].data

                owner = r.getElementsByTagName('Job_Owner')[0].childNodes[0].data

                if username in owner:
                        print id, state, name                

fakeqstat(jobs)
