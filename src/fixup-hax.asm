; vim: set ft=nasm et:

bits 64

%include "elf.inc"
%include "linkscr.inc"

;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

[section .header]

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
    dq dynamic, 0       ; p_vaddr, p_paddr
    dq dynamic.end - dynamic ; p_filesz
    dq dynamic.end - dynamic ; p_memsz
    dq 0                ; p_align
phdr.load:
    dd PT_LOAD          ; p_type
    dd PHDR_R | PHDR_W | PHDR_X ; p_flags
    dq 0                ; p_offset
    dq ehdr, 0          ; p_vaddr, p_paddr
    dq END.FILE-ehdr;_smol_total_filesize ; p_filesz
    dq END.MEM-ehdr;_smol_total_memsize ; p_memsz
    dq 0x1000           ; p_align
phdr.end:

;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

[section .rodata.interp]

global _INTERP
_INTERP:
interp:
    db "/lib64/ld-linux-x86-64.so.2", 0
interp.end:

[section .rodata.dynamic]

global _DYNAMIC
_DYNAMIC:
dynamic:
dynamic.strtab:
    dq DT_STRTAB        ; d_tag
    dq _dynstr          ; d_un.d_ptr
dynamic.debug:
    dq DT_DEBUG         ; d_tag
_DEBUG:
    dq 0                ; d_un.d_ptr
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
dynamic.pltrelsz:
    dq DT_PLTRELSZ
    dq 24 ; sizeof(Elf64_Rela)
dynamic.pltrel:
    dq DT_PLTREL
    dq DT_RELA
dynamic.jmprel:
    dq DT_JMPREL
    dq _rela_plt

; maybe let's give ld.so a bit more info
; strsz (size of .dynstr), syment (size of one .dynsym)

dynamic.end:
    dq DT_NULL

[section .rodata]

global _dynstr
_dynstr:
    db 0
    _symbols.libc: db "libc.so.6",0
    _symbols.libc.puts: db "puts",0

global _rela_plt
_rela_plt:
    ;; entry 0
    dq ehdr ; address
    dq ELF_R_INFO(1,R_JUMP_SLOT) ; symidx, type
    dq 0 ; addend

global _dynsym
_dynsym:
    ;; entry 0
    dd 0 ; name
    db 0 ; info
    db 0 ; other
    dw 0 ; shndx
    dq 0 ; value
    dq 0 ; size
    ;; entry 1
    dd _symbols.libc.puts - _dynstr ; name
    db 0 ; info
    db 0 ; other
    dw 0 ; shndx
    dq 0 ; value
    dq 0 ; size


;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

%define SYS_exit 60

[section .text]

global _smol_start
_smol_start:
    ;mov rax, [rel _DEBUG]
    ;mov rax, [rax + R_DEBUG_MAP_OFF] ; linkmap
    ;mov rbx, [rel _gotplt]
    mov rcx, [rel linkmap]
    mov rdx, [rel fixup] ; _dl_runtime_resolve_xsavec on my machine

    lea rsi, [rel somestr]
    lea rdi, [rel somestr]

    ;.loopme: jmp short .loopme

    call bluh

    lea rsi, [rel somestr]
    lea rdi, [rel somestr]

    call [ehdr]

    mov al, SYS_exit
    syscall

bluh:
    push 0
    push rcx
     jmp rdx

[section .rodata]

somestr:
    db "hello world",0

;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

[section .data.got.plt]

global _GLOBAL_OFFSET_TABLE_
_GLOBAL_OFFSET_TABLE_:
_gotplt:
    dq _DYNAMIC
linkmap:
    dq 0 ; address of link map, filled in by ld.so
fixup:
    dq 0 ; address of _dl_runtime_resolve, which is a trampoline calling _dl_fixup

END.FILE:

[section .data]

;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

[section .bss]



END.MEM:

