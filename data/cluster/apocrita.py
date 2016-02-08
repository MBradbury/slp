from __future__ import division

import math, subprocess

def name():
    return __name__

def kind():
    return "sge"

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
    subprocess.check_call("rsync -avz -e ssh cluster {0}@{1}:~/slp-algorithms-tinyos".format(
        username, url()), shell=True)

def copy_result_summary(results_directory_path, filename):
    username = raw_input("Enter your {} username: ".format(name().title()))
    subprocess.check_call("rsync -avz --rsync-path=\"mkdir -p ~/slp-algorithms-tinyos/{results_directory_path} && rsync\" -e ssh {results_directory_path}/{filename} {0}@{1}:~/slp-algorithms-tinyos/{results_directory_path}/{filename}".format(
        username, url(), results_directory_path=results_directory_path, filename=filename), shell=True)

def copy_back(dirname):
    username = raw_input("Enter your {} username: ".format(name().title()))
    subprocess.check_call("rsync -avz -e ssh {0}@{1}:~/slp-algorithms-tinyos/cluster/{2}/*.txt results/{2}".format(
        username, url(), dirname), shell=True)

def submitter(notify_emails=None):
    from data.run.driver.cluster_submitter import Runner as Submitter

    # There is only 24GB available and there are 48 threads that can be used for execution.
    # There is no way that all the TOSSIM instances will not run over the memory limit!
    # Previous jobs have used about 16.8GB maximum with 12 jobs running on a 25x25 network, that is 1450MB per job.
    # So lets define the number of jobs to run with respect to an amount of RAM slightly greater than
    # that per job.
    # Expect this to need revision if larger networks are requested.
    #
    # TODO: Optimise this, so less RAM is requested per job for smaller network sizes.
    # This means that more threads can run and the smaller jobs finish even quicker!

    ram_for_os_mb = 512
    ram_per_job_mb = 1700
    jobs = int(math.floor(((ram_per_node() * ppn()) - ram_for_os_mb) / ram_per_job_mb))

    cluster_command = "qsub -cwd -V -j yes -h -S /bin/bash -pe smp {} -l h_rt=48:00:00 -l h_vmem={}M -N \"{{}}\"".format(ppn(), ram_per_job_mb)

    if notify_emails is not None and len(notify_emails) > 0:
        cluster_command += " -m ae -M {}".format(",".join(notify_emails))

    #module_commands = "module load java/oracle/1.7.0_65 ; . sci/bin/activate"

    prepare_command = ""

    return Submitter(cluster_command, prepare_command, jobs, job_repeats=1)
