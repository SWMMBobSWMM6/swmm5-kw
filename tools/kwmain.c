/* kwswmm: the extended engine as a command-line program.
     KWSPLIT=1 KWLOOP=1 kwswmm model.inp model.rpt model.out
   KWSPLIT: 0 stock (ERROR 133), 1 HEAD, 2 CAPACITY, 3 AREA
   KWLOOP:  0 stock (ERROR 131), 1 iterate
   Unset means 0: stock EPA 5.2.4 behaviour. Prints swmm_getKwStats on stdout. */
#include <stdio.h>
#include <stdlib.h>
#include "swmm5.h"
int main(int argc, char* argv[])
{
    const char* s = getenv("KWSPLIT"); const char* l = getenv("KWLOOP");
    double v[10];
    if ( argc < 4 ) { printf("usage: kwswmm in.inp out.rpt out.out\n"); return 1; }
    swmm_setKwOptions(s ? atoi(s) : 0, l ? atoi(l) : 0);
    int rc = swmm_open(argv[1], argv[2], argv[3]);
    if ( !rc ) rc = swmm_start(1);
    if ( !rc ) { double el = 0; do { rc = swmm_step(&el); } while ( el > 0 && !rc ); }
    swmm_end();
    swmm_getKwStats(v);
    swmm_report();
    swmm_close();
    printf("rc=%d split=%g back=%g allocs=%g maxImb=%.3g loopSteps=%g meanSweeps=%.3f maxSweeps=%g nonConv=%g maxRes=%.3g headIt=%.2f\n",
        rc, v[0], v[1], v[2], v[3], v[4], v[5], v[6], v[7], v[8], v[9]);
    return rc;
}
