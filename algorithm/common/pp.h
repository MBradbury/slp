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


// Static assert code from: https://stackoverflow.com/questions/19403233/compile-time-struct-size-check-error-out-if-odd
#define STATIC_ASSERT(X)            STATIC_ASSERT2(X,__LINE__)

/*
    These macros are required by STATIC_ASSERT to make token pasting work.
    Not really useful by themselves.
*/
#define STATIC_ASSERT2(X,L)         STATIC_ASSERT3(X,L)
#define STATIC_ASSERT3(X,L)         STATIC_ASSERT_MSG(X,at_line_##L)

/*
    Static assertion with special error message.
    Note: It depends on compiler whether message is visible or not!

    STATIC_ASSERT_MSG(sizeof(long)==8, long_is_not_eight_bytes);
*/
#define STATIC_ASSERT_MSG(COND,MSG) \
    typedef char static_assertion_##MSG[(!!(COND))*2-1]


#endif // SLP_PP_H
