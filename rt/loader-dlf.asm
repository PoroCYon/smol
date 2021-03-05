; vim: set ft=nasm et:

%include "rtld.inc"

%ifdef ELF_TYPE
[section .text.startup.smol]
%else
; not defined -> debugging!
[section .text]
%endif

resolve_first:
   push 0 ; ordinal
   push rcx ; link_map
    jmp rax

%ifndef ELF_TYPE
extern _symbols
extern _gotplt.imports

; register usage:
; r13: _dl_fini address (ABI required, DO NOT OVERWRITE)

global _start
_start:
%endif

global _smol_start
_smol_start:
%ifdef USE_DL_FINI
   xchg r13, rsi ; _dl_fini
%endif
%ifdef HANG_ON_STARTUP
.loopme: jmp short .loopme
%endif

   push _gotplt.linkmap
    pop rsi
   ;lea rsi, [rel _gotplt.linkmap]
  lodsq ; rcx = link_map
   xchg rax, rcx
  lodsq ; rax = _dl_fixup

   push _symbols.libc._dl_sym
   push 0
   push 0
    pop rdx
    pop rdi
    pop rsi
   ;lea rsi, [rel _symbols.libc._dl_sym]
   call resolve_first
.retaddr:
   push _gotplt.imports
   push _symbols
    pop rsi
    pop rdi
   ;lea rsi, [rel _symbols]
   ;lea rdi, [rel _gotplt.imports]
.symloop:   ; rdi = RTLD_DEFAULT (0)
            ; rsi = name
            ; rdx = NULL
       push 0
       push rdi
       push rsi
       push 0
       push 0
        pop rdx
        pop rdi
            ; rsi already ok
%ifndef USE_NX
       call [ehdr]
%else
%error "TODO"
%endif
        pop rsi
        pop rdi
      stosq ; rax (retval) -> gotplt

            ; find end of string
 .strend: lodsb
            and al, al
            jnz short .strend

        mov al, byte [rsi]
        and al, al
        jnz short .symloop

;   xor rbp, rbp ; still 0 from _dl_start_user
%ifndef NO_START_ARG
        ; arg for _start
    mov rdi, rsp
%endif
%ifdef ALIGN_STACK
   push rax
%endif
%ifdef USE_DL_FINI
   xchg rsi, r13 ; _dl_fini
%endif
        ; fallthru to _start
%ifdef ELF_TYPE
global _smol_rt_end:
_smol_rt_end:
%endif

