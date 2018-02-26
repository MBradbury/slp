
from datetime import timedelta
import os
import math
import subprocess

class ClusterCommon(object):
    def __init__(self, kind, url, ssh_auth, ppn, tpp, rpn, max_walltime=None):
        self.kind = kind
        self.url = url
        self.ssh_auth = ssh_auth
        self.ppn = ppn
        self.threads_per_processor = tpp
        self.ram_per_node = rpn
        self.max_walltime = max_walltime

    def submitter(self, notify_emails=None):
        raise NotImplementedError

    def array_submitter(self, notify_emails=None):
        raise NotImplementedError

    def name(self):
        return type(self).__name__

    def builder(self):
        from data.run.driver.cluster_builder import Runner as Builder
        return Builder()

    def copy_to(self, dirname, user=None):
        username = self._get_username(user)
        subprocess.check_call("rsync -avz -e \"{0}\" cluster/__init__.py cluster/{3} {1}@{2}:~/slp-algorithms-tinyos/cluster".format(
            self.ssh_auth, username, self.url, dirname), shell=True)

    def copy_file(self, results_directory_path, filename, user=None):
        username = self._get_username(user)
        subprocess.check_call("rsync -avz -e \"{0}\" --rsync-path=\"mkdir -p ~/slp-algorithms-tinyos/{results_directory_path} && rsync\" {results_directory_path}/{filename} {1}@{2}:~/slp-algorithms-tinyos/{results_directory_path}/{filename}".format(
            self.ssh_auth, username, self.url, results_directory_path=results_directory_path, filename=filename), shell=True)

    def copy_back(self, dirname, sim_name, user=None):
        username = self._get_username(user)
        subprocess.check_call("rsync -avz -e \"{0}\" {1}@{2}:~/slp-algorithms-tinyos/cluster/{3}/*-{4}.txt results/{4}/{3}".format(
            self.ssh_auth, username, self.url, dirname, sim_name), shell=True)

    def _get_username(self, user):
        if user is not None:
            return user

        # Check in the ssh config for the user for this cluster
        try:
            import paramiko

            ssh_config = paramiko.SSHConfig()

            with open(os.path.expanduser("~/.ssh/config"), "r") as ssh_config_file:
                ssh_config.parse(ssh_config_file)

            lookup = ssh_config.lookup(self.name())

            user = lookup['user']

            print(f"Using the username '{user}' from your '~/.ssh/config'. Rerun with the --user option to override this.")

            return user

        except (ImportError, KeyError, FileNotFoundError):
            pass

        # Just ask them for their username
        return input("Enter your {} username: ".format(self.name().title()))


    def _ram_to_ask_for(self, ram_for_os_mb=2 * 1024):
        total_ram = self.ram_per_node * self.ppn
        app_ram = total_ram - ram_for_os_mb
        return int(app_ram // self.ppn) * self.ppn

    def _pbs_submitter(self, notify_emails=None, dry_run=False, unhold=False, *args, **kwargs):
        from data.run.driver.cluster_submitter import Runner as Submitter

        ram_to_ask_for_mb = self._ram_to_ask_for()

        # The -h flags causes the jobs to be submitted as held. It will need to be released before it is run.
        hold = "" if unhold else "-h"
        
        # Don't provide a queue, as the job will be routed to the correct place.
        cluster_command = f"qsub -j oe {hold} -l nodes=1:ppn={self.ppn} -l walltime={{}} -l mem={ram_to_ask_for_mb}mb -N \"{{}}\""

        if notify_emails is not None and len(notify_emails) > 0:
            cluster_command += " -m bae -M {}".format(",".join(notify_emails))

        prepare_command = "cd $PBS_O_WORKDIR"

        return Submitter(cluster_command, prepare_command, self.ppn, job_repeats=1, dry_run=dry_run, max_walltime=self.max_walltime)

    def _pbs_array_submitter(self, notify_emails=None, dry_run=False, unhold=False, *args, **kwargs):
        from data.run.driver.cluster_submitter import Runner as Submitter

        ram_per_node_mb = self._ram_to_ask_for() / self.ppn

        num_jobs = 1
        num_array_jobs = self.ppn

        mem = num_jobs * ram_per_node_mb

        # The -h flags causes the jobs to be submitted as held. It will need to be released before it is run.
        hold = "" if unhold else "-h"

        # Don't provide a queue, as the job will be routed to the correct place.
        
        # %1 ensures that only a single array job will be running at a given time

        cluster_command = f"qsub -j oe {hold} -t 1-{num_array_jobs}%1 -l nodes=1:ppn={num_jobs} -l walltime={{}} -l mem={mem}mb -N \"{{}}\""

        if notify_emails is not None and len(notify_emails) > 0:
            cluster_command += " -m bae -M {}".format(",".join(notify_emails))

        prepare_command = "cd $PBS_O_WORKDIR"

        return Submitter(cluster_command, prepare_command, num_jobs,
                         job_repeats=num_array_jobs, array_job_variable="$PBS_ARRAYID", dry_run=dry_run, max_walltime=self.max_walltime)

    def _sge_submitter(self, notify_emails=None, dry_run=False, unhold=False, *args, **kwargs):
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
        jobs = int(math.floor(((self.ram_per_node * self.ppn) - ram_for_os_mb) / ram_per_job_mb))

        # The -h flags causes the jobs to be submitted as held. It will need to be released before it is run.
        hold = "" if unhold else "-h"

        cluster_command = f"qsub -cwd -V -j yes {hold} -S /bin/bash -pe smp {self.ppn} -l h_rt={{}} -l h_vmem={ram_per_job_mb}M -N \"{{}}\""

        if notify_emails is not None and len(notify_emails) > 0:
            cluster_command += " -m ae -M {}".format(",".join(notify_emails))

        prepare_command = ""

        return Submitter(cluster_command, prepare_command, jobs, job_repeats=1, dry_run=dry_run, max_walltime=self.max_walltime)

    def _moab_submitter(self, notify_emails=None, dry_run=False, unhold=False, *args, **kwargs):
        from data.run.driver.cluster_submitter import Runner as Submitter

        ram_to_ask_for_mb = self._ram_to_ask_for()

        # The -h flags causes the jobs to be submitted as held. It will need to be released before it is run.
        hold = "" if unhold else "-h"

        # Don't provide a queue, as the job will be routed to the correct place.
        cluster_command = f"msub -j oe {hold} -l nodes=1:ppn={self.ppn} -l walltime={{}} -l mem={ram_to_ask_for_mb}mb -N \"{{}}\""

        if notify_emails is not None and len(notify_emails) > 0:
            cluster_command += " -m bae -M {}".format(",".join(notify_emails))

        if self.kind == "slurm":
            prepare_command = "cd $SLURM_SUBMIT_DIR"
        else:
            prepare_command = "cd $PBS_O_WORKDIR"

        return Submitter(cluster_command, prepare_command, self.ppn, job_repeats=1, dry_run=dry_run, max_walltime=self.max_walltime)


class dummy(ClusterCommon):
    def __init__(self):
        super(dummy, self).__init__("dummy", None, None,
            ppn=12,
            tpp=1, # HT is disabled
            rpn=(32 * 1024) / 12 # 32GB per node
        )

    def copy_to(self, dirname, user=None):
        raise RuntimeError("Cannot copy to the dummy cluster")

    def copy_file(self, results_directory_path, filename, user=None):
        raise RuntimeError("Cannot copy to the dummy cluster")

    def copy_back(self, dirname, user=None):
        raise RuntimeError("Cannot copy back from the dummy cluster")

    def submitter(self, unhold=False, *args, **kwargs):
        from data.run.driver.cluster_submitter import Runner as Submitter

        class DummySubmitter(Submitter):
            """Don't submit, just print the command"""
            def _submit_job(self, command):
                print(command)

        ram_to_ask_for_mb = self._ram_to_ask_for()

        # The -h flags causes the jobs to be submitted as held. It will need to be released before it is run.
        hold = "" if unhold else "-h"

        cluster_command = f"qsub -q serial -j oe {hold} -l nodes=1:ppn={self.ppn} -l walltime={{}} -l mem={ram_to_ask_for_mb}mb -N \"{{}}\""

        notify_emails = kwargs.get("notify_emails", None)
        if notify_emails is not None and len(notify_emails) > 0:
            cluster_command += " -m bae -M {}".format(",".join(notify_emails))

        prepare_command = " <prepare> "

        return DummySubmitter(cluster_command, prepare_command, self.ppn)

    def array_submitter(self, unhold=False, *args, **kwargs):
        from data.run.driver.cluster_submitter import Runner as Submitter

        class DummySubmitter(Submitter):
            """Don't submit, just print the command"""
            def _submit_job(self, command):
                print(command)

        ram_per_job_mb = self.ram_per_node
        num_jobs = 1
        num_array_jobs = self.ppn

        mem = num_jobs * ram_per_job_mb

        # The -h flags causes the jobs to be submitted as held. It will need to be released before it is run.
        hold = "" if unhold else "-h"

        cluster_command = f"qsub -q serial -j oe {hold} -t 1-{num_array_jobs}%1 -l nodes=1:ppn={num_jobs} -l walltime={{}} -l mem={mem}mb -N \"{{}}\""

        notify_emails = kwargs.get("notify_emails", None)
        if notify_emails is not None and len(notify_emails) > 0:
            cluster_command += " -m bae -M {}".format(",".join(notify_emails))

        prepare_command = " <prepare> "

        return DummySubmitter(cluster_command, prepare_command, num_jobs, job_repeats=num_array_jobs, array_job_variable="$DUMMY_ARRAYID")

class flux(ClusterCommon):
    def __init__(self):
        super(flux, self).__init__("pbs", "flux.dcs.warwick.ac.uk", "ssh",
            ppn=12,
            tpp=1, # HT is disabled
            rpn=(32 * 1024) / 12, # 32GB per node
            max_walltime=timedelta(hours=48) # See "qstat -Qf" for the batch queue
        )

    def submitter(self, *args, **kwargs):
        notify_emails = kwargs.get("notify_emails", None)
        if notify_emails is not None and len(notify_emails) > 0:
            print("Warning: flux does not currently have email notification setup")

        # WARNING: Use mem instead of pmem when submitting jobs to flux

        return self._pbs_submitter(*args, **kwargs)

    def array_submitter(self, *args, **kwargs):
        notify_emails = kwargs.get("notify_emails", None)
        if notify_emails is not None and len(notify_emails) > 0:
            print("Warning: flux does not currently have email notification setup")

        return self._pbs_array_submitter(*args, **kwargs)

class apocrita(ClusterCommon):
    def __init__(self):
        super(apocrita, self).__init__("sge", "frontend1.apocrita.hpc.qmul.ac.uk", "ssh",
            ppn=12,
            tpp=4,
            rpn=2 * 1024
        )

    def submitter(self, *args, **kwargs):
        return self._sge_submitter(*args, **kwargs)

class tinis(ClusterCommon):
    def __init__(self):
        super(tinis, self).__init__("pbs", "tinis.csc.warwick.ac.uk", os.path.expanduser("ssh -i ~/.ssh/id_rsa"),
            ppn=16,
            tpp=1,
            rpn=(64 * 1024) / 16 # 64GB per node
        )

    def submitter(self, *args, **kwargs):
        return self._moab_submitter(*args, **kwargs)

class orac(ClusterCommon):
    def __init__(self):
        super(orac, self).__init__("slurm", "orac.csc.warwick.ac.uk", os.path.expanduser("ssh -i ~/.ssh/id_rsa"),
            ppn=28,
            tpp=1,
            rpn=(128 * 1024) / 28 # 128GB per node
        )

    def submitter(self, *args, **kwargs):
        return self._moab_submitter(*args, **kwargs)

def available():
    """A list of the names of the available clusters."""
    return ClusterCommon.__subclasses__()  # pylint: disable=no-member

def available_names():
    return [cls.__name__ for cls in available()]

def create(name):
    return [cls for cls in available() if cls.__name__ == name][0]()
