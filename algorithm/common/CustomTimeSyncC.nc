

generic configuration CustomTimeSyncC(typedef SyncMessage)
{
    provides interface CustomTimeSync<SyncMessage>;
    provides interface CustomTime;
}
implementation
{
    components new CustomTimeSyncP(SyncMessage) as App;

    CustomTimeSync = App;
    CustomTime = App;

    components LocalTimeMilliC;
    App.LocalTime -> LocalTimeMilliC;

    components MainC;
    App.Boot -> MainC;
}
