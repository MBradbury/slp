#!/usr/bin/python
# postprocessAOCnew.py
# Original Author: Victor Shnayder <shnayder at eecs.harvard.edu>
# Modifications for PowerTOSSIM 2.0 & nonlinear battery model by 
# Art O Cathain{tcd.ie}, and carbajor{tcd.ie}
# Postprocessing script that reads PowerTOSSIM-Z state transition log and
# computes power and energy numbers.
#

from __future__ import print_function, division

from sys import argv
import sys
import csv
import array
import random
import time

usage = """USAGE: postprocess.py [--help] [--debug] [--nosummary]
[--detail[=basename]]  [--maxmotes N]
[--simple] [--sb={0|1}] --em file trace_file

--help:              print this help message
--debug:             turn on debugging output
--nosummary:         avoid printing the summary to stdout
--detail[=basename]: for each mote, print a list of 'time,current' tuples
                to the file basename$moteid_current.csv (default basename='mote')
                Also prints a list of 'time,battery charge' pairs
                to the file basename$moteid_battery.csv
--em file:           use the energy model in file (default: micaZ_energy_model.txt)
--sb={0|1}:          Whether the motes have a sensor board or not. (default: 0)
--maxmotes:          The maximum of number of motes to support. 1000 by default.
--simfreq            Simulation frequency (default=10^10)
--simple:            Use a simple output format, suitable for machine parsing
--powercurses:       Output suitable for PowerCurses
--capacity:          total battery capacity (in mAh) per mote (default:2000)
--effTable           Name of battery efficiency vs current table
                     (default='EfficiencyTable.csv')
--recTable           Name of battery recovery probability vs capacity table
                     (default='RecoveryProbabilityTable.csv')

By default, uses energy model from energy_model.txt in the current directory,
prints summary.

trace_file must be from PowerTOSSIM 2.0. This script will not work with PowerTOSSIM 1.0!
"""

maxtime=-1
summary = 1
prettyprint = 1
detail = 0
lineno = 0   # The line number in the trace file
emfile = "models/power/micaZ_energy_model.txt"
simfreq = 10000000000 # frequency of TOSSIM used to generate the trace
tracefile = ""
model = {}      # The energy model (mappings such as CPU_ACTIVE->8.0)
state = [{}]    # The current state of execution ([mote][component])
total = [{}]   # The energy totals (in mJ)
battery = []   # The battery charge remaining (in mAh)
mote_died = []   # Time at which battery charge fell to < 0
prev_battery = []
battery_max = [] # Max charge to which battery can recover
eff_table_filename = "models/power/EfficiencyTable.csv" # table of battery efficiency vs current load
rec_table_filename = "models/power/RecoveryProbabilityTable.csv" # table of recovery probability vs battery remaining capacity

# Hmm... might not actually want 1000 open files.  I guess I could
# open and close each one after each write.  Or just keep all the
# logs in memory and then write them out one at a time.  For now, just
# open each file when necessary and leave it at that
dumpcurrent_file = []  
dumpcharge_file = []  
basename = 'mote'

voltage = None
battery_model_timestep = 0.0005 # time unit for markov model of battery recovery
current_cutoff = 0.1 # below this value (mA), battery has a chance of recovering charge
battery_total_charge = 2000.0 # mAh
battery_unit_of_charge = 0.000001 # mAh, added every 0.5ms if recovery takes place
prev_current = []
prev_time = []

maxmotes = 1000 #NB powercurses max 100
maxseen = 0
debug = 0
powercurses = 0
em = {}  # The energy model
sb = 0   # Whether there's a sensor board

#components = ["radio", "cpu", "cpu_cycles", "adc", "sensor", "led", "eeprom"]

# Types of total we want to track
totals = ["cpu", "radio", "adc", "leds", "sensor", "eeprom"]


def quit(showusage=0, error="Illegal arguments"):
    if error:
        print("Error: {}\n".format(error), file=sys.stderr)

    if showusage:
        print(usage, file=sys.stderr)
    sys.exit()


