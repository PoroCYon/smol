
import collections
import glob
import os.path
import re
import subprocess
import struct
import sys
from typing import NamedTuple, List, Dict, OrderedDict, Tuple, Set

from .shared import *
from .hackyelf import *

implicit_syms = { '_GLOBAL_OFFSET_TABLE_' }
unsupported_symtyp = { 'NOTYPE', 'TLS', 'OBJECT' } # TODO: support OBJECT, and maybe TLS too


CC_VERSIONS = {}
LD_VERSIONS = {}


class ExportSym(NamedTuple):
    name: str
    typ: str
    scope: str
    vis: str
    ndx: str


def decide_arch(inpfiles):
    archs = set()

    for fp in inpfiles:
        with open(fp, 'rb') as ff:
            magi = ff.read(4) # EI_MAGx of ei_ident

            if magi != b'\x7fELF':
                error("Input file '%s' is not an ELF file!" % fp)

            _ = ff.read(12) # rest of ei_ident
            _ = ff.read( 2) # ei_type
            machine = ff.read(2) # ei_machine

            machnum = struct.unpack('<H', machine)[0]
            archs.add(machnum)

    if len(archs) != 1:
        error("Input files have multiple architectures, can't link this...")

    archn = archs.pop()

    if archn not in archmagic:
        eprintf("Unknown architecture number %d" + \
            ". Consult elf.h and rebuild your object files." % archn)

    return archmagic[archn]


def build_reloc_typ_table(reo) -> Dict[str, Set[str]]: # (symname, reloctyps) dict
    relocs = {}

    for s in reo.decode('utf-8').splitlines():
        stuff = s.split()

        # prolly a 'header' line
        if len(stuff) != 7 and len(stuff) != 5:
            continue

        symname, reloctyp = stuff[4], stuff[2]

        if symname[0] == '.': # bleh
            continue

        relocs.setdefault(symname, set()).add(reloctyp)

    return relocs


def has_lto_object(readelf_bin, files):
    for x in files:
        with open(x,'rb') as f:
            if f.read(2) == b'BC': # LLVM bitcode! --> clang -flto
                return True

    output = subprocess.check_output([readelf_bin, '-s', '-W'] + files,
                                     stderr=subprocess.DEVNULL)

    curfile = files[0]
    for entry in output.decode('utf-8').splitlines():
        stuff = entry.split()
        if len(stuff) < 2:
            continue
        if stuff[0] == "File:":
            curfile = stuff[1]

        # assuming nobody uses a symbol called "__gnu_lto_"...
        if "__gnu_lto_" in entry or ".gnu.lto" in entry:
            return True

    return False


def get_needed_syms(readelf_bin, inpfile) -> Dict[str, str]: # (symname, reloctyp) dict
    output = subprocess.check_output([readelf_bin, '-s', '-W',inpfile],
                                     stderr=subprocess.DEVNULL)
    outrel = subprocess.check_output([readelf_bin, '-r', '-W',inpfile],
                                     stderr=subprocess.DEVNULL)
    #eprintf(output.decode('utf-8'))
    #eprintf(outrel.decode('utf-8'))

    relocs = build_reloc_typ_table(outrel)

    curfile = inpfile
    syms = {}
    for entry in output.decode('utf-8').splitlines():
        stuff = entry.split()
        if len(stuff) < 2:
            continue
        if stuff[0] == "File:":
            curfile = stuff[1]
        if len(stuff) < 8:
            continue

        scope, ndx, name = stuff[4], stuff[6], stuff[7]

        if name.startswith("__gnu_lto_"): # yikes, an LTO object
            error("E: {} is an LTO object file, can't use this!".format(curfile))
        if scope == "GLOBAL" and ndx == "UND" and len(name) > 0:
            if name in relocs:
                rlt = relocs[name]
                if len(rlt) > 1:
                    error("E: symbol '%s' has multiple relocations types?! (%s)"
                          % (name, ', '.join(rlt)))
                #syms.add((name, rlt.pop()))
                if name in syms:
                    assert False, ("??? %s" % name)
                syms[name] = rlt.pop()
            elif name not in implicit_syms:
                error("E: symbol '%s' has no relocation type?!" % name)

    #needgot = False
    #if "_GLOBAL_OFFSET_TABLE_" in syms:
    #    needgot = True
    #    syms.remove("_GLOBAL_OFFSET_TABLE_")

    return syms#, needgot


