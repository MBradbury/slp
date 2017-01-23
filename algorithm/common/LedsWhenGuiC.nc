
configuration LedsWhenGuiC
{
  provides interface Leds;
}
implementation
{
#ifdef SLP_USES_GUI_OUPUT
  components LedsC;
#else
  components NoLedsC as LedsC;
#endif

  Leds = LedsC;
}