# Handle arguments-this can be rewritten with a dictionary of lambdas, but
# that's for later (or I can just use an existing module)
def parse_args():
    global summary, maxmotes, emfile, simfreq, tracefile, trace, argv, debug, basename, battery_total_charge
    global rec_table_filename,eff_table_filename,powercurses 
    global detail, prettyprint, sb
    argv = argv[1:]
    while argv:
        a=argv[0]
        if a == "--help":
            quit(1,"")
        elif a == "--nosummary":
            summary = 0
        elif a == "--simple":
            prettyprint = 0
        elif a.startswith("--detail"):
            detail = 1
            x=a.rfind('=')
            if x != -1:
                basename = a[x+1:]
                
        elif a.startswith("--sb="):
            t = a[5:]
            if t == "1":
                sb = 1
            elif t == "0":
                sb = 0
            else:
                quit(1)
            
                
        elif a == "--debug":
            debug = 1
        elif a == "--powercurses":
            powercurses = 1
        elif a == "--maxmotes":
            argv = argv[1:] # Consume this argument
            if not argv:
                quit(1)
            maxmotes = int(argv[0])
        elif a == "--simfreq":
            argv = argv[1:] # Consume this argument
            if not argv:
                quit(1)
            simfreq = int(argv[0])
        elif a == "--capacity":
            argv = argv[1:] # Consume this argument
            if not argv:
                quit(1)
            battery_total_charge = int(argv[0])
        elif a == "--effTable":
            argv = argv[1:] # Consume this argument
            if not argv:
                quit(1)
            eff_table_filename = argv[0]
        elif a == "--recTable":
            argv = argv[1:] # Consume this argument
            if not argv:
                quit(1)
            rec_table_filename = argv[0]
        elif a == "--em":
            argv=argv[1:]  # Consume this argument
            if not argv:
                quit(1)
            emfile = argv[0]  # Get the filename parameter
        else:
            tracefile = a
        argv = argv[1:]


    if tracefile == "":
        quit(1,"No tracefile specified")

    try:
        trace = open(tracefile)
    except IOError:
        quit(0,"Couldn't open trace file '"+tracefile+"'")


######### State initialization functions ##############

# Read energy model from file
def read_em():
    global model,lineno,em
    # Reads and parses the energy model file
    try:
        model = open(emfile)
    except IOError:
        quit(0,"Couldn't open energy model file '"+emfile+"'")

    l = model.readline()
    lineno += 1
    while l:
        l=l.strip()
        # Parse the line, skipping comments, blank lines
        if l == '' or l[0] == '#':
            l = model.readline()
            continue
        # print "splitting line '%s'" % l
        l=l.split('#')[0] # AOC: ignore end of line comments
        (k,v) = l.split()
        em[k]=float(v)
        l = model.readline()
        lineno += 1
    
def initstate():
    global state, total, battery, prev_battery, battery_max, voltage, prev_current, prev_time, dumpcurrent_file, dumpcharge_file
    global efftable, rectable, battery_total_charge, mote_died # AOC: added battery
    read_em()
    # initialize the various lists...
    state = [None] * maxmotes
    total = [None] * maxmotes
    battery = [None] * maxmotes
    mote_died = [None] * maxmotes
    prev_battery = [None] * maxmotes
    battery_max = [None] * maxmotes
    prev_current = [None] * maxmotes
    prev_time = [0] * maxmotes
    dumpcurrent_file = [None] * maxmotes
    dumpcharge_file = [None] * maxmotes
    voltage = em['VOLTAGE']
    
    for mote in range(maxmotes):
        # Init each mote with base values
        state[mote] = {'radio':{'on':0, 'tx':0,
                                'txpower':em['RADIO_DEFAULT_POWER']}, 
                       'cpu': 'CPU_IDLE',
                       'cpu_cycles':0,
                       'adc': 0,
                       'adc_on': 0,
          # For the moment, all the same, but can be changed later
                       'sensor_board': sb,  
                       'sensor': {},
                       'led': {},
                       'eeprom': {'read':0, 'write':0, 'sync':0, 'erase':0}}
        total[mote] = {}
        battery[mote] = {}
        prev_battery[mote] = {}
        battery_max[mote] = {}
        battery[mote] = battery_total_charge
        mote_died[mote] = -1
        prev_battery[mote] = battery_total_charge
        battery_max[mote] = battery_total_charge
        prev_current[mote]={}
        for k in totals:
            prev_current[mote][k] = 0
        prev_current[mote]['total']=0
        for t in totals:
            total[mote][t] = 0
    efftable=EfficiencyTable(eff_table_filename)
    rectable=RecoveryTable(rec_table_filename)

