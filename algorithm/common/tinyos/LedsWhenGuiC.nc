
configuration LedsWhenGuiC
{
  provides interface Leds;
}
implementation
{
// Enable Led output if requested
#if defined(SLP_USES_GUI_OUPUT)
  components LedsC;
#else
  components NoLedsC as LedsC;
#endif

  Leds = LedsC;
}
