import subprocess

def builder():
    from data.run.driver.cluster_builder import Runner
    return Runner()

def copy_to():
    username = raw_input("Enter your Minerva username: ")
    subprocess.check_call("rsync -avz -e ssh --delete cluster {}@minerva.csc.warwick.ac.uk:~/slp-algorithm-tinyos".format(username), shell=True)

def copy_back(dirname):
    username = raw_input("Enter your Minerva username: ")
    subprocess.check_call("rsync -avz -e ssh {0}@caffeine.dcs.warwick.ac.uk:~/slp-algorithm-tinyos/cluster/{1}/*.txt data/results/{1}".format(username, dirname), shell=True)

def submitter():
    from data.run.driver.cluster_submitter import Runner as Submitter

    # Size 25 network seem to take ~500mb per instance, so use 1000mb per instance to be safe
    cluster_command = "msub -q smp -j oe -l nodes=1:ppn=12 -l walltime=30:00:00 -l mem=4000mb -N {}"

    prepare_command = "module swap oldmodules minerva-2.0 ; module load iomkl/13.1.3/ScientificPython/2.8-python-2.7.6"
    
    return Submitter(cluster_command, prepare_command)