######### Non-linear battery model ######### 

class EfficiencyTable:
    # battery efficiency vs current
    def __init__(self, eff_table_filename):
        self.colCurrentDemand = array.array('f')
        self.colEfficiency = array.array('f')
        reader = csv.reader(open(eff_table_filename,"rb"))
        reader.next() # ignore first line
        i=0
        for row in reader:
            self.colCurrentDemand.append(float(row[0]))
            self.colEfficiency.append(float(row[1]))
            i+=1
        self.tableSize=i
        if debug:
            print('Efficiency table loaded, size={}'.format(self.tableSize))

    def __str__(self):
        i=0
        retString="Current Demand\tEfficiency\n"
        while (i<self.tableSize):
            retString += str(self.colCurrentDemand[i]) + "\t" + str(self.colEfficiency[i]) + "\n"
            i+=1
        return retString

    def getEfficiency(self, currentDemand):
        i=0
        while (self.colCurrentDemand[i]<currentDemand and (i+1)<self.tableSize):
            i+=1
        return self.colEfficiency[i]

class RecoveryTable:
    # battery recovery probability vs remaining capacity
    def __init__(self, rec_table_filename):
        self.colCapacityRemaining = array.array('f')
        self.colRecoveryProbability = array.array('f')
        reader = csv.reader(open(rec_table_filename,"rb"))
        reader.next() # ignore first line
        i=0
        for row in reader:
            self.colCapacityRemaining.append(float(row[0]))
            self.colRecoveryProbability.append(float(row[1]))
            i+=1
        self.tableSize=i
        if debug:
            print('Recovery table loaded, size={}'.format(self.tableSize))

    def __str__(self):
        i=0
        retString="Capacity Remaining\tRecovery Probability\n"
        while i < self.tableSize:
            retString += str(self.colCapacityRemaining[i]) + "\t" + str(self.colRecoveryProbability[i]) + "\n"
            i+=1
        return retString

    def getRecoveryProbability(self, capacityRemaining):
        i=0
        #print "getRecoveryProbability:" + str(capacityRemaining)
        while (self.colCapacityRemaining[i]<capacityRemaining):
            i+=1
        #print str(i) + ":" + str(self.colRecoveryProbability[i])
        return self.colRecoveryProbability[i]

def testTables():
     global efftable, rectable
     print(efftable)
     print(rectable)
     print(str(rectable.getRecoveryProbability(0.1)))
     print(str(rectable.getRecoveryProbability(1)))

######################## Current computation #######################

def get_cpu_current(mote):
    #return em["CPU_"+state[mote]["cpu"]]
    return em[state[mote]["cpu"]] # CPU_ now included in trace

def get_sensor_current(mote):
    mystate = state[mote]['sensor']
    total = 0
    # If the sensor board is plugged it draws a constant base current 
    if state[mote]['sensor_board']:
        total += em.get('SENSOR_BOARD')
    for (type,value) in mystate.items():
        if value==1:
            total += em.get("SENSOR_"+type, 0)
    return total

def get_adc_current(mote):
    # FIXME: if we discover that sampling actually takes energy
    # in addition to the base cost, add it in if sampling.
    if state[mote]['adc_on']:
        return em['ADC']
    else:
        return 0

