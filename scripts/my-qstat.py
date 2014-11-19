#!/usr/bin/python
import xml.dom.minidom
import os
import sys
import string
#import re


f=os.popen('qstat -x')

dom=xml.dom.minidom.parse(f)

#data = dom.getElementsByTagName('Data')[0]

jobs = dom.getElementsByTagName('Job')


def fakeqstat(joblist):

        for r in joblist:

                #print(r)
                #print(dir(r))

                id = r.getElementsByTagName('Job_Id')[0].childNodes[0].data
                name = r.getElementsByTagName('Job_Name')[0].childNodes[0].data
                state = r.getElementsByTagName('job_state')[0].childNodes[0].data

                owner = r.getElementsByTagName('Job_Owner')[0].childNodes[0].data

                if 'bradbury' in owner:
                        print id, state, name                

                """jobname=r.getElementsByTagName('JB_name')[0].childNodes[0].data
                jobown=r.getElementsByTagName('JB_owner')[0].childNodes[0].data
                jobstate=r.getElementsByTagName('state')[0].childNodes[0].data
                jobnum=r.getElementsByTagName('JB_job_number')[0].childNodes[0].data
                jobtime='not set'
                if(jobstate=='r'):
                        jobtime=r.getElementsByTagName('JAT_start_time')[0].childNodes[0].data
                elif(jobstate=='dt'):
                        jobtime=r.getElementsByTagName('JAT_start_time')[0].childNodes[0].data
                else:
                        jobtime=r.getElementsByTagName('JB_submission_time')[0].childNodes[0].data



                print  jobnum, '\t', jobown.ljust(16), '\t', jobname.ljust(16),'\t', jobstate,'\t',jobtime
                """

fakeqstat(jobs)
