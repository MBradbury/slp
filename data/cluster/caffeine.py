import subprocess

def builder():
    from data.run.driver.cluster_builder import Runner as Builder
    return Builder()

def copy_to():
    username = raw_input("Enter your Caffeine username: ")
    subprocess.check_call("rsync -avz -e ssh --delete cluster {}@caffeine.dcs.warwick.ac.uk:~/slp-algorithm-tinyos".format(username), shell=True)

def copy_back(dirname):
    username = raw_input("Enter your Caffeine username: ")
    subprocess.check_call("rsync -avz -e ssh {0}@caffeine.dcs.warwick.ac.uk:~/slp-algorithm-tinyos/cluster/{1}/*.txt data/results/{1}".format(username, dirname), shell=True)

def submitter():
    from data.run.driver.cluster_submitter import Runner as Submitter

    # The -h flags causes the jobs to be submitted as held. It will need to be released before it is run.
    cluster_command = "qsub -q serial -j oe -h -l nodes=1:ppn=4 -l walltime=250:00:00 -N {}"

    prepare_command = "module load jdk/1.7.0_07 ; module load python/2.7.8"

    return Submitter(cluster_command, prepare_command)