def uniq_list(l):
    od = OrderedDict()
    for x in l: od[x] = x
    return list(od.keys())

def format_cc_path_line(entry):
    category, path = entry.split(': ', 1)
    path = path.lstrip('=')
    return (category, uniq_list(os.path.realpath(p) \
        for p in path.split(':') if os.path.isdir(p))[::-1])


def get_cc_paths(cc_bin, arch):
    bits = []
    if arch == 'i386': bits.append("-m32")
    elif arch == 'x86_64': bits.append("-m64")

    output = None
    bak = os.environ.copy()
    os.environ['LANG'] = "C" # DON'T output localized search dirs!
    try:
        output = subprocess.check_output([cc_bin, *bits, '-print-search-dirs'],
                                         stderr=subprocess.DEVNULL)
    finally:
        os.environ = bak

    lines = output.decode('utf-8').splitlines()
    #print("lines", lines)
    outputpairs = list(map(format_cc_path_line, lines))
    #print("pairs", outputpairs)
    paths = OrderedDict()

    for category, path in outputpairs: paths[category] = path

    if 'libraries' not in paths: # probably localized... sigh
        # monkeypatch, assuming order...
        paths = {}
        paths['install'  ] = outputpairs[0][1]
        paths['programs' ] = outputpairs[1][1]
        paths['libraries'] = outputpairs[2][1]

    #print("searchpaths", paths['libraries'])
    return paths


def get_cc_version(cc_bin):
    global CC_VERSIONS

    typver = CC_VERSIONS.get(cc_bin, None)
    if typver is not None:
        return typver

    # Backup the current environment and set LANG to C to avoid localized outputs
    bak = os.environ.copy()
    os.environ['LANG'] = "C"

    r = None
    output = None

    try:
        # Run the compiler with --version and capture the output
        output = subprocess.check_output([cc_bin, '--version'], stderr=subprocess.DEVNULL)
    finally:
        # Restore the original environment
        os.environ = bak

    # Decode the output from bytes to string and split into lines
    lines = output.decode('utf-8').splitlines()

    # Check if the output corresponds to GCC
    if "Free Software Foundation" in lines[1]:
        # Use regex to find the version number in the output lines
        match = re.search(r'(\d+)\.(\d+)\.(\d+)', lines[0])
        if match:
            # If a version number is found, return it as a tuple of integers
            r = ("gcc", tuple(map(int, match.groups())))
        else:
            # If no version number is found, return a generic version (0, 0, 0)
            r = ("gcc", (0, 0, 0))
    else:
        # Assume Clang if not GCC, and attempt to extract version similarly
        match = re.search(r'(\d+)\.(\d+)\.(\d+)', lines[0])
        if match:
            r = ("clang", tuple(map(int, match.groups())))
        else:
            r = ("clang", (0, 0, 0))

    assert r is not None, ("Couldn't parse C compiler version somehow??? " + cc_bin)
    CC_VERSIONS[cc_bin] = r  # cache result
    return r