def tx_current(x):
    """ Return the radio current for transmit power x """
    return em["RADIO_TX_"+("%02X" % x)]

def get_radio_current(mote):
    #the state is:  {'on':ON/OFF,'tx': TX/RX,'txpower':PowerLevel}
    mystate = state[mote]['radio']
    if mystate['on']:
        if mystate['tx']:
            return tx_current(mystate['txpower'])
        else:
            return em['RADIO_RX']
    else:
        return 0
        
def get_leds_current(mote):
    # Count how many leds are on:
    numon = state[mote]['led'].values().count(1)
    return numon * em['LED']

def get_eeprom_current(mote):
    # Assumes that EEPROM can't read and write at the same time
    # I believe that's correct
    if state[mote]['eeprom']['read']:
        return em['EEPROM_READ']
    if state[mote]['eeprom']['write']:
        return em['EEPROM_WRITE']
    if state[mote]['eeprom']['sync']:
        return em['EEPROM_SYNC']
    if state[mote]['eeprom']['erase']:
       return em['EEPROM_ERASE']
    return 0
    

# There should probably be one entry for each key of the totals
# defined above
current_fn_map = {
    'cpu': get_cpu_current,
    'radio': get_radio_current,
    'adc': get_adc_current,
    'leds':get_leds_current,
    'sensor':get_sensor_current,
    'eeprom':get_eeprom_current}


def get_current(mote):
    total = 0
    for k in current_fn_map.keys():
        total += current_fn_map[k](mote)
    return total

def print_currents():
    for m in range(maxseen+1):
        print("mote %d: current %f" % (m, get_current(m)))


######################## Event processing ##########################

# The handlers should just update the state.  Other functions are
# responsible for keeping track of totals.

def cpu_cycle_handler(mote, time, newstate):
    # AOC: NOT IMPLEMENTED
    # the cpu cycle messages always have a single number, which is
    # the total since beginning of execution
    global state
    state[mote]['cpu_cycles'] = float(newstate[1])

def cpu_state_handler(mote, time, newstate):
    # Here are the possible states, from PowerStateM.nc:
    #        char cpu_power_state[8][20] = {"IDLE", \
    #                                       "ADC_NOISE_REDUCTION", \
    #                                       "POWER_DOWN", \
    #                                       "POWER_SAVE", \
    #                                       "RESERVED", \
    #                                       "RESERVED", \
    #                                       "STANDBY", \
    #                                       "EXTENDED_STANDBY"}
    # The energy model should have keys for each of the form CPU_`state`
    global state
    state[mote]["cpu"] = newstate[0]

def adc_handler(mote, time, newstate):
    global state
    #FIXME: The ADC has to be on for any ADC event to work-check this
    action = newstate[1]
    if action == 'SAMPLE':
        state[mote]["adc"] = 1
    elif action == 'DATA_READY':
        state[mote]["adc"] = 0
    elif action == 'ON':
        state[mote]["adc_on"] = 1
    elif action == 'OFF':
        state[mote]["adc_on"] = 0
    else:
        quit(0,"Line %d: Syntax error: adc action %s unknown" % (lineno,action))

