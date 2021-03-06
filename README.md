# Introduction

This repository contains code implementing several source location privacy protocol for wireless sensor networks.
The instructions below will inform you how to setup the dependencies to be able to simulate and deploy these algorithms.

# Reproducing Results

The code in this repository has been used to generate the results for several academic papers.
Please see the [docs/papers](./doc/papers) directory for information on how to run experiments for specific papers.

# Syntax Highlighting

nesC is a C derivative. Syntax highlighting for Sublime Text 3 is maintained at <https://github.com/MBradbury/Packages/blob/master/C%2B%2B/nesC.sublime-syntax>.

# Setup System Requirements

The following commands will get you set up with TinyOS and the slp-algorithms-tinyos framework on your local machine.

1. Install required packages. The commands below are specific to Debian.
   Other OSes will need to install these packages in a different way.
   You may need to prefix commands with "sudo" to install using admin privileges.

        :::bash
        sudo apt-get install liblapack-dev python python-pip python-dev g++ gfortran python-tk git mercurial make libssl-dev libffi-dev libxml2-utils

   Python 3 is required by the testbed framework.

2. Install python libraries

        :::bash
        pip install scipy numpy cython pandas more_itertools psutil paramiko pip cryptography requests matplotlib networkx pydot lazy_import --upgrade -v
        pip install git+git://github.com/MBradbury/python_euclidean2_2d.git --upgrade -v
        pip install git+git://github.com/emulbreh/bridson.git --upgrade -v

   Make sure to prefix these commands with ```sudo``` if installing for the system python.

## Using pyenv (general)

If you do not have python installed, or have an install that requires
admin permissions to use pip install, then pyenv is a good alternative.

You do not need to do this step if you are using your system python.

```bash
sudo apt-get install lzma-dev tk-dev libreadline-dev libbz2-dev libssl-dev
```

```bash
curl -L https://raw.githubusercontent.com/yyuu/pyenv-installer/master/bin/pyenv-installer | bash
CONFIGURE_OPTS="--enable-optimizations" MAKE_OPTS=profile-opt pyenv install 3.6.4 -v
pyenv global 3.6.4
```

## Using pyenv (on flux)

To install on flux there is a slightly different procedure:

```bash
module load flux-installers && pyenv-install.sh && source ~/.bashrc
CONFIGURE_OPTS="--enable-optimizations" MAKE_OPTS=profile-opt pyenv install 3.6.4 -v
pyenv global 3.6.4
```

Please ensure that you install the python packages using pip after setting up python in this way.

# Setup SLP Simulation Framework

1. Setup directory structure

        :::bash
        cd ~
        mkdir wsn
        cd wsn

2. Clone the SLP simulation framework

   I recommend forking MBradbury/slp-algorithms-tinyos to give you your
   own repository to push changes to. You can do this on bitbucket.org.

   * Anonymously:

        :::bash
        hg clone https://MBradbury@bitbucket.org/MBradbury/slp-algorithms-tinyos

   * With a username (one of the following):

        :::bash
        hg clone ssh://hg@bitbucket.org/MBradbury/slp-algorithms-tinyos

        :::bash
        hg clone https://<username>@bitbucket.org/MBradbury/slp-algorithms-tinyos

You should end up with a path to this repo such as ~/wsn/slp-algorithms-tinyos.

# Setup TinyOS

1. Clone the tinyos fork 

        :::bash
        cd ~/wsn
        git clone -b bradbury_2_1_2 https://github.com/MBradbury/tinyos-main.git

   There should now be a folder at ~/wsn/tinyos-main.

2. Create ~/tinyos.env with the following contents

        :::bash
        export TOSROOT="<fill in path to tinyos repo here>"
        export TOSDIR="$TOSROOT/tos"
        export CLASSPATH="$CLASSPATH:$TOSROOT/support/sdk/java:$TOSROOT/support/sdk/java/tinyos.jar"
        export MAKERULES="$TOSROOT/support/make/Makerules"
        export PYTHONPATH="$PYTHONPATH:$TOSROOT/support/sdk/python"

   Replace <fill in path to tinyos repo here> with the path to the tinyos repo.