def get_ld_version(cc_bin):
    global LD_VERSIONS

    typver = LD_VERSIONS.get(cc_bin, None)
    if typver is not None:
        return typver

    # Backup the current environment and set LANG to C to avoid localized outputs
    bak = os.environ.copy()
    os.environ['LANG'] = "C"

    r = None
    output = None

    try:
        # Run the compiler with -Wl,--version and capture the output
        output = subprocess.check_output([cc_bin, '-Wl,--version'], stderr=subprocess.DEVNULL)
    finally:
        os.environ = bak  # restore original env

    # Decode the output from bytes to string and split into lines
    lines = output.decode('utf-8').splitlines()

    if len(lines) > 1 and "Free Software Foundation" in lines[1]:  # GNU ld
        match = re.search(r'(\d+)\.(\d+)\.(\d+)', lines[0])
        if match:
            r = ('gnuld', tuple(map(int, match.groups())))
        else:
            r = ('gnuld', (0, 0, 0))
    elif "LLD" in lines[0]:  # LLVM LLD
        match = re.search(r'(\d+)\.(\d+)\.(\d+)', lines[0])
        if match:
            r = ('lld', tuple(map(int, match.groups())))
        else:
            r = ('lld', (0, 0, 0))
    else:
        assert False, ("Unknown linker! " + lines[0])

    assert r is not None, ("Couldn't parse linker version somehow??? " + cc_bin)
    LD_VERSIONS[cc_bin] = r  # cache result
    return r

def is_valid_elf(f, arch):
    with open(f, 'rb') as ff:
        eimag = ff.read(4)  # ei_mag0..3
        if eimag != b'\x7fELF':
            return False

        eiclass = ff.read(1)[0]  # 32/64-bit
        eidata = ff.read(1)[0]  # little/big endian
        _ = ff.read(16-6)  # rest of e_ident
        _ = ff.read(2)  # e_type
        mach = struct.unpack('<H', ff.read(2))[0]  # e_machine

        #print("lib", f, "eimag", eimag, "eidata", eidata, "eiclass", eiclass, "mach", mach)
        if eidata != 1:  # must be little-endian (for now, sorry)
            return False

        nbits = eiclass << 5  # cheating a bit to turn 1 into 32 and 2 into 64
        if nbits != ARCH2BITS[arch]:  # wrong bitness
            return False
        if mach != archmagic[arch]:  # wrong arch
            return False

    return True


def find_lib(spaths, wanted, arch):
    for p in spaths:
        #print("looking in", p)
        for f in glob.glob(glob.escape('%s/lib%s' % (p, wanted)) + '.so*'):
            if os.path.isfile(f) and is_valid_elf(f, arch):
                return f
        for f in glob.glob(glob.escape('%s/%s'    % (p, wanted)) + '.so*'):
            if os.path.isfile(f) and is_valid_elf(f, arch):
                return f
        #for f in glob.glob(glob.escape(p) + '/lib' + wanted + '.a' ): return f
        #for f in glob.glob(glob.escape(p) + '/'    + wanted + '.a' ): return f

    error("E: couldn't find library '%s'." % wanted)


def get_soname(readelf_bin: str, lib: str) -> str:
    outdyn = subprocess.check_output([readelf_bin, '-d', '-W',inpfile],
                                     stderr=subprocess.DEVNULL)

    soname = os.path.split(inpfile)[1]
    for entry in outdyn.decode('utf-8').splitlines():
        if 'SONAME' in entry:
            # 0xTAGHEX (TAGNAME)    Library soname: [libfoo-123.so.1.2.3]
            soname = entry.strip().split()[-1]
            soname = soname[1:-1]
            break

    return soname


def find_libs(readelf_bin: str, spaths, wanted, arch) -> Dict[str,str]:
    # return dict([(l, get_soname(readelf_bin, l)) for l in ...])
    return dict([(l, l) for l in (find_lib(spaths, l, arch) for l in wanted)])