def radio_state_handler(mote, time, newstate):# AOC: updated
    """
    The possible values for newstate:
    ON  - turn radio on. 
    OFF - turn radio off.
    SEND_MESSAGE,ON - start sending
                ,OFF - finish sending
    RECV_MESSAGE,DONE - received message. Not used; radio is assumed to always be in
                    receive mode (and hence receive power consumption) when on, 
                    unless transmitting
    SetRFPower XX  for some hex value of XX-there should be an
    energy model entry for RADIO_TX_XX
    
    Thus, the state for the radio is:
    {'on':ON/OFF,'tx': TX/RX,'txpower':PowerLevel}
    """
    global state
    oldstate = state[mote]['radio']
    op = newstate[0]
    if op == "ON":
        # Parameters are set to defaults when turning on
        oldstate['on'] = 1
        oldstate['tx'] = 0 # Defaults to RX mode
        oldstate['txpower'] = em['RADIO_DEFAULT_POWER']
    elif op == "OFF": 
        oldstate['on'] = 0
    elif op == "SetRFPower":
        oldstate['txpower'] = int(newstate[2],16)  # must be a hex number
    elif op == "SEND_MESSAGE":
        opOnOff = newstate[1]
        # The mica(1) stack, doesn't explicitly turn radio on, so
        # TX/RX transitions also turn it on.  Should be valid for micaZ
        # as well, unless it tries to send while the radio is off, which
        # probably qualifies as a bug
        oldstate['on'] = 1 
        if opOnOff=='ON':
            oldstate['tx'] = 1
        else:
        # leave radio in receive state once sending is done
            oldstate['tx'] = 0
    elif op == "RECV_MESSAGE": # even if RECV_MESSAGE is DONE, means radio is switched on at least
        oldstate['on'] = 1
        oldstate['tx'] = 0
    else:
        quit(0,"Line %d: Syntax error: radio state %s unknown" % (lineno,op))
    

def led_state_handler(mote, time, newstate): # AOC: updated
    """ The state for the LEDs is pretty simple:
        They start out off, and here we just keep track of which are on
        in a dictionary.  So the state[mote]['led'] looks like
        {'LED0':onoff, 'LED1':onoff, 'LED2':onoff}
    """
    global state,debug
    ledno = newstate[0]
    ledstate = newstate[1]
    if debug:
        print("time:%.0f led:%s state:%s"%(time,ledno,ledstate))
    if ledstate=="OFF":
        state[mote]['led'][ledno]=0
    else:
        assert ledstate=="ON"
        state[mote]['led'][ledno]=1

def sensor_state_handler(mote, time, newstate): # AOC: sorta updated but not tested
    global state
    # If we're doing sensor stuff, there must be a sensor board:
    type = newstate[0]
    action = newstate[1]
    if action == 'ON':
        state[mote]['sensor'][type] = 1
    elif action == 'OFF':
        state[mote]['sensor'][type] = 0
    else:
        quit(0, "Line %d: Syntax error: sensor state %s unknown"
             % (lineno, action))

def eeprom_state_handler(mote, time, newstate):
    global state
    type = newstate[0]
    action = newstate[1]
    if type == 'READ':
        if action == 'START':
            state[mote]['eeprom']['read'] = 1
        elif action == 'STOP':
            state[mote]['eeprom']['read'] = 0
        else:
            quit(0, "Line %d: Syntax error: EEPROM READ action %s unknown"
             % (lineno, action))
    elif type == 'WRITE':
        if action == 'START':
            state[mote]['eeprom']['write'] = 1
        elif action == 'STOP':
            state[mote]['eeprom']['write'] = 0
        else:
            quit(0, "Line %d: Syntax error: EEPROM WRITE action %s unknown"
             % (lineno, action))
    elif type == 'SYNC':
        if action == 'START':
            state[mote]['eeprom']['sync'] = 1
        elif action == 'STOP': 
            state[mote]['eeprom']['sync'] = 0
        else:
            quit(0, "Line %d: Syntax error: EEPROM SYNC action %s unknown"
             % (lineno, action))
    elif type == 'ERASE':
        if action == 'START':
            state[mote]['eeprom']['erase'] = 1
        elif action == 'STOP':
            state[mote]['eeprom']['erase'] = 0
        else:
            quit(0, "Line %d: Syntax error: EEPROM ERASE action %s unknown"
             % (lineno, action))
    else:
        quit(0, "Line %d: Syntax error: EEPROM TYPE %s unknown"
             % (lineno, type))

# A table of event type to the appropriate handler
event_handler = {'CPU_CYCLES'  :    cpu_cycle_handler,
                 'CPU_STATE'   :    cpu_state_handler,
                 'ADC'  :          adc_handler,
                 'RADIO_STATE' :  radio_state_handler,
                 'LED_STATE'   :    led_state_handler,
                 'SENSOR_STATE': sensor_state_handler,
                 'EEPROM'      : eeprom_state_handler}

