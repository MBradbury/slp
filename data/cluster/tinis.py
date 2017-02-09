from __future__ import division

import os
import math
import subprocess

def name():
    return __name__

def kind():
    return "pbs"

def url():
    return "tinis.csc.warwick.ac.uk"

def ppn():
    return 16

def threads_per_processor():
    return 1

# 64GB per node
def ram_per_node():
    return (64 * 1024) / ppn()

def builder():
    from data.run.driver.cluster_builder import Runner as Builder
    return Builder()

def copy_to(dirname):
    username = raw_input("Enter your {} username: ".format(name().title()))
    subprocess.check_call("rsync -avz -e \"ssh -i {0}/.ssh/id_rsa\" cluster/__init__.py cluster/{3} {1}@{2}:~/slp-algorithms-tinyos/cluster".format(
        os.environ['HOME'], username, url(), dirname), shell=True)

def copy_file(results_directory_path, filename):
    username = raw_input("Enter your {} username: ".format(name().title()))
    subprocess.check_call("rsync -avz --rsync-path=\"mkdir -p ~/slp-algorithms-tinyos/{results_directory_path} && rsync\" -e ssh {results_directory_path}/{filename} {0}@{1}:~/slp-algorithms-tinyos/{results_directory_path}/{filename}".format(
        username, url(), results_directory_path=results_directory_path, filename=filename), shell=True)

def copy_back(dirname):
    username = raw_input("Enter your {} username: ".format(name().title()))
    subprocess.check_call("rsync -avz -e \"ssh -i {0}/.ssh/id_rsa\" {1}@{2}:~/slp-algorithms-tinyos/cluster/{3}/*.txt results/{3}".format(
        os.environ['HOME'], username, url(), dirname), shell=True)

def submitter(notify_emails=None):
    from data.run.driver.cluster_submitter import Runner as Submitter

    ram_for_os_mb = 3 * 1024

    jobs = ppn()
    ram_per_job_mb = int(math.floor(((ram_per_node() * ppn()) - ram_for_os_mb) / jobs))

    cluster_command = "msub -j oe -h -q cnode -l nodes=1:ppn={} -l walltime={{}} -l mem={}mb -N \"{{}}\"".format(
        ppn(), ppn() * ram_per_job_mb)

    if notify_emails is not None and len(notify_emails) > 0:
        cluster_command += " -m ae -M {}".format(",".join(notify_emails))

    prepare_command = ""

    return Submitter(cluster_command, prepare_command, jobs, job_repeats=1)
