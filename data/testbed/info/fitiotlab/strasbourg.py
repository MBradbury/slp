# Note this file was generated by ./scripts/fetch_fitiotlab_topologies.py.
# Please make changes to that script instead of editing this file.

from itertools import groupby, count

import numpy as np

from simulator.Topology import Topology

class Strasbourg(Topology):
    """The layout of nodes on the Strasbourg testbed, see: https://www.iot-lab.info/testbed/maps.php?site=strasbourg"""

    platform = "wsn430v13"

    def __init__(self, subset=None):
        super(Strasbourg, self).__init__()
        
        self.nodes[1] = np.array((0.0, 9.0, 0.5), dtype=np.float64)
        self.nodes[2] = np.array((0.0, 9.0, 1.5), dtype=np.float64)
        self.nodes[3] = np.array((0.0, 9.0, 2.5), dtype=np.float64)
        self.nodes[4] = np.array((1.0, 9.0, 0.5), dtype=np.float64)
        self.nodes[5] = np.array((1.0, 9.0, 1.5), dtype=np.float64)
        self.nodes[6] = np.array((1.0, 9.0, 2.5), dtype=np.float64)
        self.nodes[7] = np.array((2.0, 9.0, 0.5), dtype=np.float64)
        self.nodes[8] = np.array((2.0, 9.0, 1.5), dtype=np.float64)
        self.nodes[9] = np.array((2.0, 9.0, 2.5), dtype=np.float64)
        self.nodes[10] = np.array((3.0, 9.0, 0.5), dtype=np.float64)
        self.nodes[11] = np.array((3.0, 9.0, 1.5), dtype=np.float64)
        self.nodes[12] = np.array((3.0, 9.0, 2.5), dtype=np.float64)
        self.nodes[13] = np.array((4.0, 9.0, 0.5), dtype=np.float64)
        self.nodes[14] = np.array((4.0, 9.0, 1.5), dtype=np.float64)
        self.nodes[15] = np.array((4.0, 9.0, 2.5), dtype=np.float64)
        self.nodes[16] = np.array((5.0, 9.0, 0.5), dtype=np.float64)
        self.nodes[17] = np.array((5.0, 9.0, 1.5), dtype=np.float64)
        self.nodes[18] = np.array((5.0, 9.0, 2.5), dtype=np.float64)
        self.nodes[19] = np.array((6.0, 9.0, 0.5), dtype=np.float64)
        self.nodes[20] = np.array((6.0, 9.0, 1.5), dtype=np.float64)
        self.nodes[21] = np.array((6.0, 9.0, 2.5), dtype=np.float64)
        self.nodes[22] = np.array((7.0, 9.0, 0.5), dtype=np.float64)
        self.nodes[23] = np.array((7.0, 9.0, 1.5), dtype=np.float64)
        self.nodes[25] = np.array((0.0, 8.0, 0.5), dtype=np.float64)
        self.nodes[26] = np.array((0.0, 8.0, 1.5), dtype=np.float64)
        self.nodes[27] = np.array((0.0, 8.0, 2.5), dtype=np.float64)
        self.nodes[28] = np.array((1.0, 8.0, 0.5), dtype=np.float64)
        self.nodes[29] = np.array((1.0, 8.0, 1.5), dtype=np.float64)
        self.nodes[30] = np.array((1.0, 8.0, 2.5), dtype=np.float64)
        self.nodes[31] = np.array((2.0, 8.0, 0.5), dtype=np.float64)
        self.nodes[32] = np.array((2.0, 8.0, 1.5), dtype=np.float64)
        self.nodes[33] = np.array((2.0, 8.0, 2.5), dtype=np.float64)
        self.nodes[34] = np.array((3.0, 8.0, 0.5), dtype=np.float64)
        self.nodes[35] = np.array((3.0, 8.0, 1.5), dtype=np.float64)
        self.nodes[36] = np.array((3.0, 8.0, 2.5), dtype=np.float64)
        self.nodes[37] = np.array((4.0, 8.0, 0.5), dtype=np.float64)
        self.nodes[38] = np.array((4.0, 8.0, 1.5), dtype=np.float64)
        self.nodes[39] = np.array((4.0, 8.0, 2.5), dtype=np.float64)
        self.nodes[40] = np.array((5.0, 8.0, 0.5), dtype=np.float64)
        self.nodes[41] = np.array((5.0, 8.0, 1.5), dtype=np.float64)
        self.nodes[42] = np.array((5.0, 8.0, 2.5), dtype=np.float64)
        self.nodes[43] = np.array((6.0, 8.0, 0.5), dtype=np.float64)
        self.nodes[44] = np.array((6.0, 8.0, 1.5), dtype=np.float64)
        self.nodes[45] = np.array((6.0, 8.0, 2.5), dtype=np.float64)
        self.nodes[46] = np.array((7.0, 8.0, 0.5), dtype=np.float64)
        self.nodes[47] = np.array((7.0, 8.0, 1.5), dtype=np.float64)
        self.nodes[48] = np.array((7.0, 8.0, 2.5), dtype=np.float64)
        self.nodes[49] = np.array((0.0, 7.0, 0.5), dtype=np.float64)
        self.nodes[50] = np.array((0.0, 7.0, 1.5), dtype=np.float64)
        self.nodes[51] = np.array((0.0, 7.0, 2.5), dtype=np.float64)
        self.nodes[52] = np.array((1.0, 7.0, 0.5), dtype=np.float64)
        self.nodes[53] = np.array((1.0, 7.0, 1.5), dtype=np.float64)
        self.nodes[54] = np.array((1.0, 7.0, 2.5), dtype=np.float64)
        self.nodes[55] = np.array((2.0, 7.0, 0.5), dtype=np.float64)
        self.nodes[56] = np.array((2.0, 7.0, 1.5), dtype=np.float64)
        self.nodes[57] = np.array((2.0, 7.0, 2.5), dtype=np.float64)
        self.nodes[58] = np.array((3.0, 7.0, 0.5), dtype=np.float64)
        self.nodes[60] = np.array((3.0, 7.0, 2.5), dtype=np.float64)
        self.nodes[61] = np.array((4.0, 7.0, 0.5), dtype=np.float64)
        self.nodes[62] = np.array((4.0, 7.0, 1.5), dtype=np.float64)
        self.nodes[63] = np.array((4.0, 7.0, 2.5), dtype=np.float64)
        self.nodes[64] = np.array((5.0, 7.0, 0.5), dtype=np.float64)
        self.nodes[65] = np.array((5.0, 7.0, 1.5), dtype=np.float64)
        self.nodes[66] = np.array((5.0, 7.0, 2.5), dtype=np.float64)
        self.nodes[67] = np.array((6.0, 7.0, 0.5), dtype=np.float64)
        self.nodes[68] = np.array((6.0, 7.0, 1.5), dtype=np.float64)
        self.nodes[69] = np.array((6.0, 7.0, 2.5), dtype=np.float64)
        self.nodes[70] = np.array((7.0, 7.0, 0.5), dtype=np.float64)
        self.nodes[71] = np.array((7.0, 7.0, 1.5), dtype=np.float64)
        self.nodes[72] = np.array((7.0, 7.0, 2.5), dtype=np.float64)
        self.nodes[73] = np.array((0.0, 6.0, 0.5), dtype=np.float64)
        self.nodes[74] = np.array((0.0, 6.0, 1.5), dtype=np.float64)
        self.nodes[75] = np.array((0.0, 6.0, 2.5), dtype=np.float64)
        self.nodes[76] = np.array((1.0, 6.0, 0.5), dtype=np.float64)
        self.nodes[77] = np.array((1.0, 6.0, 1.5), dtype=np.float64)
        self.nodes[78] = np.array((1.0, 6.0, 2.5), dtype=np.float64)
        self.nodes[79] = np.array((2.0, 6.0, 0.5), dtype=np.float64)
        self.nodes[80] = np.array((2.0, 6.0, 1.5), dtype=np.float64)
        self.nodes[81] = np.array((2.0, 6.0, 2.5), dtype=np.float64)
        self.nodes[82] = np.array((3.0, 6.0, 0.5), dtype=np.float64)
        self.nodes[83] = np.array((3.0, 6.0, 1.5), dtype=np.float64)
        self.nodes[84] = np.array((3.0, 6.0, 2.5), dtype=np.float64)
        self.nodes[85] = np.array((4.0, 6.0, 0.5), dtype=np.float64)
        self.nodes[86] = np.array((4.0, 6.0, 1.5), dtype=np.float64)
        self.nodes[87] = np.array((4.0, 6.0, 2.5), dtype=np.float64)
        self.nodes[88] = np.array((5.0, 6.0, 0.5), dtype=np.float64)
        self.nodes[89] = np.array((5.0, 6.0, 1.5), dtype=np.float64)
        self.nodes[90] = np.array((5.0, 6.0, 2.5), dtype=np.float64)
        self.nodes[91] = np.array((6.0, 6.0, 0.5), dtype=np.float64)
        self.nodes[92] = np.array((6.0, 6.0, 1.5), dtype=np.float64)
        self.nodes[93] = np.array((6.0, 6.0, 2.5), dtype=np.float64)
        self.nodes[94] = np.array((7.0, 6.0, 0.5), dtype=np.float64)
        self.nodes[95] = np.array((7.0, 6.0, 1.5), dtype=np.float64)
        self.nodes[96] = np.array((7.0, 6.0, 2.5), dtype=np.float64)
        self.nodes[97] = np.array((0.0, 5.0, 0.5), dtype=np.float64)
        self.nodes[98] = np.array((0.0, 5.0, 1.5), dtype=np.float64)
        self.nodes[99] = np.array((0.0, 5.0, 2.5), dtype=np.float64)
        self.nodes[100] = np.array((1.0, 5.0, 0.5), dtype=np.float64)
        self.nodes[101] = np.array((1.0, 5.0, 1.5), dtype=np.float64)
        self.nodes[102] = np.array((1.0, 5.0, 2.5), dtype=np.float64)
        self.nodes[103] = np.array((2.0, 5.0, 0.5), dtype=np.float64)
        self.nodes[104] = np.array((2.0, 5.0, 1.5), dtype=np.float64)
        self.nodes[105] = np.array((2.0, 5.0, 2.5), dtype=np.float64)
        self.nodes[106] = np.array((3.0, 5.0, 0.5), dtype=np.float64)
        self.nodes[107] = np.array((3.0, 5.0, 1.5), dtype=np.float64)
        self.nodes[108] = np.array((3.0, 5.0, 2.5), dtype=np.float64)
        self.nodes[109] = np.array((4.0, 5.0, 0.5), dtype=np.float64)
        self.nodes[110] = np.array((4.0, 5.0, 1.5), dtype=np.float64)
        self.nodes[111] = np.array((4.0, 5.0, 2.5), dtype=np.float64)
        self.nodes[112] = np.array((5.0, 5.0, 0.5), dtype=np.float64)
        self.nodes[113] = np.array((5.0, 5.0, 1.5), dtype=np.float64)
        self.nodes[114] = np.array((5.0, 5.0, 2.5), dtype=np.float64)
        self.nodes[115] = np.array((6.0, 5.0, 0.5), dtype=np.float64)
        self.nodes[116] = np.array((6.0, 5.0, 1.5), dtype=np.float64)
        self.nodes[117] = np.array((6.0, 5.0, 2.5), dtype=np.float64)
        self.nodes[118] = np.array((7.0, 5.0, 0.5), dtype=np.float64)
        self.nodes[119] = np.array((7.0, 5.0, 1.5), dtype=np.float64)
        self.nodes[120] = np.array((7.0, 5.0, 2.5), dtype=np.float64)
        self.nodes[121] = np.array((0.0, 4.0, 0.5), dtype=np.float64)
        self.nodes[122] = np.array((0.0, 4.0, 1.5), dtype=np.float64)
        self.nodes[123] = np.array((0.0, 4.0, 2.5), dtype=np.float64)
        self.nodes[124] = np.array((1.0, 4.0, 0.5), dtype=np.float64)
        self.nodes[125] = np.array((1.0, 4.0, 1.5), dtype=np.float64)
        self.nodes[126] = np.array((1.0, 4.0, 2.5), dtype=np.float64)
        self.nodes[127] = np.array((2.0, 4.0, 0.5), dtype=np.float64)
        self.nodes[128] = np.array((2.0, 4.0, 1.5), dtype=np.float64)
        self.nodes[129] = np.array((2.0, 4.0, 2.5), dtype=np.float64)
        self.nodes[130] = np.array((3.0, 4.0, 0.5), dtype=np.float64)
        self.nodes[131] = np.array((3.0, 4.0, 1.5), dtype=np.float64)
        self.nodes[132] = np.array((3.0, 4.0, 2.5), dtype=np.float64)
        self.nodes[133] = np.array((4.0, 4.0, 0.5), dtype=np.float64)
        self.nodes[134] = np.array((4.0, 4.0, 1.5), dtype=np.float64)
        self.nodes[135] = np.array((4.0, 4.0, 2.5), dtype=np.float64)
        self.nodes[136] = np.array((5.0, 4.0, 0.5), dtype=np.float64)
        self.nodes[138] = np.array((5.0, 4.0, 2.5), dtype=np.float64)
        self.nodes[139] = np.array((6.0, 4.0, 0.5), dtype=np.float64)
        self.nodes[140] = np.array((6.0, 4.0, 1.5), dtype=np.float64)
        self.nodes[141] = np.array((6.0, 4.0, 2.5), dtype=np.float64)
        self.nodes[142] = np.array((7.0, 4.0, 0.5), dtype=np.float64)
        self.nodes[143] = np.array((7.0, 4.0, 1.5), dtype=np.float64)
        self.nodes[144] = np.array((7.0, 4.0, 2.5), dtype=np.float64)
        self.nodes[145] = np.array((0.0, 3.0, 0.5), dtype=np.float64)
        self.nodes[146] = np.array((0.0, 3.0, 1.5), dtype=np.float64)
        self.nodes[147] = np.array((0.0, 3.0, 2.5), dtype=np.float64)
        self.nodes[148] = np.array((1.0, 3.0, 0.5), dtype=np.float64)
        self.nodes[149] = np.array((1.0, 3.0, 1.5), dtype=np.float64)
        self.nodes[150] = np.array((1.0, 3.0, 2.5), dtype=np.float64)
        self.nodes[151] = np.array((2.0, 3.0, 0.5), dtype=np.float64)
        self.nodes[152] = np.array((2.0, 3.0, 1.5), dtype=np.float64)
        self.nodes[153] = np.array((2.0, 3.0, 2.5), dtype=np.float64)
        self.nodes[154] = np.array((3.0, 3.0, 0.5), dtype=np.float64)
        self.nodes[155] = np.array((3.0, 3.0, 1.5), dtype=np.float64)
        self.nodes[156] = np.array((3.0, 3.0, 2.5), dtype=np.float64)
        self.nodes[157] = np.array((4.0, 3.0, 0.5), dtype=np.float64)
        self.nodes[158] = np.array((4.0, 3.0, 1.5), dtype=np.float64)
        self.nodes[159] = np.array((4.0, 3.0, 2.5), dtype=np.float64)
        self.nodes[160] = np.array((5.0, 3.0, 0.5), dtype=np.float64)
        self.nodes[161] = np.array((5.0, 3.0, 1.5), dtype=np.float64)
        self.nodes[162] = np.array((5.0, 3.0, 2.5), dtype=np.float64)
        self.nodes[163] = np.array((6.0, 3.0, 0.5), dtype=np.float64)
        self.nodes[164] = np.array((6.0, 3.0, 1.5), dtype=np.float64)
        self.nodes[165] = np.array((6.0, 3.0, 2.5), dtype=np.float64)
        self.nodes[166] = np.array((7.0, 3.0, 0.5), dtype=np.float64)
        self.nodes[167] = np.array((7.0, 3.0, 1.5), dtype=np.float64)
        self.nodes[168] = np.array((7.0, 3.0, 2.5), dtype=np.float64)
        self.nodes[169] = np.array((0.0, 2.0, 0.5), dtype=np.float64)
        self.nodes[170] = np.array((0.0, 2.0, 1.5), dtype=np.float64)
        self.nodes[171] = np.array((0.0, 2.0, 2.5), dtype=np.float64)
        self.nodes[172] = np.array((1.0, 2.0, 0.5), dtype=np.float64)
        self.nodes[173] = np.array((1.0, 2.0, 1.5), dtype=np.float64)
        self.nodes[174] = np.array((1.0, 2.0, 2.5), dtype=np.float64)
        self.nodes[175] = np.array((2.0, 2.0, 0.5), dtype=np.float64)
        self.nodes[176] = np.array((2.0, 2.0, 1.5), dtype=np.float64)
        self.nodes[177] = np.array((2.0, 2.0, 2.5), dtype=np.float64)
        self.nodes[178] = np.array((3.0, 2.0, 0.5), dtype=np.float64)
        self.nodes[179] = np.array((3.0, 2.0, 1.5), dtype=np.float64)
        self.nodes[180] = np.array((3.0, 2.0, 2.5), dtype=np.float64)
        self.nodes[181] = np.array((4.0, 2.0, 0.5), dtype=np.float64)
        self.nodes[182] = np.array((4.0, 2.0, 1.5), dtype=np.float64)
        self.nodes[183] = np.array((4.0, 2.0, 2.5), dtype=np.float64)
        self.nodes[184] = np.array((5.0, 2.0, 0.5), dtype=np.float64)
        self.nodes[185] = np.array((5.0, 2.0, 1.5), dtype=np.float64)
        self.nodes[186] = np.array((5.0, 2.0, 2.5), dtype=np.float64)
        self.nodes[187] = np.array((6.0, 2.0, 0.5), dtype=np.float64)
        self.nodes[188] = np.array((6.0, 2.0, 1.5), dtype=np.float64)
        self.nodes[189] = np.array((6.0, 2.0, 2.5), dtype=np.float64)
        self.nodes[190] = np.array((7.0, 2.0, 0.5), dtype=np.float64)
        self.nodes[191] = np.array((7.0, 2.0, 1.5), dtype=np.float64)
        self.nodes[192] = np.array((7.0, 2.0, 2.5), dtype=np.float64)
        self.nodes[193] = np.array((0.0, 1.0, 0.5), dtype=np.float64)
        self.nodes[194] = np.array((0.0, 1.0, 1.5), dtype=np.float64)
        self.nodes[195] = np.array((0.0, 1.0, 2.5), dtype=np.float64)
        self.nodes[196] = np.array((1.0, 1.0, 0.5), dtype=np.float64)
        self.nodes[197] = np.array((1.0, 1.0, 1.5), dtype=np.float64)
        self.nodes[198] = np.array((1.0, 1.0, 2.5), dtype=np.float64)
        self.nodes[199] = np.array((2.0, 1.0, 0.5), dtype=np.float64)
        self.nodes[200] = np.array((2.0, 1.0, 1.5), dtype=np.float64)
        self.nodes[201] = np.array((2.0, 1.0, 2.5), dtype=np.float64)
        self.nodes[202] = np.array((3.0, 1.0, 0.5), dtype=np.float64)
        self.nodes[203] = np.array((3.0, 1.0, 1.5), dtype=np.float64)
        self.nodes[204] = np.array((3.0, 1.0, 2.5), dtype=np.float64)
        self.nodes[205] = np.array((4.0, 1.0, 0.5), dtype=np.float64)
        self.nodes[206] = np.array((4.0, 1.0, 1.5), dtype=np.float64)
        self.nodes[207] = np.array((4.0, 1.0, 2.5), dtype=np.float64)
        self.nodes[208] = np.array((5.0, 1.0, 0.5), dtype=np.float64)
        self.nodes[209] = np.array((5.0, 1.0, 1.5), dtype=np.float64)
        self.nodes[210] = np.array((5.0, 1.0, 2.5), dtype=np.float64)
        self.nodes[211] = np.array((6.0, 1.0, 0.5), dtype=np.float64)
        self.nodes[212] = np.array((6.0, 1.0, 1.5), dtype=np.float64)
        self.nodes[213] = np.array((6.0, 1.0, 2.5), dtype=np.float64)
        self.nodes[214] = np.array((7.0, 1.0, 0.5), dtype=np.float64)
        self.nodes[215] = np.array((7.0, 1.0, 1.5), dtype=np.float64)
        self.nodes[216] = np.array((7.0, 1.0, 2.5), dtype=np.float64)
        self.nodes[217] = np.array((0.0, 0.0, 0.5), dtype=np.float64)
        self.nodes[218] = np.array((0.0, 0.0, 1.5), dtype=np.float64)
        self.nodes[219] = np.array((0.0, 0.0, 2.5), dtype=np.float64)
        self.nodes[220] = np.array((1.0, 0.0, 0.5), dtype=np.float64)
        self.nodes[221] = np.array((1.0, 0.0, 1.5), dtype=np.float64)
        self.nodes[222] = np.array((1.0, 0.0, 2.5), dtype=np.float64)
        self.nodes[223] = np.array((2.0, 0.0, 0.5), dtype=np.float64)
        self.nodes[224] = np.array((2.0, 0.0, 1.5), dtype=np.float64)
        self.nodes[225] = np.array((2.0, 0.0, 2.5), dtype=np.float64)
        self.nodes[226] = np.array((3.0, 0.0, 0.5), dtype=np.float64)
        self.nodes[227] = np.array((3.0, 0.0, 1.5), dtype=np.float64)
        self.nodes[228] = np.array((3.0, 0.0, 2.5), dtype=np.float64)
        self.nodes[229] = np.array((4.0, 0.0, 0.5), dtype=np.float64)
        self.nodes[230] = np.array((4.0, 0.0, 1.5), dtype=np.float64)
        self.nodes[231] = np.array((4.0, 0.0, 2.5), dtype=np.float64)
        self.nodes[232] = np.array((5.0, 0.0, 0.5), dtype=np.float64)
        self.nodes[233] = np.array((5.0, 0.0, 1.5), dtype=np.float64)
        self.nodes[234] = np.array((5.0, 0.0, 2.5), dtype=np.float64)
        self.nodes[235] = np.array((6.0, 0.0, 0.5), dtype=np.float64)
        self.nodes[236] = np.array((6.0, 0.0, 1.5), dtype=np.float64)
        self.nodes[237] = np.array((6.0, 0.0, 2.5), dtype=np.float64)
        self.nodes[238] = np.array((7.0, 0.0, 0.5), dtype=np.float64)
        self.nodes[239] = np.array((7.0, 0.0, 1.5), dtype=np.float64)
        self.nodes[240] = np.array((7.0, 0.0, 2.5), dtype=np.float64)
        
        if subset is not None:
            to_keep = {x for l in (range(start, end+1) for (start, end) in subset) for x in l}
            for key in set(self.nodes) - to_keep:
                del self.nodes[key]
        
        self._process_node_id_order("topology")

    def node_ids(self):
        """Get the node id string that identifies which nodes are being used to the testbed."""
        # From: https://stackoverflow.com/questions/17415086/combine-consecutive-numbers-into-range-tuples
        groups = groupby(self.nodes.keys(), key=lambda item, c=count():item-next(c))
        temp = [list(g) for k, g in groups]
        return "+".join("{}-{}".format(x[0], x[-1]) for x in temp)

    def __str__(self):
        return "Strasbourg<>"