def time_diff(t_from, t_to):
    """Returns the difference, in seconds from 't_from' to 't_to', where both
    are expressed in simulation ticks """
    global simfreq
    return (float(t_to) - float(t_from))/simfreq

# Updates every total for every timestep.  This is inefficient,
# because if the radio is on for 100 events, there's no need to do 100
# small adds But it's simpler this way.  Can fix it (by making
# prev_time parametrized by total type) if it's a problem
#
# AOC: here is where we do the battery modelling.

def update_totals(time):
    global total, battery_max, prev_battery,efftable,rectable, mote_died
    for m in range(maxseen+1):
        if (battery[m]<0 and mote_died[m] == -1):
            mote_died[m]=time
        prev_battery[m]=battery[m]
        current_drawn=0
        for t in totals:
            td = time_diff(prev_time[m], time)
            total[m][t] += td * prev_current[m][t] * voltage
            current_drawn += prev_current[m][t]
        if (current_drawn>current_cutoff):  
            battery[m] -= td / 3600 * current_drawn / efftable.getEfficiency(current_drawn) # rate capacity effect
        else:
            td_remaining=td
            if (rectable.getRecoveryProbability(battery[m]/battery_total_charge))>0: 
                # don't bother with this step if no recovery probability
                while td_remaining > 0:
                    if (random.random()<rectable.getRecoveryProbability(battery[m]/battery_total_charge)): # recovery effect
                        battery[m] += battery_unit_of_charge
                    if (battery[m]>battery_max[m]):
                        battery[m]=battery_max[m]
                    td_remaining-=battery_model_timestep
                
        #battery[m] -= td / 3600 * current_drawn # naive linear model 

def update_currents(time):
    global prev_time, prev_current
    for m in range(maxseen+1):
        prev_time[m]=time
        for t in totals:
            prev_current[m][t] = current_fn_map[t](m)


def dump_currents(mote,time):
    global dumpcharge_file, dumpcurrent_file, debug
    m=mote
    if not dumpcurrent_file[m]:
        # Open file for current
        dumpcurrent_file[m] = open(basename + str(m)+"_current.csv", "w")
        # Write the header
        dumpcurrent_file[m].write("time,");
        for x in ['total'] + totals:
            dumpcurrent_file[m].write("%s," % x)
        dumpcurrent_file[m].write("\n")
        # Open file for battery
        dumpcharge_file[m] = open(basename + str(m)+"_battery.csv", "w")
        dumpcharge_file[m].write("time,charge (mAh)")
        dumpcharge_file[m].write("\n")


    if debug: print(prev_current[m]['total'], get_current(m))
    if prev_current[m]['total'] != get_current(m):
        # To make a square wave, print the previous currents up to "just
        # before now", then print the new currents
        tm = float(time) / simfreq - 0.000001
        dumpcurrent_file[m].write("%.6f," % tm)
        for t in ['total'] + totals:
            c = float(prev_current[m][t])
            dumpcurrent_file[m].write("%.6f," % c)
        dumpcurrent_file[m].write("\n");
        
        tm = float(time)/simfreq
        c = get_current(m)
        prev_current[m]['total'] = c
        dumpcurrent_file[m].write("%.6f,%.6f," % (tm,c))
        for t in totals:
            c = current_fn_map[t](m)
            dumpcurrent_file[m].write("%.6f," % c);
        dumpcurrent_file[m].write("\n");

    # write charge 
    if prev_battery[m]!=battery[m]:
        tm = float(time)/simfreq
        dumpcharge_file[m].write("%.6f," % tm)
        dumpcharge_file[m].write("%.6f" % battery[mote])
        dumpcharge_file[m].write("\n");


dbg_unknown_event_types = {}

