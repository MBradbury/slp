
def name():
    return __name__

def platform():
    """The hardware platform of the testbed"""
    return "telosb"

def nodes():
    """The list of nodes on the testbed and their information"""
    return (
        ('ailuropoda-1',    '137.205.115.103', 'b8:27:eb:0b:14:ce'), # Source
        ('ailuropoda-2',    '137.205.115.221', 'b8:27:eb:52:57:de'), # Sink

        # Others
        ('ailuropoda-3',    '', 'b8:27:eb:9b:85:9e'),
        ('ailuropoda-4',    '', 'b8:27:eb:c9:b7:04'),
        ('ailuropoda-5',    '', 'b8:27:eb:9c:0d:6c'),
        ('ailuropoda-6',    '', 'b8:27:eb:ad:8e:d2'),
        ('ailuropoda-7',    '', 'b8:27:eb:59:a4:ab'),
        ('ailuropoda-8',    '', 'b8:27:eb:13:64:d5'),
        ('ailuropoda-9',    '', 'b8:27:eb:95:90:2d'),
        ('ailuropoda-10',   '', 'b8:27:eb:29:82:fe'),
    )