3. Add the following to ~/.bashrc before any interactivity check

        :::bash
        source ~/tinyos.env
   Then run the following:

        :::bash
        source ~/.bashrc

4. Install TinyOS dependencies

   These instructions are based on those at: http://tinyprod.net/repos/debian/
   You can view that website for more information.

   1. Add the TinyProd signing key

        :::bash
        wget -O - http://tinyprod.net/repos/debian/tinyprod.key | sudo apt-key add -

   2. Specify the apt-get sources

      Add a file called "/etc/apt/sources.list.d/tinyprod-debian.list" with the following contents:

        deb http://tinyprod.net/repos/debian wheezy main
        deb http://tinyos.stanford.edu/tinyos/dists/ubuntu lucid main

   3. Install the dependencies

        :::bash
        sudo apt-get update
        sudo apt-get install nesc tinyos-tools

      If you are working with avrora, cooja or deploying to a testbed then you will want to install
      the necessary cross compilers. There are two options here, either use the TinyOS packaged
      compilers or use your operating system's toolchain.

      Some issues have been observed with the MSP430 4.6.3 version distributed with both
      TinyOS and Debian. Alternately you could download the latest MSP430-GCC from TI at
      <http://software-dl.ti.com/msp430/msp430_public_sw/mcu/msp430/MSPGCC/latest/index_FDS.html>.

      TinyOS:

        ::bash
        deb http://tinyprod.net/repos/debian msp430-46 main
        sudo apt-get install msp430-46 avr-tinyos

      Debian:

        :::bash
        sudo apt-get-install gcc-msp430 gcc-avr

   4. Test tinyos worked

        :::bash
        cd ~/wsn/tinyos-main/apps/Blink
        make micaz sim

      You should see an output that contains "*** Successfully built micaz TOSSIM library".

# Set up Avrora (optional if only using TOSSIM)

  1. Make sure a suitable version of Java is installed

  2. Go to https://sourceforge.net/projects/avrora/ and download the latest avrora jar

  3. Edit ~/.bashrc to export an environment variable called "AVRORA_JAR_PATH" which contains
     the path to the Avrora jar. An example path is shown below.

     :::bash
     export AVRORA_JAR_PATH="/home/matt/wsn/avrora/avrora-beta-1.7.117.jar"

# Set up COOJA (optional if only using TOSSIM)

  COOJA is a simulator that comes with Contiki. If you are writing your code using
  TinyOS you will typically use the TOSSIM simulator, so will not need COOJA.

  1. Clone the contiki repository

       :::bash
       cd ~/wsn
       git clone git@github.com:contiki-os/contiki.git -b release-3-1
       cd contiki
       git submodule update --init

  If you wish to simulate MicaZ nodes you will need to use this fork and the master branch instead: <https://github.com/MBradbury/contiki.git>.
  This is due to a number of bugs in Cooja's MicaZ code.

  2. Install dependencies

       :::bash
       sudo apt-get update
       sudo apt-get install ant

  3. Build COOJA

       :::bash
       cd ~/wsn/contiki/tools/cooja
       ant jar

  4. Edit ~/.bashrc to export an environment variable called "CONTIKI_DIR" which contains
     the path to the contiki repository. An example path is shown below.

       :::bash
       export CONTIKI_DIR="/home/matt/wsn/contiki"


# Updating from upstream

Ideally you will have forked the slp-algorithms-tinyos repository.
You will want to pull updates from it by doing the following:

Modify your slp-algorithms-tinyos/.hg/hgrc to contain the following line under default:
"upstream = ssh://hg@bitbucket.org/MBradbury/slp-algorithms-tinyos"

If you are not using SSH keys, then you should use the following:
"upstream = https://<username>@bitbucket.org/MBradbury/slp-algorithms-tinyos"

You can then update from the upstream fork by doing the following:
```bash
hg pull -u upstream
```

You may need to perform a merge:
```bash
hg commit -m "Merge"
```

You will need to push what you have pulled to your fork:
```bash
hg push
```

You can update the tinyos repository by doing the following:
```bash
git pull
```

