
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

        interface Timer<TMilli> as SendDoneTimer;
        
        interface ReceiveIndicator as EnergyIndicator;
        //interface ReceiveIndicator as ByteIndicator;
        interface ReceiveIndicator as PacketIndicator;

        interface LocalTime<TMilli>;

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
    
    // Send State
    enum {
        S_LPL_NOT_SENDING,    // DEFAULT
        S_LPL_SENDING,        // 1. Sending messages
        S_LPL_CLEAN_UP,       // 2. Clean up the transmission
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
    
    /***************** Prototypes ***************/
    task void send();
    task void resend();
    task void startRadio();
    task void stopRadio();
    
    void initializeSend();
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
        const uint32_t rcvd_time = call LocalTime.get();

        call NormalMessageTimingAnalysis.received(rcvd_time, is_new);
    }

    command void SLPDutyCycle.received_Fake(message_t* msg, bool is_new)
    {
        const uint32_t rcvd_time = call LocalTime.get();

        call FakeMessageTimingAnalysis.received(rcvd_time, is_new);
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
        
        call SendDoneTimer.stop();
        
        if (call RadioPowerState.isState(S_ON))
        {
            initializeSend();
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

        // Try to stop the radio if allowed
        post stopRadio();

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

        if (call SendState.isState(S_LPL_SENDING))
        {
            initializeSend();
        }
    }
  
    event void SubControl.stopDone(error_t error)
    {
        call RadioPowerState.forceState(S_OFF);
        call Leds.led2Off();

        finishSplitControlRequests();

        call SendDoneTimer.stop();

        if (call SendState.isState(S_LPL_SENDING))
        {
            // We're in the middle of sending a message; start the radio back up
            post startRadio();
        }
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

        // Attempt to turn the radio off if possible
        post stopRadio();

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
        if (!isDutyCycling() ||
            !call NormalMessageTimingAnalysis.can_turn_off() ||
            !call FakeMessageTimingAnalysis.can_turn_off() ||
            call SendState.getState() != S_LPL_NOT_SENDING)
        {
            return;
        }

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
    event void NormalMessageTimingAnalysis.on_timer_fired()
    {
        post startRadio();
    }

    event void FakeMessageTimingAnalysis.on_timer_fired()
    {
        post startRadio();
    }

    event void NormalMessageTimingAnalysis.off_timer_fired()
    {
        post stopRadio();
    }

    event void FakeMessageTimingAnalysis.off_timer_fired()
    {    
        post stopRadio();
    }
    
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