def build_symbol_map(readelf_bin, libraries: Dict[str,str]) -> Dict[str, Dict[str, ExportSym]]:
    # create dictionary that maps symbols to libraries that provide them, and their metadata
    symbol_map = {} # symname -> (lib, exportsym)

    # if this check is not performed, readelf will exit with a nonzero exitcode
    if len(libraries) == 0:
        return symbol_map

    # TODO: maybe get the SONAME from this readelf invocation as well? not sure
    #       what the guarantees are w/ the ordering of the output stuff...
    # NOTE: seems to work out just fine, if this breaks, please fall back to
    #       the "read soname in find_libs()" behavior (which is currently
    #       commented out, both here and in that function above)
    out = subprocess.check_output([readelf_bin, '-dsW', *libraries.keys()], stderr=subprocess.DEVNULL)

    lines = out.decode('utf-8').splitlines()
    firstlib = list(libraries.items())
    curfile = firstlib[0]
    #soname  = firstlib[1]
    for line in lines:
        fields = line.strip().split()
        if len(fields) < 2:
            continue

        if fields[0] == "File:":
            curfile = fields[1]
            #soname  = libraries[curfile]
        if "SONAME" in line:
            soname = fields[-1][1:-1]

        if len(fields) != 8:
            continue

        typ, scope, vis, ndx, name = fields[3:8]
        if vis != "DEFAULT" \
                or scope == "LOCAL": #\
                #or (ndx == "UND" and scope != "WEAK"):# \ # nah, that one's done further down the line as well
                #or typ in unsupported_symtym:
                # ^ except, for the last case, we're going to emit proper errors later on
            continue

        # strip away GLIBC versions
        name = re.sub(r"@@.*$", "", name)

        symbol_map.setdefault(name, {})[soname] = ExportSym(name, typ, scope, vis, ndx)

    return symbol_map


# this ordening is specific to ONE symbol!
def build_preferred_lib_order(sym, libs: Dict[str, ExportSym]) -> List[str]:
    # libs: lib -> syminfo
    realdefs    = [lib for lib, v in libs.items() if v.scope != "WEAK" and v.ndx != "UND"]
    weakdefs    = [lib for lib, v in libs.items() if v.scope == "WEAK" and v.ndx != "UND"]
    weakunddefs = [lib for lib, v in libs.items() if v.scope == "WEAK" and v.ndx == "UND"]
    unddefs     = [lib for lib, v in libs.items() if v.scope != "WEAK" and v.ndx == "UND"]

    #ks = [v.name for k, v in libs.items()]
    #print("k=",ks)
    #assert all(k == ks[0] for k in ks)

    if len(realdefs) > 1: #or (len(realdefs) == 0 and len(weakdefs) > 1):
        error("E: symbol '%s' defined non-weakly in multiple libraries! (%s)"
              % (sym, ', '.join(realdefs)))

    if len(realdefs) == 0 and len(weakdefs) > 1:
        eprintf("W: symbol '%s' defined amibguously weakly in multiple libraries! Will pick a random one... (%s)"
              % (sym, ', '.join(weakdefs)))
    if len(realdefs) == 0 and len(weakdefs) == 0: # must be in weakunddefs or unddefs
        error("E: no default weak implementation found for symbol '%s'" % sym)

    return realdefs + weakdefs + weakunddefs + unddefs

def has_good_subordening(needles, haystack):
    haylist = [x[0] for x in haystack]
    prevind = 0
    for lib in needles:
        curind = None
        try:
            curind = haylist.index(lib)
        except ValueError: # not in haystack --> eh, let's ignore
            continue

        if curind < prevind:
            return False
        prevind = curind
    return True


def add_with_ordening(haystack: List[Tuple[str, Dict[str, str]]], # [(libname, (symname -> reloctyp))]
                      needles: List[str], # [lib]
                      sym: str, reloc: str, last=False) \
                   -> List[Tuple[str, Dict[str, str]]]:
    haylist = [x[0] for x in haystack]
    startind = None if last else 0
    ii = 0
    for lib in needles:
        #eprintf("k=",k,"v=",v)
        try:
            newind = haylist.index(lib)
            #eprintf("lib=%s newind=%d" % (lib, newind))
            #assert newind >= startind, "???? (%d <= %d)" % (newind, startind)
            startind = newind

            if ii == 0:
                symrelocdict = haystack[startind][1]
                assert not(sym in symrelocdict), "?????"
                haystack[startind][1][sym] = reloc
        except ValueError: # not in haystack --> add!
            if startind is None:
                startind = len(haystack)
            if not last:
                startind = startind + 1
            #eprintf("lib=%s NEWind=%d" % (lib, startind))
            dv = {sym: reloc} if ii == 0 else {}
            haystack.insert(startind, (lib, dv))
            haylist.insert(startind, lib)
            if last:
                startind = startind + 1
        ii = ii + 1

    return haystack


