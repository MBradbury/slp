from __future__ import division, print_function

import math
import subprocess

def name():
    return __name__

def kind():
    return "pbs"

def url():
    return "flux.dcs.warwick.ac.uk"

def ppn():
    return 12

# HT is disabled
def theads_per_processor():
    return 1

# 32GB per node
def ram_per_node():
    return (32 * 1024) / ppn()

def builder():
    from data.run.driver.cluster_builder import Runner as Builder
    return Builder()

def copy_to(dirname):
    username = raw_input("Enter your {} username: ".format(name().title()))
    subprocess.check_call("rsync -avz -e ssh cluster/__init__.py cluster/{2} {0}@{1}:~/slp-algorithms-tinyos/cluster".format(
        username, url(), dirname), shell=True)

def copy_file(results_directory_path, filename):
    username = raw_input("Enter your {} username: ".format(name().title()))
    subprocess.check_call("rsync -avz --rsync-path=\"mkdir -p ~/slp-algorithms-tinyos/{results_directory_path} && rsync\" -e ssh {results_directory_path}/{filename} {0}@{1}:~/slp-algorithms-tinyos/{results_directory_path}/{filename}".format(
        username, url(), results_directory_path=results_directory_path, filename=filename), shell=True)

def copy_back(dirname):
    username = raw_input("Enter your {} username: ".format(name().title()))
    subprocess.check_call("rsync -avz -e ssh {0}@{1}:~/slp-algorithms-tinyos/cluster/{2}/*.txt results/{2}".format(
        username, url(), dirname), shell=True)

def submitter(notify_emails=None):
    from data.run.driver.cluster_submitter import Runner as Submitter

    ram_for_os_mb = 4 * 1024

    jobs = ppn()
    ram_per_job_mb = int(math.floor(((ram_per_node() * ppn()) - ram_for_os_mb) / jobs))

    # The -h flags causes the jobs to be submitted as held. It will need to be released before it is run.
    # Don't provide a queue, as the job will be routed to the correct place.
    cluster_command = "qsub -j oe -h -l nodes=1:ppn={} -l walltime={{}} -l mem={}mb -N \"{{}}\"".format(
        ppn(), ppn() * ram_per_job_mb)

    if notify_emails is not None and len(notify_emails) > 0:
        print("Warning: flux does not currently have email notification setup")
        cluster_command += " -m ae -M {}".format(",".join(notify_emails))

    prepare_command = "cd $PBS_O_WORKDIR"

    return Submitter(cluster_command, prepare_command, jobs, job_repeats=1)

def array_submitter(notify_emails=None):
    from data.run.driver.cluster_submitter import Runner as Submitter

    # Hopefully enough ram for the larger jobs
    ram_per_job_mb = 2 * 1024
    num_jobs = 1
    num_array_jobs = ppn()

    # The -h flags causes the jobs to be submitted as held. It will need to be released before it is run.
    # Don't provide a queue, as the job will be routed to the correct place.
    cluster_command = "qsub -j oe -h -t 1-{}%1 -l nodes=1:ppn={} -l walltime={{}} -l mem={}mb -N \"{{}}\"".format(
        num_array_jobs, num_jobs, num_jobs * ram_per_job_mb)

    if notify_emails is not None and len(notify_emails) > 0:
        print("Warning: flux does not currently have email notification setup")
        cluster_command += " -m ae -M {}".format(",".join(notify_emails))

    prepare_command = "cd $PBS_O_WORKDIR"

    return Submitter(cluster_command, prepare_command, num_jobs, job_repeats=num_array_jobs, array_job_variable="$PBS_ARRAYID")
