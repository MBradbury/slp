#!/usr/bin/gnuplot

set terminal pdf enhanced

set style fill solid

set key top left

binwidth = 1

bin(x,width)=width*floor(x/width) + width/2.0

set boxwidth binwidth

set xrange [-35:-105]
set yrange [0:2000]

set xtics auto

set xlabel "Noise (dB)"
set ylabel "Count"

set output "hist-graph-meyer-heavy.pdf"
plot "<(head -n 2500 ../meyer-heavy.txt)" using (bin($1,binwidth)):(1.0) smooth freq with boxes title "meyer-heavy" lc rgb "dark-violet"

set output "hist-graph-casino-lab.pdf"
plot "<(head -n 2500 ../casino-lab.txt)" using (bin($1,binwidth)):(1.0) smooth freq with boxes title "casino-lab" lc rgb "forest-green"