# Takes a line, parses it, and performs the appropriate changes to the
# mote state and totals.
# The line format we expect consists of whitespace separated fields:
# DATA can consist of more than 1 field, but the rest must not
# junk POWER: Mote # STATE_TYPE {DATA...} at TIME(in cycles)
def handle_event(l):
    global maxseen, maxtime, detail, powercurses, debug

    l=l.replace("\n","");
    #if debug: print lineno, l
    event = l.split(',')
    event0 = event[0].split(':')
    #print event1;
    mote = (int)(event0[0].strip('DEBUG() '))
    time = (float)(event0[1])
    if (time>maxtime):
        maxtime=time
    if debug:
        print("mote: %d, time: %.0f" % (mote,time))
    # Check if this is a power event
    # if event[1] != "POWER:":
    #     return
    
    if(mote > maxseen): maxseen = mote
    if debug:
        print("handling event: '%s'" % l)
        print(event)
    if event[1] in event_handler:
        # Update the totals up to just before this event
        update_totals(time)
        # Update the state due to this event
        event_handler[event[1]](mote,time,event[2:])
        if detail:
            # At this point, the state is updated, but still have the old
            # current values
            dump_currents(mote,time)
        # Update the prev_current values
        update_currents(time)
        
    else:
        global dbg_unknown_event_types
        if not event[1] in dbg_unknown_event_types:
            print("Don't know how to handle "+event[1]+" events")
            dbg_unknown_event_types[event[1]] = 1
    if powercurses: 
        print("POWERCURSES,%.6f,%d,%.2f" % (time/simfreq,mote,battery[mote]/battery_total_charge*100))



########################  "Main" code ###################

def print_summary():
    global total, battery, mote_died
    global maxseen, battery_total_charge,eff_table_filename,rec_table_filename,efftable,rectable, tracefile
    if prettyprint:
        print("trace file used: " + tracefile)
        print("energy model used: " + emfile)
        print("maxseen %d" % maxseen)
        print("mote battery starting energy: %.0f mJ" % (battery_total_charge * voltage * 3600))

    for mote in range(maxseen+1):
        sum = 0
        if not prettyprint:
            s = str(mote)+"   "
        for t in totals:
            if prettyprint:
                print("Mote %d, %s total: %.1f" % (mote, t, total[mote][t]))
            else:
                s += "%.4f" % total[mote][t]
                s += "   "
            sum += total[mote][t]
        cpu_active_e = state[mote]['cpu_cycles'] * voltage * em['CPU_ACTIVE']/em['CPU_FREQ']
        if prettyprint: 
            print("Mote %d, cpu_cycle total: %.1f" % (mote, cpu_active_e))
        else:
            s += "%.4f" % cpu_active_e
            s += "   "
        sum += cpu_active_e
        if prettyprint:
            print("Mote %d, Total energy used: %.0f" %(mote, sum))
            #print("Mote %d, Battery energy used: %.0f" %(mote, battery_total_charge * voltage * 3600 - battery[mote]*voltage*3600))
            print("Mote %d, Battery energy remaining (linear): %.0f" %(mote, battery_total_charge*voltage*3600-sum))
            print("Mote %d, Battery energy remaining: %.0f" %(mote, battery[mote]*voltage*3600))
            print("Mote %d, Battery mAh remaining: %.2f" %(mote, battery[mote]))
            if mote_died[mote] > 0:
                print("Mote %d, Mote ran out of battery at time: %.1f" %(mote, mote_died[mote]/simfreq ))
            print("")
        else:
            s += "%.4f" % sum
            s += "   "
            s += "%.4f" % battery[mote]
            print(s)


if __name__=='__main__':
    start_time=time.time()
    parse_args()
    initstate()
    #testTables()
    #sys.exit()
    lineno = 1
    l=trace.readline()
    while l:
        handle_event(l)
        lineno += 1
        l = trace.readline()

    if summary:
        print_summary()
        print("Simulated seconds: %.1f" % (maxtime/simfreq))
        print("Real seconds: %.1f" % (time.time()-start_time))


    