Or by the following instruction if you forked it:
```bash
git pull https://github.com/MBradbury/tinyos-main bradbury_2_1_2
```

# Examples for running simulations

(Assumes you are in ~/wsn/slp-algorithms-tinyos)

See the options that can be provided to an algorithm:
```bash
./run.py algorithm.protectionless tossim GUI -h
```

Some example runs
```bash
./run.py algorithm.protectionless tossim GUI -c SourceCorner -ns 11 -cm low-asymmetry -nm meyer-heavy  -am "SeqNosReactiveAttacker()" --source-period 1
./run.py algorithm.adaptive_spr tossim GUI -c SourceCorner -ns 11 -cm low-asymmetry -nm meyer-heavy  -am "SeqNosReactiveAttacker()" --source-period 1 -safety 50 --approach PB_FIXED1_APPROACH
./run.py algorithm.phantom tossim GUI -c SourceCorner -ns 11 -cm ideal -nm casino-lab  -am "SeqNosReactiveAttacker()" --source-period 1 -safety 50 --walk-length 8
```

An example run with a bit flip fault model. Note that we expect the simulation to do nothing after
this point, as the source node has its busy flag flipped to true.
```bash
./run.py algorithm.protectionless tossim GUI -c SourceCorner -ns 11 -cm low-asymmetry -nm meyer-heavy --source-period 1 -am "SeqNosReactiveAttacker()" -nido randomised -fm "BitFlipFaultModel(0, 'SourceBroadcasterC.busy', 2)"
```

We might also want to test with crashes that can be done like so.
Note that in this example we have used the string 'top_right' to specify the top right node's id.
Other landmark node names can be used in this fashion.
```bash
./run.py algorithm.protectionless tossim GUI -c SourceCorner -ns 11 -cm low-asymmetry -nm meyer-heavy --source-period 1 -am "SeqNosReactiveAttacker()" -nido randomised -fm "NodeCrashFaultModel(12, 5)"
./run.py algorithm.protectionless tossim GUI -c SourceCorner -ns 11 -cm low-asymmetry -nm meyer-heavy --source-period 1 -am "SeqNosReactiveAttacker()" -nido randomised -fm "NodeCrashFaultModel('top_right', 5)"
```

When running locally with a GUI it can be helpful to display certain variables instead of the node ids.
These are two examples of how to specify variables for regular components and generic components
```bash
./run.py algorithm.adaptive_spr_notify tossim GUI -cm low-asymmetry -ns 11 -c SourceCorner -nm meyer-heavy -safety 50 -am "SeqNosReactiveAttacker()" --source-period 1 --approach PB_FIXED1_APPROACH --gui-node-label 'SourceBroadcasterC.extra_to_send'
./run.py algorithm.adaptive_spr_notify tossim GUI -cm low-asymmetry -ns 11 -c SourceCorner -nm meyer-heavy -safety 50 -am "SeqNosReactiveAttacker()" --source-period 1 --approach PB_FIXED1_APPROACH --gui-node-label '/*SourceBroadcasterAppC.NodeTypeC.NodeTypeP*/NodeTypeP$0$current_type'
```

# Running locally

To run a large combination of parameters locally you can use the following command
```bash
./create.py <algorithm> run <sim>
```

You will first need to edit your algorithm's Parameters.py file to contain the parameter
combinations that you wish to run.

# Running on the cluster

In order to run your code on the cluster you will first need to checkout the files as described above.

The available clusters are described by individual files in slp-algorithms-tinyos/data/cluster.

## Safety Periods

The first step is to ensure that you have the correct safety period results on your computer.
If you are using a standard configuration then it is likely the slp-results-protectionless will contain the
necessary safety periods.
If you are using custom configurations, then it would be a good idea to fork the slp-results-protectionless
repository, gather the results and commit them to that repository.

One you have the necessary safety period results you can create the summary file like so:

```bash
./create.py protectionless analyse
```

You can then copy that summary to the desired cluster like so:

```bash
./create.py protectionless cluster <cluster> copy-result-summary
```

The cluster will now have the correct safety periods present to be able to run the simulations.

## Arguments

