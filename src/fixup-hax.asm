; vim: set ft=nasm et:

bits 64

%include "elf.inc"
%include "linkscr.inc"

org 0x10000

;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

global _EHDR
_EHDR:
ehdr:
    ; e_ident
    db 0x7F, "ELF"
    db EI_CLASS, EI_DATA, EI_VERSION, 0;EI_OSABI
    db 0;EI_OSABIVERSION
    times 7 db 0
    dw ELF_TYPE         ; e_type
    dw ELF_MACHINE      ; e_machine
    dd EI_VERSION       ; e_version
    dq _smol_start      ; e_entry
    dq phdr - ehdr      ; e_phoff
    dq 0                ; e_shoff
    dd 0                ; e_flags
    dw ehdr.end - ehdr  ; e_ehsize
    dw phdr.load - phdr.dynamic ; e_phentsize

;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

global _PHDR
_PHDR:
phdr:
phdr.interp:
    dd PT_INTERP        ; p_type    ; e_phnum, e_shentsize
    dd 0                ; p_flags   ; e_shnum, e_shstrndx

ehdr.end:
    dq interp - ehdr    ; p_offset
    dq interp, interp   ; p_vaddr, p_paddr

    dq interp.end - interp ; p_filesz
    dq interp.end - interp ; p_memsz
    dq 0                ; p_align
phdr.dynamic:
    dd PT_DYNAMIC       ; p_type    ; e_phnum, e_shentsize
    dd 0                ; p_flags   ; e_shnum, e_shstrndx
    dq dynamic - ehdr   ; p_offset
    dq dynamic;, 0       ; p_vaddr, p_paddr

global _INTERP
_INTERP:
interp:
    db "/lib64/ld-linux-x86-64.so.2",0
interp.end:
    dd 0

    ;dq dynamic.end - dynamic ; p_filesz
    ;dq dynamic.end - dynamic ; p_memsz
    ;dq 0                ; p_align

phdr.load:
    dd PT_LOAD          ; p_type
    dd PHDR_R | PHDR_W | PHDR_X ; p_flags
    dq 0                ; p_offset
    dq ehdr, 0          ; p_vaddr, p_paddr
    dq END.FILE-ehdr ; p_filesz
    dq END.MEM-ehdr ; p_memsz
    dd 0x1000           ; p_align
phdr.end:

;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

;global _INTERP
;_INTERP:
;interp:
;    db "/lib64/ld-linux-x86-64.so.2",0
;interp.end:
;    dd 0

global _DYNAMIC
_DYNAMIC:
dynamic:
dynamic.strtab:
    dq DT_STRTAB        ; d_tag
    dq _dynstr          ; d_un.d_ptr
;dynamic.debug:
;    dq DT_DEBUG         ; d_tag
;_DEBUG:
;    dq 0                ; d_un.d_ptr
dynamic.needed:
    dq DT_NEEDED
    dq (_symbols.libc - _dynstr)
dynamic.symtab:
    dq DT_SYMTAB
    dq _dynsym;0 ; none

; some magic
dynamic.pltgot:
    dq DT_PLTGOT
    dq _gotplt
;dynamic.pltrelsz:
;    dq DT_PLTRELSZ
;    dq 24 ; sizeof(Elf64_Rela)
;dynamic.pltrel:
;    dq DT_PLTREL
;    dq DT_RELA
dynamic.jmprel:
    dq DT_JMPREL
    dq _rela_plt
dynamic.end:
    db DT_NULL

;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

;global _rela_plt
;_rela_plt:
;    ;; entry 0
;    dq ehdr ; address
;    dq ELF_R_INFO(0,R_JUMP_SLOT) ; symidx, type
;    dq 0 ; addend

global _dynsym
_dynsym:
    ;; entry 0
    dd _symbols.libc.puts - _dynstr ; name
    db 0 ; info
    ; rest is ignored

;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

%define SYS_exit 60

global _smol_start
_smol_start:
     lea rsi, [rel _gotplt+8]
   lodsq ; linkmap -> rax
    xchg rax, rdx
   lodsq ; fixup -> rax

    call resolve_first
retaddr:
         ; and now we can call the resolved symbol
     lea rdi, [rel symname]
    call rax
         ; more symbols can also be looked up by calling [ehdr]

     mov al, SYS_exit
;    push 42
;     pop rdi
 syscall ; %rdi, %rsi, %rdx, %r10, %r8 and %r9

resolve_first:
      pop rsi
     push rsi
     ;mov rsi, [rsp]
      sub si, retaddr-symname

         ; %rdi, %rsi, %rdx, %rcx, %r8 and %r9
         ; rdi = handle (RTLD_DEFAULT)
         ; rsi = name (symbol name)
         ; rdx = who (NULL is fine)
    push 0   ; symbol ordinal (_dl_sym)
    push rdx ; link_map

    push 0
    ;push 0
     pop rdi ; handle (RTLD_DEFAULT)
    push rdi
     pop rdx ; who (NULL, "If the address is not recognized the call comes from
             ; the main program (we hope)" -glibc src)
     ;lea rsi, [rel symname] ; symbol name

     jmp rax

;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

symname:
    db "puts",0

;helloworld:
;    db "hello, world!",0

global _dynstr
_dynstr:
;    db 0
    _symbols.libc: db "libc.so.6",0
    _symbols.libc.puts: db "_dl_sym",0

global _rela_plt
_rela_plt:
    dq ehdr ; address
    db ELF_R_INFO(0,R_JUMP_SLOT) ; symidx, type
    ;dq 0 ; addend

END.FILE:

; yep, GOT in .bss
global _GLOBAL_OFFSET_TABLE_
_GLOBAL_OFFSET_TABLE_:

_gotplt: resq 1;db _DYNAMIC ; not a requirement!
linkmap: resq 1 ; address of link map, filled in by ld.so
fixup:   resq 1 ; address of _dl_runtime_resolve, which is a trampoline calling _dl_fixup

END.MEM:

