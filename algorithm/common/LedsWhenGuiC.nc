
configuration LedsWhenGuiC
{
  provides interface Leds;
}
implementation
{
#if defined(SLP_USES_GUI_OUPUT) && SLP_USES_GUI_OUPUT
  components LedsC;
#else
  components NoLedsC as LedsC;
#endif

  Leds = LedsC;
}
