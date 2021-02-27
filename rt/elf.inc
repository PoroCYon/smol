; vim: set ft=nasm:

%if __BITS__ == 32
%define EI_CLASS        (1) ; 1 == 32-bit
%else
%define EI_CLASS        (2) ; 2 == 64-bit
%endif
%define EI_DATA         (1) ; 1 == little-endian
%define EI_VERSION      (1) ; current
%define EI_OSABI        (3) ; Linux
%define EI_OSABIVERSION (1) ; current

%define ELF_TYPE (2) ; 2 == executable

%ifndef ELF_MACHINE
%if __BITS__ == 32
%define ELF_MACHINE ( 3) ;  3 == i386
%else
%define ELF_MACHINE (62) ; 62 == x86_64
%endif
%endif

; segment to be loaded into memory
%define PT_LOAD    (1)
; ptr to the dynamic table (ElfXX_Dyn)
%define PT_DYNAMIC (2)
; program interpreter to use (null-terminated string)
%define PT_INTERP  (3)

%define PHDR_R (4)
%define PHDR_W (2)
%define PHDR_X (1)

; end of dynamic table
%define DT_NULL   ( 0)
; needed library name (offset to str in .dynstr)
%define DT_NEEDED ( 1)
; start of a table of strings (null-termiated strings one following the other, .dynstr)
%define DT_STRTAB ( 5)
; offset to table of symbols imported from elsewhere, and exported symbols (ElfXX_Sym, .dynsym)
%define DT_SYMTAB ( 6)
; "for debugging purposes, undefined" --> value filled in by ld.so with a pointer to a struct r_debug
%define DT_DEBUG  (21)

; offset to relocation table (ElfXX_Rel)
%define DT_REL      (17)
; offset to relocation-with-addend table (ElfXX_Rela)
%define DT_RELA     ( 7)
; offset to PLT relocation table (Rel or Rela, depending on DT_PLTREL)
%define DT_JMPREL   (23)
; is either DT_REL or DT_RELA, signifies the type of relocation used for DT_JMPREL
%define DT_PLTREL   (20)
; size of one element of DT_JMPREL, should be in accordance with DT_PLTREL
%define DT_PLTRELSZ ( 2)
; "processor defined value" --> offset to the GOT (.got.plt)
%define DT_PLTGOT   ( 3)

%if __BITS__ == 32
%define ELF_R_INFO(sym,type) (((sym) <<  8) | (type))
%else
%define ELF_R_INFO(sym,type) (((sym) << 32) | (type))
%endif

%if __BITS__ == 64
%define R_JUMP_SLOT (7)
%endif

%define ST_NAME_OFF       ( 0)
%define ST_INFO__STT_MASK (15)
%define STT_GNU_IFUNC     (10)

;  ,---- not 16? ; what's this comment??!
; v
%if __BITS__ == 32
%define D_UN_PTR_OFF         ( 4)
%define ST_VALUE_OFF         ( 4)
%define ST_INFO_OFF          (12)
%define SYMTAB_SIZE          (16)
%define ELF_DYN_SZ           ( 8)
%else
%define D_UN_PTR_OFF         ( 8)
%define ST_VALUE_OFF         ( 8)
%define ST_INFO_OFF          ( 4)
%define SYMTAB_SIZE          (24)
%define ELF_DYN_SZ           (16)
%endif

%if __BITS__ == 32
%define R_DEBUG_VERSION_OFF (0)
%define R_DEBUG_MAP_OFF     (4)
%define R_DEBUG_BRK_OFF     (8)
%else
%define R_DEBUG_VERSION_OFF  ( 0)
%define R_DEBUG_MAP_OFF      ( 8)
%define R_DEBUG_BRK_OFF      (16)
%endif

