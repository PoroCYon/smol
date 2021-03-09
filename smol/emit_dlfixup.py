
import sys
from collections import OrderedDict

from .shared import *

def sort_imports(libraries):
    for k, v in libraries.items():
        libraries[k] = OrderedDict(sorted(v.items(), key=lambda sr: sr[0]))

    return libraries

def output_dlfixup(arch, libraries, nx, outf, det):
    assert arch == 'x86_64'

    # ugly hack
    libraries.setdefault('libc.so.6', {})
    if '_dl_sym' in libraries['libc.so.6']:
        error("Don't use _dl_sym in user code!")

    outf.write('; vim: set ft=nasm:\n')
    outf.write('bits 64\n')

    if nx:
        outf.write('%define USE_NX 1\n')

    if det: libraries = sort_imports(libraries)

    shorts = { l: l.split('.', 1)[0].lower().replace('-', '_') for l in libraries }

    outf.write('%include "header-dlf.asm"\n')
    outf.write('dynamic.needed:\n')
    for library, symrels in libraries.items():
        if (len(symrels) > 0):
            outf.write('    dq DT_NEEDED\n')
            outf.write('    dq (_library.{} - _dynstr)\n'.format(shorts[library]))

    # need a few extra ones here & not in the template source because bah
    outf.write("""\
;dynamic.symtab:
;    dq DT_SYMTAB
;    dq _dynsym
;dynamic.pltgot:
;    dq DT_PLTGOT
;    dq _gotplt
;dynamic.jmprel:
;    dq DT_JMPREL
;    dq _rela_plt
dynamic.end:
%ifndef UNSAFE_DYNAMIC
    dq DT_NULL
%endif
""")

    # all needed sonames first - runtime code will parse a list of
    # null-terminated strings as symbol names

    outf.write('[section .dynstr]\n')
    outf.write('global _dynstr\n')
    outf.write('_dynstr: ;db 0\n')
    for library, symrels in libraries.items():
        if (len(symrels) > 0):
            outf.write('    _library.{}: db "{}",0\n'.format(shorts[library], library))

    # now do the actual symbol names

    outf.write('_symbols.libc._dl_sym: db "_dl_sym",0\n') # this is a special one
    outf.write('_symbols:\n')
    for library, symrels in libraries.items():
        outf.write('    _symbols.{}:\n'.format(shorts[library]))
        for sym, reloc in symrels.items():
            outf.write('        _symbols.{}.{}: db "{}",0\n'.format(shorts[library], sym, sym))
    outf.write('_symbols.end: db 0\n')

    # now we need some addresses to put the values in, so let's do that as well:
    outf.write('[section .bss.got.plt nobits]\n')
    outf.write('_gotplt.imports:\n')
    for library, symrels in libraries.items():
        outf.write('    _gotplt.imports.{}:\n'.format(shorts[library]))
        for sym, reloc in symrels.items():
            if reloc not in ['R_X86_64_PLT32', 'R_X86_64_GOTPCRELX', \
                             'R_X86_64_REX_GOTPCRELX', 'R_X86_64_GOTPCREL']:
                error('Relocation type %s of symbol %s unsupported!' % (reloc, sym))

            if reloc in ['R_X86_64_GOTPCRELX', 'R_X86_64_REX_GOTPCRELX', \
                         'R_X86_64_GOTPCREL']:
                outf.write("""\
global {name}
{name}:
""".format(name=sym))

            outf.write('        _gotplt.imports.{}.{}: resq 1\n'.format(shorts[library], sym))


    # for R_X86_64_PLT32 relocs, we need some extra boilerplate to make stuff
    # go to the addresses above
    outf.write('global _smolplt\n')
    outf.write('_smolplt:\n')
    for library, symrels in libraries.items():
        for sym, reloc in symrels.items():
            if reloc == 'R_X86_64_PLT32':
                outf.write("""\
[section .text.smolplt.{name}]
global {name}
{name}:
    jmp [rel _gotplt.imports.{lib}.{name}]
""".format(lib=shorts[library],name=sym).lstrip('\n'))

    # that's all folks!
    outf.write('_smolplt.end:\n')
    outf.write('%include "loader-dlf.asm"\n')

