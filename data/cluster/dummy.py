
def url():
    return None

def ppn():
    return 1

def builder():
    from data.run.driver.cluster_builder import Runner as Builder
    return Builder()

def copy_to():
    raise RuntimeError("Cannot copy to the dummy cluster")

def copy_back(dirname):
    raise RuntimeError("Cannot copy back from the dummy cluster")

def submitter():
    from data.run.driver.cluster_submitter import Runner as Submitter

    # Don't submit, just print the command
    class DummySubmitter(Submitter):
        def __init__(self, cluster_command, prepare_command):
            super(DummySubmitter, self).__init__(cluster_command, prepare_command)

        def _submit_job(self, command):
            print(command)

    ram_per_job_mb = 1000

    cluster_command = "qsub -q serial -j oe -h -l nodes=1:ppn={} -l walltime=500:00:00 -l mem={}mb -N {{}}".format(ppn(), ppn() * ram_per_job_mb)

    prepare_command = " <prepare> "

    return DummySubmitter(cluster_command, prepare_command)
