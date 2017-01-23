#!/usr/bin/gnuplot

set terminal pdf enhanced

set style fill solid 0.25 border -1
set style boxplot outliers pointtype 7
set style data boxplot
#set boxwidth 1.5
set pointsize 0.5

set border 2

unset key

set xtics ("meyer-heavy" 1, "casino-lab" 2) scale 0.0
#set xtics ("meyer-heavy-1k" 1, "meyer-heavy-10k" 2, "casino-lab-1k" 3, "casino-lab-10k" 4) scale 0.0
#set xtics ("meyer-heavy" 1, "meyer-heavy-1k" 2, "meyer-heavy-10k" 3, "casino-lab" 4, "casino-lab-1k" 5, "casino-lab-10k" 6) scale 0.0

set xtics nomirror
set ytics nomirror

set yrange [-25:-105]

set ylabel "Decibels (dB)"

set output "box-graph.pdf"

plot "<(head -n 2500 ../meyer-heavy.txt)" using (1):1 title "meyer-heavy", \
     "<(head -n 2500 ../casino-lab.txt)" using (2):1 title "casino-lab", \

#plot "<(head -n 2000 ../meyer-heavy.txt)" using (1):1 title "meyer-heavy-1k", \
#     "<(head -n 10000 ../meyer-heavy.txt)" using (2):1 title "meyer-heavy-10k", \
#     "<(head -n 1000 ../casino-lab.txt)" using (3):1 title "casino-lab-1k", \
#     "<(head -n 10000 ../casino-lab.txt)" using (4):1 title "casino-lab-10k"

#plot "../meyer-heavy.txt" using (1):1 title "meyer-heavy", \
#     "<(head -n 1000 ../meyer-heavy.txt)" using (2):1 title "meyer-heavy-1k", \
#     "<(head -n 10000 ../meyer-heavy.txt)" using (3):1 title "meyer-heavy-10k", \
#     "../casino-lab.txt" using (4):1 title "casino-lab", \
#     "<(head -n 1000 ../casino-lab.txt)" using (5):1 title "casino-lab-1k", \
#     "<(head -n 10000 ../casino-lab.txt)" using (6):1 title "casino-lab-10k"
