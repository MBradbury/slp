#!/usr/bin/gnuplot

set terminal pdf enhanced

set style fill solid

binwidth = 1

bin(x,width)=width*floor(x/width) + width/2.0

set boxwidth binwidth

set xrange [-105:-35]
set yrange [0:750]

set xtics auto

set xlabel "Decibels (dB)"
set ylabel "Count"

set output "hist-graph-meyer-heavy.pdf"
plot "<(head -n 1000 ../meyer-heavy.txt)" using (bin($1,binwidth)):(1.0) smooth freq with boxes title "meyer-heavy" lc rgb "dark-violet"

set output "hist-graph-casino-lab.pdf"
plot "<(head -n 1000 ../casino-lab.txt)" using (bin($1,binwidth)):(1.0) smooth freq with boxes title "casino-lab" lc rgb "forest-green"
