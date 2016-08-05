=Algorithm Hierarchy=

protectionless

protectionless_spr

protectionless_ctp

template	->	adaptive	-> adaptive_spr			-> src_angle_adaptive_spr
                                                    -> adaptive_spr_phantom_hybrid

noforward

phantom		-> phantom_grow

phantom_chen

periodic	-> probrate

short_lived_fake_kamat

protectionless_tdma_das		-> tdma_das



=Algorithm Summaries=

==noforward==
Base algorithm to implement routing on.
Source nodes generate normal messages every period, but do no routing.
No SLP implemented here.

==protectionless==
Basic flooding algorithm with no SLP.

==protectionless_spr==
Basic single path routing from source to sink with no SLP.

==template==
Port of the fake source template SLP algorithm from JProwler to TinyOS.
Many fixed parameters, were used to do a search to find good parameter values.

==adaptive==
Modification of template to have parameters determined online.

==multi_src_adaptive==
Modification of adaptive to handle multiple sources.
(Not fully implemented)

==adaptive_spr==
Modification of adaptive to use a single path route of fake sources.
Aim to reduce energy usage, by reducing competition between fake sources.

==multi_src_adaptive_spr==
Modification of adaptive_spr to handle multiple sources.
(Not fully implemented)

==phantom==
Implementation of phantom flooding.

==phantom_grow==
Modification of phantom to use a bloom filter to choose next node.
Not all of the GROW algorithm has been implemented here.

==phantom_chen==
Chen Gu's implementation of phantom.

==periodic==
Global SLP privacy scheme, all nodes periodically broadcast.
If no normal message in queue then a fake message is sent instead.

==probrate==
Modification of periodic where an exponential distribution is used to determine next broadcast period.

==short_lived_fake_kamat==
Implementation of the short lived fake source algorithm by Kamat.
nodes randomly choose to broadcast fake messages after receiving a normal message.
