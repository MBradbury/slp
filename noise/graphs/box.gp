#!/usr/bin/gnuplot

set terminal pdf enhanced

set style fill solid 0.25 border -1
set style boxplot outliers pointtype 7
set style data boxplot
set boxwidth 0.5
set pointsize 0.5

set border 2

unset key

set xtics ("meyer-heavy" 1, "casino-lab" 2) scale 0.0
set xtics nomirror
set ytics nomirror

set yrange [-35:-105]

set output "box-graph.pdf"

plot "<(head -n 1000 ../meyer-heavy.txt)" using (1):1 title "meyer-heavy", "<(head -n 1000 ../casino-lab.txt)" using (2):1 title "casino-lab"