The next step is to modify the algorithm's Parameters.py file to contain the correct set of arguments you wish to run.
To aid in testing there exists a dummy cluster driver which will print out the cluster command rather than execute it.

Use this to test that you have set up the correct parameters in Parameters.py like so:
```bash
./create.py <algorithm> cluster dummy submit
```

To copy this file to the cluster you must execute the following
```bash
./create.py <algorithm> cluster <cluster> copy-parameters
```

## Build

You must now build all the combinations of arguments. You may wish to provide "--no-skip-complete" if no runs have been performed.
```bash
./create.py <algorithm> cluster dummy build
```

## Copy built binaries to cluster

To copy the built binaries to the cluster you need to execute the following command:
```bash
./create.py <algorithm> cluster <cluster> copy
```

## Submitting jobs to the cluster

To submit jobs to the cluster you will need to modify certain files.


The most important file to modify is Parameters.py, as this defined the parameters combinations
that will be run on the cluster. DO NOT modify Parameters.py.sample unless a new parameter is added.
Custom parameter combinations should only be specified in Parameters.py.


When submitting to the cluster it can be helpful to specify a time limit. It is important to specify a limit that is about
how long you expect the jobs to take, plus a bit extra for safety. If the jobs exceed the time limit they will
be killed. If they take much less time than the time limit they will take longer to be scheduled.

So considering this, I have found that it is best to specify different expected times for different sized networks.
With size 11 having a smaller time limit and size 25 having a larger time limit.

To begin with ensure that your algorithm's CommandLine.py is up-to-date.

You will need to modify slp-algorithms-tinyos/algorithm/<algorithm>/CommandLine.py to override _time_estimater.
Look at CommandLineCommon.py for the defaults.

To keep things simple you could just use a very large request time, but it is likely it will mean your jobs are not
run as often as they could be.


Now submit the jobs using the following. Again you may need to provide "--no-skip-complete".
```bash
./create.py <algorithm> cluster <cluster> submit
```

## Array Jobs

Alternatively you could use array jobs using the following command. The difference here is that rather than submitting
one job that takes up an entire node, many smaller jobs that only require one processor are submitted instead. This
should improve throughput of results on certain clusters. As the number of repeats performed per job will be smaller
make sure that you divide the walltime by the number of array jobs that will be created.

```bash
./create.py <algorithm> cluster <cluster> submit --array
```

## Releasing jobs

Cluster jobs are submitted as held jobs. Please inspect them to make sure that everything is setup correctly.
To queue to jobs you need to release them. This is different for different cluster platforms.

For flux you should do the following:
```bash
./scripts/pbs-qstat.sh | cut -f 1 -d' ' | xargs qrls
```

## Copy back from cluster

Once all your jobs have finished you will need to copy them back from the cluster.
```bash
./create.py <algorithm> cluster <cluster> copy-back
```

You can then analyse the results like so:
```bash
./create <algorithm> analyse
```

Which will generate a result summary at "slp-algorithms-tinyos/results/<algorithm>/<algorithm>-results.csv".

As some of the analysis can be very expensive it is recommended to skip certain fields.
```bash
./create <algorithm> analyse -S SentHeatMap ReceivedHeatMap
```

## Resubmitting Jobs

If for any reason you need to go back and submit more of the same jobs that you have run before there are a few tricks.

When building or submitting jobs, the results summary file (in slp-algorithms-tinyos/results/<algorithm>/<algorithm>-results.csv)
will be read so that jobs will only be executed if the results show that not enough have been executed so far.

You can copy these result summaries to the cluster using:
```bash
./create.py <algorithm> cluster <cluster> copy-result-summary
```

If you want to ignore any existing results make sure to pass "no-skip-complete" when building or submitting cluster jobs.
Doing so will run all parameter combinations as specified in the <algorithm>/CommandLine.py file.
```bash
./create.py <algorithm> cluster dummy build --no-skip-complete
./create.py <algorithm> cluster <cluster> submit --no-skip-complete
```

## Job Notification

