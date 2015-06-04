from __future__ import division

import math, subprocess

def name():
    return __name__

def url():
    return "frontend1.apocrita.hpc.qmul.ac.uk"

def ppn():
    return 12

def theads_per_processor():
    return 4

def ram_per_node():
    return 2 * 1024

def builder():
    from data.run.driver.cluster_builder import Runner as Builder
    return Builder()

def copy_to():
    username = raw_input("Enter your {} username: ".format(name().title()))
    subprocess.check_call("rsync -avz -e ssh --delete cluster {0}@{1}:~/slp-algorithm-tinyos".format(
        username, url()), shell=True)

def copy_back(dirname):
    username = raw_input("Enter your {} username: ".format(name().title()))
    subprocess.check_call("rsync -avz -e ssh {0}@{1}:~/slp-algorithm-tinyos/cluster/{2}/*.txt results/{2}".format(
        username, url(), dirname), shell=True)

def submitter():
    from data.run.driver.cluster_submitter import Runner as Submitter

    ram_for_os_mb = 1024
    ram_per_job_mb = math.floor(ram_per_node() - (ram_for_os_mb / ppn()))

    cluster_command = "qsub -cwd -V -j yes -S /bin/bash -pe smp {} -l h_rt=24:00:00 -l h_vmem={}M -N \"{{}}\"".format(ppn(), ram_per_job_mb)

    #module_commands = "module load java/oracle/1.7.0_65 ; module load python2.7.8"

    prepare_command = ". sci/bin/activate ; cd slp-algorithm-tinyos"

    # There is only 24GB available and there are 48 threads that can be used for execution.
    # There is no way that all the TOSSIM instances will not run over the memory limit!
    # So lets use every node, but only 2 threads per node
    threads_to_use = 2

    return Submitter(cluster_command, prepare_command, ppn() * threads_to_use)
