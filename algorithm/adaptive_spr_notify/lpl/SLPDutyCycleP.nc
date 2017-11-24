
#include "Lpl.h"
#include "DefaultLpl.h"

module SLPDutyCycleP
{
    provides
    {
        interface Init;
        interface LowPowerListening;
        interface Send;
        interface Receive;
        interface SplitControl;
        interface SLPDutyCycle;
    }
    uses
    {
        interface Random;
        interface Leds;

        interface MetricLogging;

        interface Send as SubSend;
        interface Receive as SubReceive;
        interface SplitControl as SubControl; // Csma

        interface CC2420Transmit as Resend;
        interface RadioBackoff;

        interface CC2420PacketBody;
        interface PacketAcknowledgements;

        interface State as SendState;
        interface State as RadioPowerState;
        interface State as SplitControlState;

        interface SystemLowPowerListening;

        interface Timer<TMilli> as OnTimer;
        interface Timer<TMilli> as OffTimer;
        interface Timer<TMilli> as SendDoneTimer;
        
        interface ReceiveIndicator as EnergyIndicator;
        //interface ReceiveIndicator as ByteIndicator;
        interface ReceiveIndicator as PacketIndicator;

        interface LocalTime<TMilli>;
        interface PacketTimeStamp<TMilli,uint32_t>;

        interface MessageTimingAnalysis as NormalMessageTimingAnalysis;
        interface MessageTimingAnalysis as FakeMessageTimingAnalysis;
    }
}
implementation
{
    /**
     * Radio Power State
     */
    enum {
        S_OFF, // off by default
        S_TURNING_ON,
        S_ON,
        S_TURNING_OFF,
    };
    
    /**
     * Send States
     */
    enum {
        S_IDLE,
        S_SENDING,
    };
    
    enum {
        ONE_MESSAGE = 0,
    };

    /** The message currently being sent */
    norace message_t *currentSendMsg;
    
    /** The length of the current send message */
    uint8_t currentSendLen;
    
    /** TRUE if the radio is duty cycling and not always on */
    bool dutyCycling;

    /** The number of times the CCA has been sampled in this wakeup period */
    uint16_t ccaChecks;

    uint16_t sleepInterval;
    
    /***************** Prototypes ***************/
    task void send();
    task void resend();
    task void startRadio();
    task void stopRadio();
    //task void getCca();
    
    void initializeSend();
    void startOnTimer();
    void startOffTimer();
    void startOffTimerFromMessage();
    bool isDutyCycling();
    bool finishSplitControlRequests();
    
    /***************** Init Commands ***************/
    command error_t Init.init()
    {
        dutyCycling = FALSE;
        return SUCCESS;
    }

    /**************** SLPDutyCycle *****************/

    command void SLPDutyCycle.normal_expected_interval(uint32_t expected_interval_ms)
    {
        call NormalMessageTimingAnalysis.expected_interval(expected_interval_ms);
    }

    command void SLPDutyCycle.fake_expected_interval(uint32_t expected_interval_ms)
    {
        call FakeMessageTimingAnalysis.expected_interval(expected_interval_ms);
    }

    command void SLPDutyCycle.received_Normal(message_t* msg, bool is_new)
    {
        const bool valid_timestamp = call PacketTimeStamp.isValid(msg);
        const uint32_t rcvd_time = valid_timestamp ? call PacketTimeStamp.timestamp(msg) : call LocalTime.get();

        call NormalMessageTimingAnalysis.received(rcvd_time, valid_timestamp, is_new);

        if (is_new)
        {
            startOffTimerFromMessage();
        }
    }

    command void SLPDutyCycle.received_Fake(message_t* msg, bool is_new)
    {
        const bool valid_timestamp = call PacketTimeStamp.isValid(msg);
        const uint32_t rcvd_time = valid_timestamp ? call PacketTimeStamp.timestamp(msg) : call LocalTime.get();

        //call FakeMessageTimingAnalysis.received(rcvd_time, valid_timestampm is_new);

        //LOG_STDOUT(0, "received Fake %d %" PRIu32 " expected %" PRIu32 "\n", valid_timestamp, rcvd_time, expected_delay);
    }

    /***************** StdControl Commands ****************/

    // Start duty cycling
    command error_t SplitControl.start()
    {
        if (call SplitControlState.isState(S_ON))
        {
            return EALREADY;
        }
        else if (call SplitControlState.isState(S_TURNING_ON))
        {
            return SUCCESS;
        }
        else if (!call SplitControlState.isState(S_OFF))
        {
            return EBUSY;
        }

        call SplitControlState.forceState(S_TURNING_ON);

        dutyCycling = TRUE;
        
        post startRadio();

        return SUCCESS;
    }
    
    // Stop duty cycling
    command error_t SplitControl.stop()
    {
        if (call SplitControlState.isState(S_OFF))
        {
            return EALREADY;
        }
        else if (call SplitControlState.isState(S_TURNING_OFF))
        {
            return SUCCESS;
        }
        else if (!call SplitControlState.isState(S_ON))
        {
            return EBUSY;
        }

        call SplitControlState.forceState(S_TURNING_OFF);
        
        dutyCycling = FALSE;

        // Start radio and leave on
        post startRadio();

        return SUCCESS;
    }
    
    /***************** Send Commands ***************/
    command error_t Send.send(message_t* msg, uint8_t len)
    {
        if (call SendState.requestState(S_LPL_SENDING) != SUCCESS)
        {
            return EBUSY;
        }

        currentSendMsg = msg;
        currentSendLen = len;
        
        // In case our off timer is running...
        //call OffTimer.stop();
        call SendDoneTimer.stop();
        
        if (call RadioPowerState.isState(S_ON))
        {
            initializeSend();
            return SUCCESS;
        }
        else
        {
            post startRadio();
        }
        
        return SUCCESS;
    }

    command error_t Send.cancel(message_t* msg)
    {
        if (currentSendMsg != msg)
        {
            return FAIL;
        }

        call SendState.toIdle();
        call SendDoneTimer.stop();

        return call SubSend.cancel(msg);
    }
    
    
    command uint8_t Send.maxPayloadLength()
    {
        return call SubSend.maxPayloadLength();
    }

    command void* Send.getPayload(message_t* msg, uint8_t len)
    {
        return call SubSend.getPayload(msg, len);
    }
    
    
    /***************** RadioBackoff Events ****************/
    async event void RadioBackoff.requestInitialBackoff(message_t* msg)
    {
        if ((call CC2420PacketBody.getMetadata(msg))->rxInterval > ONE_MESSAGE)
        {
            call RadioBackoff.setInitialBackoff(call Random.rand16() % (0x4 * CC2420_BACKOFF_PERIOD) + CC2420_MIN_BACKOFF);
        }
    }
    
    async event void RadioBackoff.requestCongestionBackoff(message_t* msg)
    {
        if ((call CC2420PacketBody.getMetadata(msg))->rxInterval > ONE_MESSAGE)
        {
            call RadioBackoff.setCongestionBackoff(call Random.rand16() % (0x3 * CC2420_BACKOFF_PERIOD) + CC2420_MIN_BACKOFF);
        }
    }
    
    // Request CCA for output message
    async event void RadioBackoff.requestCca(message_t* msg)
    {
    }
    
    
    /***************** SubControl Events ***************/
    event void SubControl.startDone(error_t error)
    {
        call RadioPowerState.forceState(S_ON);
        call Leds.led2On();

        finishSplitControlRequests();

        if (call SendState.isState(S_LPL_FIRST_MESSAGE) ||
            call SendState.isState(S_LPL_SENDING))
        {
            initializeSend();
        }

        /*if (finishSplitControlRequests())
        {
            return;
        }
        else if(isDutyCycling())
        {
            post getCca();
        }*/
    }
  
    event void SubControl.stopDone(error_t error)
    {
        call RadioPowerState.forceState(S_OFF);
        call Leds.led2Off();

        finishSplitControlRequests();

        call OffTimer.stop();

        /*if (call SendState.isState(S_LPL_FIRST_MESSAGE) ||
            call SendState.isState(S_LPL_SENDING))
        {
            // We're in the middle of sending a message; start the radio back up
            post startRadio();
        }
        else
        {
            call OffTimer.stop();
            call SendDoneTimer.stop();
        }*/
        
        /*if (finishSplitControlRequests())
        {
          return;
        }
        else if(isDutyCycling())
        {
            call OnTimer.startOneShot(sleepInterval);
        }*/
    }
    
    /***************** SubSend Events ***************/
    event void SubSend.sendDone(message_t* msg, error_t error)
    {
        switch(call SendState.getState())
        {
        case S_LPL_SENDING:
            if (call SendDoneTimer.isRunning()) 
            {
                if (!call PacketAcknowledgements.wasAcked(msg))
                {
                    post resend();
                    return;
                }
            }
            break;
            
        case S_LPL_CLEAN_UP:
            /**
             * We include this state so upper layers can't send a different message
             * before the last message gets done sending
             */
            break;
            
        default:
            break;
        }  
        
        call SendState.toIdle();
        call SendDoneTimer.stop();

        signal Send.sendDone(msg, error);
    }
    
    /***************** SubReceive Events ***************/
    /**
     * If the received message is new, we signal the receive event and
     * start the off timer.  If the last message we received had the same
     * DSN as this message, then the chances are pretty good
     * that this message should be ignored, especially if the destination address
     * as the broadcast address
     */
    event message_t *SubReceive.receive(message_t* msg, void* payload, uint8_t len)
    {
        return signal Receive.receive(msg, payload, len);
    }
    
    /***************** Timer Events ****************/
    
    /**
     * When this timer is running, that means we're sending repeating messages
     * to a node that is receive check duty cycling.
     */
    event void SendDoneTimer.fired()
    {
        if (call SendState.isState(S_LPL_SENDING))
        {
            // The next time SubSend.sendDone is signalled, send is complete.
            call SendState.forceState(S_LPL_CLEAN_UP);
        }
    }
    
    /***************** Resend Events ****************/
    /**
     * Signal that a message has been sent
     *
     * @param p_msg message to send.
     * @param error notifaction of how the operation went.
     */
    async event void Resend.sendDone(message_t* p_msg, error_t error)
    {
        // This is actually caught by SubSend.sendDone
    }
    
    
    /***************** Tasks ***************/
    task void send()
    {
        if (call SubSend.send(currentSendMsg, currentSendLen) != SUCCESS)
        {
            post send();
        }
    }
    
    task void resend()
    {
        if (call Resend.resend(TRUE) != SUCCESS)
        {
            post resend();
        }
    }
    
    task void startRadio()
    {
        const error_t startResult = call SubControl.start();

        if (startResult == SUCCESS)
        {
            call RadioPowerState.forceState(S_TURNING_ON);
        }
        else if (startResult == EALREADY)
        {
            // Already on, do nothing
        }
        else
        {
            // If the radio wasn't started successfully or already on, then try again
            post startRadio();
        }
    }
    
    task void stopRadio()
    {
        error_t stopResult;

        // Can only turn off if we are not sending 
        /*if (call SendState.getState() != S_LPL_NOT_SENDING)
        {
            return;
        }*/

        stopResult = call SubControl.stop();

        if (stopResult == SUCCESS)
        {
            call RadioPowerState.forceState(S_TURNING_OFF);
        }
        else if (stopResult == EALREADY)
        {
            // Already off, do nothing
        }
        else
        {
            post stopRadio();
        }
    }
    
    /***************** Functions ***************/
    void initializeSend()
    {
        const uint16_t remote_wakeup_interval = call LowPowerListening.getRemoteWakeupInterval(currentSendMsg);

        if (remote_wakeup_interval > ONE_MESSAGE)
        {
            if ((call CC2420PacketBody.getHeader(currentSendMsg))->dest == IEEE154_BROADCAST_ADDR)
            {
                call PacketAcknowledgements.noAck(currentSendMsg);
            }
            else
            {
                // Send it repetitively within our transmit window
                call PacketAcknowledgements.requestAck(currentSendMsg);
            }

            call SendDoneTimer.startOneShot(remote_wakeup_interval);
        }
                
        post send();
    }
    
    /***************** Timer Events ****************/
    event void OnTimer.fired()
    {        
        startOffTimer();

        post startRadio();

        /*if(isDutyCycling())
        {
            if (call RadioPowerState.isState(S_OFF))
            {
                ccaChecks = 0;
                
                // Turn on the radio only after the uC is fully awake.  ATmega128's 
                // have this issue when running on an external crystal.
                post getCca();
            } 
            else
            {
                // Someone else turned on the radio, try again in awhile
                call OnTimer.startOneShot(sleepInterval);
            }
        }*/
    }

    event void OffTimer.fired()
    {    
        /*
         * Only stop the radio if the radio is supposed to be off permanently
         * or if the duty cycle is on and our sleep interval is not 0
         */
        if (isDutyCycling())// || call SendState.getState() == S_LPL_NOT_SENDING)
        { 
            post stopRadio();

            startOnTimer();
        }
    }
    
    
    /***************** Tasks ****************/  
    /*task void getCca()
    {
        uint8_t detects = 0;

        if (!isDutyCycling())
        {
            return;
        }
            
        ccaChecks++;
        if (ccaChecks == 1)
        {
            // Microcontroller is ready, turn on the radio and sample a few times
            post startRadio();
            return;
        }

        atomic
        {
            for( ; ccaChecks < MAX_LPL_CCA_CHECKS && call SendState.isIdle(); ccaChecks++)
            {
                if (call PacketIndicator.isReceiving())
                {
                    startOffTimer();
                    return;
                }
                
                if (call EnergyIndicator.isReceiving())
                {
                    detects++;
                    if (detects > MIN_SAMPLES_BEFORE_DETECT)
                    {
                        startOffTimer();
                        return;
                    }

                    // Leave the radio on for upper layers to perform some transaction
                }
            }
        }
        
        if (call SendState.isIdle())
        {
            post stopRadio();
        }  
    }*/
    
    /**
     * @return TRUE if the radio should be actively duty cycling
     */
    bool isDutyCycling()
    {
        return dutyCycling;
    }

    bool finishSplitControlRequests()
    {
        const uint8_t state = call SplitControlState.getState();

        if (state == S_TURNING_OFF)
        {
            call SplitControlState.forceState(S_OFF);
            signal SplitControl.stopDone(SUCCESS);
            return TRUE;
        }
        else if (state == S_TURNING_ON)
        {
            // Starting while we're duty cycling first turns off the radio
            call SplitControlState.forceState(S_ON);
            signal SplitControl.startDone(SUCCESS);
            return TRUE;
        }
        else
        {
            return FALSE;
        }
    }

    void startOnTimer()
    {
        if (!call OnTimer.isRunning())
        {
            //const uint32_t now = call LocalTime.get();
            //const uint32_t last_group_start = call NormalMessageTimingAnalysis.last_group_start();
            const uint32_t next_group_wait = call NormalMessageTimingAnalysis.next_group_wait();
            const uint32_t early_wakeup_duration = call NormalMessageTimingAnalysis.early_wakeup_duration();
            const uint32_t awake_duration = call NormalMessageTimingAnalysis.awake_duration();

            const uint32_t start = next_group_wait - early_wakeup_duration - awake_duration;//(now - last_group_start);

            simdbg("stdout", "Starting on timer in %" PRIu32 "\n", start);
            call OnTimer.startOneShot(start);
        }
    }

    // OnTimer has just fired, start off timer
    void startOffTimer()
    {
        if (!call OffTimer.isRunning())
        {
            const uint32_t early_wakeup_duration = call NormalMessageTimingAnalysis.early_wakeup_duration();
            const uint32_t awake_duration = call NormalMessageTimingAnalysis.awake_duration();

            const uint32_t start = early_wakeup_duration + awake_duration;

            //simdbg("stdout", "Starting off timer in %" PRIu32 " (%" PRIu32 ",%" PRIu32 ",%" PRIu32 ")\n",
            //    start, awake_duration, now, last_group_start);
            simdbg("stdout", "Starting off timer 2 in %" PRIu32 "\n", start);
            call OffTimer.startOneShot(start);
        }
    }

    // Just received a message, consider when to turn off
    void startOffTimerFromMessage()
    {
        if (!call OffTimer.isRunning())
        {
            const uint32_t now = call LocalTime.get();
            const uint32_t last_group_start = call NormalMessageTimingAnalysis.last_group_start(); // This is the current group
            const uint32_t awake_duration = call NormalMessageTimingAnalysis.awake_duration();

            const uint32_t start = awake_duration - (now - last_group_start);

            simdbg("stdout", "Starting off timer 1 in %" PRIu32 " (%" PRIu32 ",%" PRIu32 ",%" PRIu32 ")\n",
                start, awake_duration, now, last_group_start);
            call OffTimer.startOneShot(start);
        }
    }
    

    /***************** LowPowerListening Commands ***************/
    command void LowPowerListening.setLocalWakeupInterval(uint16_t sleepIntervalMs) {}
    command uint16_t LowPowerListening.getLocalWakeupInterval() { return 0; }
    
    command void LowPowerListening.setRemoteWakeupInterval(message_t *msg, uint16_t intervalMs)
    {
        (call CC2420PacketBody.getMetadata(msg))->rxInterval = intervalMs;
    }
    command uint16_t LowPowerListening.getRemoteWakeupInterval(message_t *msg)
    {
        return (call CC2420PacketBody.getMetadata(msg))->rxInterval;
    }
}
