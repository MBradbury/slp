import os, subprocess

def url():
    return "minerva.csc.warwick.ac.uk"

def ppn():
    return 12

def builder():
    from data.run.driver.cluster_builder import Runner
    return Runner()

def copy_to():
    username = raw_input("Enter your Minerva username: ")
    subprocess.check_call("rsync -avz -e \"ssh -i {0}/.ssh/id_rsa\" --delete cluster {1}@{2}:~/slp-algorithm-tinyos".format(
        os.environ['HOME'], username, url()), shell=True)

def copy_back(dirname):
    username = raw_input("Enter your Minerva username: ")
    subprocess.check_call("rsync -avz -e \"ssh -i {0}/.ssh/id_rsa\" {1}@{2}:~/slp-algorithm-tinyos/cluster/{3}/*.txt results/{3}".format(
        os.environ['HOME'], username, url(), dirname), shell=True)

def submitter():
    from data.run.driver.cluster_submitter import Runner as Submitter

    # Size 25 network seem to take ~500mb per instance, so use 1500mb per instance to be safe
    ram_per_job_mb = 1500

    cluster_command = "msub -j oe -l nodes=1:ppn={} -l walltime=10:00:00 -l mem={}mb -N \"{{}}\"".format(ppn(), ppn() * ram_per_job_mb)

    prepare_command = "module swap oldmodules minerva-2.0 ; module load iomkl/13.1.3/ScientificPython/2.8-python-2.7.6"
    
    return Submitter(cluster_command, prepare_command)
