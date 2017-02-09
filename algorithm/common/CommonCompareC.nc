
module CommonCompareC
{
    provides interface Compare<am_addr_t> as Compare_am_addr_t;
}
implementation
{
    command bool Compare_am_addr_t.equals(const am_addr_t* a, const am_addr_t* b)
    {
        return *a == *b;
    }
}
