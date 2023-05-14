/*
 * Description:
 *      This file will provide additional information to the compiler
 *      By defining SPEED value, the optimization can be changed during macro expansion phase
 *      Default SPEED value is 2 (-O2)
 *      
 *      Example Usage:
 *          #include "DuinoCoinSpeed.h"
 *          // this should gives 
 *          //      #pragma GCC optimize ("-O2")
 * 
 * Author: JK Rolling
 * Date: 2022/01/20
 * 
 */

#ifndef DUINOCOINSPEED_H_
#define DUINOCOINSPEED_H_

#define OPTIMIZATION(x) _Pragma (#x)

// user to change SPEED preference
#ifndef SPEED
  #define SPEED 4
#endif

// 0 -O0    <- reduce compilation time
// 1 -Os    <- optimize for size
// 2 -O2    <- Fast
// 3 -O3    <- Faster
// 4 -Ofast <- Fastest
// g -Og    <- optimize debugging experience
#if SPEED==0
  OPTIMIZATION (GCC optimize ("-O0"))
#elif SPEED==1
  OPTIMIZATION (GCC optimize ("-Os"))
#elif SPEED==2
  OPTIMIZATION (GCC optimize ("-O2"))
#elif SPEED==3
  OPTIMIZATION (GCC optimize ("-O3"))
#elif SPEED==4
  OPTIMIZATION (GCC optimize ("-Ofast"))
#elif SPEED==g
  OPTIMIZATION (GCC optimize ("-Og"))
#else
  #error "Invalid SPEED value. Use 0/1/2/3/4/g"
#endif

#endif

/*
 * Tested on Arduino UNO
 * 0 --> 260H/s
 * 1 --> 314H/s
 * 2 --> 328H/s
 * 3 --> 342H/s
 * 4 --> 342H/s
 * g --> 260H/s
 * 
 */
