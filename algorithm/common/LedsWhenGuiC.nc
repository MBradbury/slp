
configuration LedsWhenGuiC
{
  provides interface Leds;
}
implementation
{
// Enable Led output if requested and also if there is no cost
// to use them in terms of serial logging
#if (defined(SLP_USES_GUI_OUPUT) && SLP_USES_GUI_OUPUT) || (defined(SLP_LEDS_RECORD_NO_SERIAL) && SLP_LEDS_RECORD_NO_SERIAL)
  components LedsC;
#else
  components NoLedsC as LedsC;
#endif

  Leds = LedsC;
}
