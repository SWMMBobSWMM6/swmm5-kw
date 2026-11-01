"""Minimal reader for SWMM 5 binary output (.out): IDs and per-period results.
   read(path) -> dict(nodes=[ids], links=[ids], periods=n, start=days, step=seconds,
                      node(i, var) -> list, link(j, var) -> list, error=code)
   Link vars: 0 flow, 1 depth, 2 velocity, 3 volume, 4 capacity. Node vars: 0 depth, 1 head,
   2 volume, 3 lateral inflow, 4 total inflow, 5 flooding."""
import struct

def read(path):
    b = open(path, 'rb').read()
    I = lambda off: struct.unpack_from('<i', b, off)[0]
    off_id, off_prop, off_res, nper, err, magic2 = struct.unpack_from('<6i', b, len(b) - 24)
    magic, ver, units, nsub, nnode, nlink, npol = struct.unpack_from('<7i', b, 0)
    pos = off_id; names = []
    for _ in range(nsub + nnode + nlink + npol):
        n = I(pos); names.append(b[pos + 4:pos + 4 + n].decode('latin-1')); pos += 4 + n
    subs, nodes, links = names[:nsub], names[nsub:nsub + nnode], names[nsub + nnode:nsub + nnode + nlink]
    # reporting variable counts sit right before the results section
    pos = off_prop
    nsp = I(pos); pos += 4 * (1 + nsp) + 4 * nsp * nsub
    nnp = I(pos); pos += 4 * (1 + nnp) + 4 * nnp * nnode
    nlp = I(pos); pos += 4 * (1 + nlp) + 4 * nlp * nlink
    nsv = I(pos); pos += 4 * (1 + nsv)
    nnv = I(pos); pos += 4 * (1 + nnv)
    nlv = I(pos); pos += 4 * (1 + nlv)
    nyv = I(pos); pos += 4 * (1 + nyv)
    start = struct.unpack_from('<d', b, pos)[0]; step = I(pos + 8)
    rec = 8 + 4 * (nsub * nsv + nnode * nnv + nlink * nlv + nyv)
    def series(base, var):
        return [struct.unpack_from('<f', b, off_res + k * rec + 8 + 4 * (base + var))[0] for k in range(nper)]
    return dict(nodes=nodes, links=links, periods=nper, start=start, step=step, error=err,
                node=lambda i, v: series(nsub * nsv + i * nnv, v),
                link=lambda j, v: series(nsub * nsv + nnode * nnv + j * nlv, v))
