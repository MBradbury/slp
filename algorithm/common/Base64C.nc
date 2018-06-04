/* base64.c -- Encode binary data using printable characters.
   Copyright (C) 1999-2001, 2004-2006, 2009-2012 Free Software Foundation, Inc.

   This program is free software; you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation; either version 2, or (at your option)
   any later version.

   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program; if not, see <http://www.gnu.org/licenses/>.  */

/* Written by Simon Josefsson.  Partially adapted from GNU MailUtils
 * (mailbox/filter_trans.c, as of 2004-11-28).  Improved by review
 * from Paul Eggert, Bruno Haible, and Stepan Kasal.
 *
 * See also RFC 4648 <http://www.ietf.org/rfc/rfc4648.txt>.
 *
 * Be careful with error checking.  Here is how you would typically
 * use these functions:
 *
 * bool ok = base64_decode_alloc (in, inlen, &out, &outlen);
 * if (!ok)
 *   FAIL: input was not valid base64
 * if (out == NULL)
 *   FAIL: memory allocation error
 * OK: data in OUT/OUTLEN
 *
 * size_t outlen = base64_encode_alloc (in, inlen, &out);
 * if (out == NULL && outlen == 0 && inlen != 0)
 *   FAIL: input too long
 * if (out == NULL)
 *   FAIL: memory allocation error
 * OK: data in OUT/OUTLEN.
 *
 */

// This code was based off code made available at  http://ab-initio.mit.edu/octave-Faddeeva/gnulib/lib/base64.c

/* This uses that the expression (n+(k-1))/k means the smallest
   integer >= n/k, i.e., the ceiling of n/k.  */
#define BASE64_LENGTH(inlen) (((((inlen) + 2) / 3) * 4) + 1)

module Base64C
{
    provides interface Encode;
}
implementation
{
    command bool Encode.encode(char* out, uint8_t outlen, const void* inVoid, uint8_t inlen)
    {
        static const char* b64str = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

        const uint8_t* in = (const uint8_t*)inVoid;

        if (outlen < BASE64_LENGTH(inlen))
        {
            out[0] = '\0';
            return FALSE;
        }

        while (inlen && outlen)
        {
            *out++ = b64str[(in[0] >> 2) & 0x3f];
            if (!--outlen)
                break;

            *out++ = b64str[((in[0] << 4) + (--inlen ? in[1] >> 4 : 0)) & 0x3f];
            if (!--outlen)
                break;

            *out++ = (inlen ? b64str[((in[1] << 2) + (--inlen ? in[2] >> 6 : 0)) & 0x3f] : '=');
            if (!--outlen)
                break;

            *out++ = inlen ? b64str[in[2] & 0x3f] : '=';
            if (!--outlen)
                break;

            if (inlen)
                inlen--;

            if (inlen)
                in += 3;
        }

        if (outlen)
            *out = '\0';

        return TRUE;
    }
}
