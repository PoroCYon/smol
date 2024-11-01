
import os.path
import subprocess
import sys

from .parse import *
from .shared import eprintf


def cc_relink_objs(verbose, cc_bin, arch, inputs, output, cflags):
    archflag = '-m64' if arch == "x86_64" else '-m32'

    cctyp, ccver = get_cc_version(cc_bin)
    assert cctyp == "gcc", "A GCC compiler is needed for relinking objects!"
    relink_arg = "-flinker-output=rel" if ccver < (9,0) else "-flinker-output=nolto-rel"

    args = [cc_bin, archflag, '-nostartfiles', '-nostdlib', \
            '-r', relink_arg, '-o', output] + cflags + inputs

    if verbose: eprintf("cc: %s" % repr(args))
    subprocess.check_call(args, stdout=subprocess.DEVNULL)

def nasm_assemble_elfhdr(verbose, nasm_bin, arch, rtdir, intbl, output, asflags):
    if rtdir[-1] != '/': rtdir = rtdir + '/'
    archflag = 'elf64' if arch == "x86_64" else 'elf32'

    args = [nasm_bin, '-I', rtdir, '-f', archflag] + asflags + [intbl, '-o', output]

    if verbose: eprintf("nasm: %s" % repr(args))
    subprocess.check_call(args, stdout=subprocess.DEVNULL)

def ld_link_final(verbose, cc_bin, arch, lddir, inobjs, output, ldflags, nx, sectorder, debug):
    linkscr = None
    if arch == 'x86_64':
        linkscr = ('x86_64_%s_nx' if nx else 'x86_64_%s_rwx') % sectorder
    else:
        linkscr = '%s_%s' % (arch, sectorder)

    archflag = '-m64' if arch == "x86_64" else '-m32'

    ldtyp, ldver = get_ld_version(cc_bin)

    workaround_args = []
    # workaround for https://sourceware.org/bugzilla/show_bug.cgi?id=32067
    if ldtyp == 'gnuld' and ldver >= (2,42,0) and ldver < (2,43,1):
        workaround_args += ["-fno-lto"]

    args = [cc_bin, *workaround_args, archflag, '-L', lddir, '-T', '%s/link_%s.ld'%(lddir,linkscr), '-no-pie']
    if not debug:
        args.append('-Wl,--oformat=binary')
        #args = [*args, '-T', lddir+'/link.ld', '-Wl,--oformat=binary']
    args += ['-nostartfiles', '-nostdlib', '-o', output, *inobjs, *ldflags]

    if verbose: eprintf("ld: %s" % repr(args))
    subprocess.check_call(args, stdout=subprocess.DEVNULL)

