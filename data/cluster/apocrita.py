import subprocess

def name():
    return __name__

def url():
    return "frontend1.apocrita.hpc.qmul.ac.uk"

def ppn():
    return 12

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

    # Size 25 network seem to take ~500mb per instance, so use 1500mb per instance to be safe
    ram_per_job_mb = 1500

    cluster_command = "qsub -V -j oe -pe smp {} -l h_rt=30:00:00 -l h_vmem={}mb -N \"{{}}\"".format(ppn(), ram_per_job_mb)

    prepare_command = "module load java/oracle/1.7.0_65 ; module load python2.7.8 ; . sci/bin/activate"

    return Submitter(cluster_command, prepare_command)
