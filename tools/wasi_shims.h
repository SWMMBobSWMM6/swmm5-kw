/* Shims for wasm32-wasi: wasi-libc compiles these out; SWMM only needs them for temp/interface files. */
#ifndef WASI_SHIMS_H
#define WASI_SHIMS_H
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
static inline int kw_wasi_mkstemp(char *tmpl) { static int n = 0; size_t L = strlen(tmpl);
    if (L >= 6) { char buf[8]; snprintf(buf, sizeof buf, "%06d", ++n); memcpy(tmpl + L - 6, buf, 6); }
    FILE *f = fopen(tmpl, "w+b"); if (!f) return -1; fclose(f); return 3; }
#define mkstemp kw_wasi_mkstemp
static inline char *kw_wasi_realpath(const char *p, char *r) { if (!r) r = (char*)malloc(strlen(p)+1); strcpy(r, p); return r; }
#define realpath kw_wasi_realpath
#endif
