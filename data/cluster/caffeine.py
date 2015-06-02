import subprocess

def url():
    return "caffeine.dcs.warwick.ac.uk"

def ppn():
    return 4

def builder():
    from data.run.driver.cluster_builder import Runner as Builder
    return Builder()

def copy_to():
    username = raw_input("Enter your Caffeine username: ")
    subprocess.check_call("rsync -avz -e ssh --delete cluster {}@{}:~/slp-algorithm-tinyos".format(
        username, url()), shell=True)

def copy_back(dirname):
    username = raw_input("Enter your Caffeine username: ")
    subprocess.check_call("rsync -avz -e ssh {0}@{1}:~/slp-algorithm-tinyos/cluster/{2}/*.txt results/{2}".format(
        username, url(), dirname), shell=True)

def submitter():
    from data.run.driver.cluster_submitter import Runner as Submitter

    ram_per_job_mb = 850

    # The -h flags causes the jobs to be submitted as held. It will need to be released before it is run.
    cluster_command = "qsub -q blend -j oe -h -l nodes=1:ppn={} -l walltime=500:00:00 -l mem={}mb -N \"{{}}\"".format(ppn(), ppn() * ram_per_job_mb)

    prepare_command = "module load jdk/1.7.0_07 ; module load python/2.7.8 ; LD_LIBRARY_PATH=\"$LD_LIBRARY_PATH:/opt/share/lib\""

    return Submitter(cluster_command, prepare_command)
