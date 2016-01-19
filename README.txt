
1. Clone the SLP simulation framework

Anonymously:

hg clone https://MBradbury@bitbucket.org/MBradbury/slp-algorithm-tinyos

With a username:

hg clone ssh://hg@bitbucket.org/MBradbury/slp-algorithm-tinyos
hg clone https://<username>@bitbucket.org/MBradbury/slp-algorithm-tinyos

2. Clone the tinyos fork 

git clone -b bradbury_2_1_2 https://github.com/MBradbury/tinyos-main.git

3. Create ~/tinyos.env with the following contents

export TOSROOT="<fill in path to tinyos repo here>"
export TOSDIR="$TOSROOT/tos"
export CLASSPATH="$CLASSPATH:$TOSROOT/support/sdk/java:$TOSROOT/support/sdk/java/tinyos.jar"
export MAKERULES="$TOSROOT/support/make/Makerules"
export PYTHONPATH="$PYTHONPATH:$TOSROOT/support/sdk/python"

Add the following to ~/.bashrc

source ~/tinyos.env

4. Compile parts of the simulation

cd slp-algorithm-tinyos/tinyos/support/sdk/java/net/tinyos/sim
javac LinkLayerModel.java

