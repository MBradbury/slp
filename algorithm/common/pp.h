#ifndef SLP_PP_H
#define SLP_PP_H

/*
 * Concatenate preprocessor tokens A and B without expanding macro definitions
 * (however, if invoked from a macro, macro arguments are expanded).
 */
#define PPCAT_NX(A, B) A ## B

/*
 * Concatenate preprocessor tokens A and B after macro-expanding them.
 */
#define PPCAT(A, B) PPCAT_NX(A, B)

#define ARRAY_SIZE(a) (sizeof(a) / sizeof(*a))

#define CHAR_BIT 8

#define STRINGIFY(a) STRINGIFY_IMPL(a)
#define STRINGIFY_IMPL(a) #a

#ifndef STATIC_ASSERT_MSG
#	include "slp_static_assert.h"
#endif

// From: https://stackoverflow.com/questions/29134152/overloading-macros-with-variadic-arguments
#define CHECK_N(x, n, ...) n
#define CHECK(...) CHECK_N(__VA_ARGS__, 0,)
#define PROBE(x) x, 1,

#define IS_2(x) CHECK(PPCAT(IS_2_, x))
#define IS_2_2 PROBE(~)

#define NARGS_SEQ(_1,_2,_3,_4,_5,_6,_7,_8,N,...) N
#define NARGS(...) NARGS_SEQ(__VA_ARGS__, 8, 7, 6, 5, 4, 3, 2, 1)

#endif // SLP_PP_H
