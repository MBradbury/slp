#!/bin/bash
sudo apt-get install liblapack-dev python python-pip python-dev g++ gfortran python-tk git mercurial make libssl-dev libffi-dev
sudo pip install scipy numpy cython pandas more_itertools shutilwhich psutil paramiko pip cryptography --upgrade -v
sudo pip install git+git://github.com/MBradbury/python_euclidean2_2d.git --upgrade -v

mkdir ~/wsn
cd ~/wsn

git clone -b bradbury_2_1_2 https://github.com/MBradbury/tinyos-main.git

cat <<EOT >> ~/tinyos.env
export TOSROOT="/home/$USER/wsn/tinyos_main"
export TOSDIR="$TOSROOT/tos"
export CLASSPATH="$CLASSPATH:$TOSROOT/support/sdk/java:$TOSROOT/support/sdk/java/tinyos.jar"
export MAKERULES="$TOSROOT/support/make/Makerules"
export PYTHONPATH="$PYTHONPATH:$TOSROOT/support/sdk/python"
EOT

echo "source ~/tinyos.env" >> ~/.bashrc

source ~/.bashrc

wget -O - http://tinyprod.net/repos/debian/tinyprod.key | sudo apt-key add -

sudo cat<<EOT >> /etc/apt/sources.list.d/tinyprod-debian.list
deb http://tinyprod.net/repos/debian wheezy main
deb http://tinyprod.net/repos/debian msp430-46 main
deb http://tinyos.stanford.edu/tinyos/dists/ubuntu lucid main
EOT

sudo apt-get update
sudo apt-get install nesc tinyos-tools msp430-46 avr-tinyos

echo "Please enter your bitbucket username: "
read bitbucket_username

hg clone https://${bitbucket_username}@bitbucket.org/${bitbucket_username}/slp-algorithms-tinyos

echo "All Done!"