def visable(ll): # "visualisable" (for printf debugging)
    rr = []
    for k, v in ll:
        if isinstance(v, ExportSym):
            rr.append((k, v)) # v.name
        else:
            rr.append((k, v.keys()))
    return rr
def resolve_extern_symbols(needed: Dict[str, List[str]], # symname -> reloctyps
                           available: Dict[str, Dict[str, ExportSym]], # symname -> (lib -> syminfo)
                           args) \
                        -> OrderedDict[str, Dict[str, str]]: # libname -> (symname -> reloctyp)
    # first of all, we're going to check which needed symbols are provided by
    # which libraries
    bound = {} # sym -> (reloc, (lib -> syminfo))
    for k, v in needed.items():
        if k not in available:
            error("E: symbol '%s' could not be found." % k)

        bound[k] = (v, available[k])

    # default ordening
    bound = bound.items()
    if args.det:
        bound = sorted(bound, key=lambda kv: (len(kv[0]), kv[0]))

    #eprintf("bound", bound,"\n")

    liborder = [] # [(libname, (symname -> reloctyp))]
    for k, v in bound: # k: sym (str)
        # reloc: str
        # libs: lib -> syminfo
        reloc, libs = v[0], v[1]
        if len(libs) <= 1:
            continue
        # preferred: [lib]
        #eprintf("libs",visable(libs.items()))
        preferred = build_preferred_lib_order(k, libs)
        #eprintf("preferred",preferred)
        if not has_good_subordening(preferred, liborder) and not args.fuse_dlfixup_loader:
            message = None
            if args.fuse_dnload_loader and not args.fskip_zero_value:
                message = "WARN: unreconcilable library ordenings '%s' and '%s' "+\
                    "for symbol '%s', you are STRONGLY advised to use `-fskip-zero-value'!"
            if not args.fuse_dnload_loader and not args.fskip_zero_value:
                message = "WARN: unreconcilable library ordenings '%s' and '%s' "+\
                    "for symbol '%s', you might want to enable `-fskip-zero-value'."
            if message is not None:
                message = message % (', '.join(t[0] for t in liborder), ', '.join(preferred), k)
                eprintf(message)

        liborder = add_with_ordening(liborder, preferred, k, reloc)
        #eprintf("new order",visable(liborder),"\n")

    # add all those left without any possible preferred ordening
    for k, v in bound:
        reloc, libs = v[0], v[1]
        if len(libs) == 0:
            assert False, ("??? (%s)" % sym)
        if len(libs) != 1:
            continue
        lib = libs.popitem() # (lib, syminfo)
        #eprintf("lib",lib)
        liborder = add_with_ordening(liborder, [lib[0]], k, reloc, True)
        #eprintf("new order (no preference)",visable(liborder),"\n")

    #eprintf("ordered", visable(liborder))
    return OrderedDict(liborder)

def check_start_sym_ok(objpath):
    # we could use readelf here, but problem is, it doesn't want to give the
    # offset of a symbol into the file, which is needed to check whether _start
    # is actually in .text._start or .text.startup._start .
    # so, time to use hackyelf:

    elf = None
    with open(objpath, 'rb') as f:
        elf = parse(f.read())

    startsym = None
    for sym in elf.symtab:
        if sym.name == "_start":
            startsym = sym
            break

    if startsym is None:
        eprintf("WARNING: no '_start' function found.")
        return False

    startsh, startshndx = None, None
    for i in range(len(elf.shdrs)):
        sh = elf.shdrs[i]

        if sh.name in (".text._start", ".text.startup._start"):
            if startsh is not None:
                eprintf("WARNING: more than one '.text._start' or '.text.startup._start' section found.")
                return False

            startsh = sh
            startshndx = i

    if startsh is None:
        eprintf("WARNING: no '.text._start' or '.text.startup._start' section found.")
        return False

    if startsym.shndx != startshndx:
        eprintf("WARNING: '_start' symbol not in '.text._start' or '.text.startup._start'.")
        return False

    return True

