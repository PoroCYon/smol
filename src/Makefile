
all: fixup-hax
#.bin

fixup-hax: fixup-hax.asm
	nasm -I../rt/ -fbin -o "$@" "$<"
	chmod +x "$@"
	wc -c "$@"

#fixup-hax.o: fixup-hax.asm
#	nasm -g -I../rt/ -felf64 -o "$@" "$<"
#
#fixup-hax.elf: fixup-hax.o
#	ld -L../ld/ -Tlink_x86_64.ld -I~/src/glibc/inst/lib/ld-linux-x86-64.so.2 -o "$@" "$<"
#	chmod +x "$@"
#
#fixup-hax.bin: fixup-hax.elf
#	objcopy -O binary "$<" "$@"
#	chmod +x "$@"

clean:
	$(RM) -v fixup-hax.bin fixup-hax.o fixup-hax.elf fixup-hax

.PHONY: all clean