A useful feature is the ability to be notified when a job is completed or cancelled via email.
This can be done in two ways (#2 is recommended, as I tend to forget to do #1):

1. By specifying "--notify=<email address>" when submitting your jobs.

2. By editing your ~/.bashrc to contain "export SLP_NOTIFY_EMAILS=<email address>"

# Faster analysis

Analysing results may be slow depending on how many are present.

Your first attempt to speed up the analysis is to ask the analysis to use more threads.
A good number of threads will vary from machine to machine. I usually use the total number
of physical cores present on the machine, if it has HT. If not, I use the number of physical
cores minus 1.

```bash
./create.py <algorithm> analyse --thread-count 4
```

If that is still fairly slow, you can compile the analysis code to c.

Make sure cython is installed first.
```bash
pip install cython
```

Then make sure you are in the root of slp-algorithms-tinyos before cythonising analysis.
Once cythonised, the analysis script is run as usual.
```bash
cd slp-algorithms-tinyos
./scripts/cythonise_analysis.sh
./create.py <algorithm> analyse --thread-count 4
```

A very important thing to note is that if you make any change to data/analysis.py
then you MUST rerun ./scripts/cythonise_analysis.sh. This may happen when you pull
from another repo. If you do not then analysis may not work properly.


# Merging results from multiple runs on the cluster

When you run the same job on the cluster twice you will need to
merge the results files for the second run to be of use.
The script in ./scripts/merge_results.py can be used to do this.

To make sure the correct files are merged all results will execute
a job with seed 44 twice. If files are incorrect merged then the
analysis will fail as the results for seed 44 will not match.

First, lets say you have already copied the results from the
previous run on the cluster locally to your machine.
This folder will be something like: "slp-algorithms-tinyos/results/<algorithm>".

1. Move the existing results to another directory "slp-algorithms-tinyos/results/<algorithm>/old"
2. Copy results from the cluster using "./create <algorithm> <cluster> copy-back"
3. Move the new results to "slp-algorithms-tinyos/results/<algorithm>/new"
4. Move the first set of results back to where they were
5. Run ./scripts/merge_results.py --results-dir "slp-algorithms-tinyos/results/<algorithm>" --merge-dir "slp-algorithms-tinyos/results/<algorithm>/new"

You will need to manually remove the backup files which are left behind in case the merge goes wrong.


# Deploying on a testbed

## FlockLab Setup

You will need to register for an account at https://flocklab.ethz.ch
The credentials you used to register will need to be saved in a file at "~/.flocklabauth" with the format of the file:
```bash
USER=username
PASSWORD=password
```
Replace `username` and `password` with the username and password that you registered with.


## FiT IoT-Lab Setup

Install the python tools by following the instructions at https://github.com/iot-lab/iot-lab/wiki/CLI-Tools-Installation
The current release (2.4.0) can be checked at this website: https://github.com/iot-lab/cli-tools/releases
```bash
sudo apt-get install python-setuptools
wget -qO - https://github.com/iot-lab/cli-tools/archive/[release_version].tar.gz | tar xz
cd cli-tools-[release_version] && sudo python setup.py install
```

Authenticate your account:
```bash
auth-cli -u <username>
```

## w-iLab.t Setup

Download jfed (see: http://jfed.iminds.be/downloads). You must make sure you have Java 8 installed.

```bash
sudo apt-key adv --keyserver hkp://pool.sks-keyservers.net --recv-keys E7F4995E 
sudo echo "deb http://jfed.iminds.be/deb-repo stable main" | sudo tee /etc/apt/sources.list.d/jfed.list
sudo apt-get update
sudo apt-get install jfed 
```

Download your certificate from https://authority.ilabt.iminds.be/getcert.php

# Profiling the code

## Simulator framework profiling

Perform the analysis:
```bash
python -OO -m cProfile -o s1.prof ./run.py ...
```

View the results:
```bash
./scripts/analyse_prof.sh s1.prof
```

## TinyOS profiling

Install the dependences:
```bash
sudo apt-get install google-perftools
sudo pip install yep
```

Perform the analysis:
```bash
python -OO -m yep -o t1.prof -- ./run.py ...
```

Visualise the call tree:
```bash
google-pprof -gv $(which python) t1.prof
```
