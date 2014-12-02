import os, subprocess

def ppn():
    return 12

def builder():
    from data.run.driver.cluster_builder import Runner
    return Runner()

def copy_to():
    username = raw_input("Enter your Minerva username: ")
    subprocess.check_call("rsync -avz -e \"ssh -i {0}/.ssh/id_rsa\" --delete cluster {1}@minerva.csc.warwick.ac.uk:~/slp-algorithm-tinyos".format(
        os.environ['HOME'], username), shell=True)

def copy_back(dirname):
    username = raw_input("Enter your Minerva username: ")
    subprocess.check_call("rsync -avz -e \"ssh -i {0}/.ssh/id_rsa\" {1}@minerva.csc.warwick.ac.uk:~/slp-algorithm-tinyos/cluster/{2}/*.txt results/{2}".format(
        os.environ['HOME'], username, dirname), shell=True)

def submitter():
    from data.run.driver.cluster_submitter import Runner as Submitter

    # Size 25 network seem to take ~500mb per instance, so use 1000mb per instance to be safe
    ram_per_job_mb = 1000

    cluster_command = "msub -q smp -j oe -l nodes=1:ppn={} -l walltime=25:00:00 -l mem={}mb -N {{}}".format(ppn(), ppn() * ram_per_job_mb)

    prepare_command = "module swap oldmodules minerva-2.0 ; module load iomkl/13.1.3/ScientificPython/2.8-python-2.7.6"
    
    return Submitter(cluster_command, prepare_command)
