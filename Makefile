OBJDIR := obj
BINDIR := bin
SRCDIR := rt
TESTDIR:= test

NASM ?= nasm
OBJCOPY ?= objcopy

BITS ?= $(shell getconf LONG_BIT)

# -mpreferred-stack-boundary=3 messes up the stack and kills SSE!

COPTFLAGS=-Os -fno-plt -fno-stack-protector -fno-stack-check -fno-unwind-tables \
  -fno-asynchronous-unwind-tables -fomit-frame-pointer -ffast-math -no-pie \
  -fno-pic -fno-PIE -ffunction-sections -fdata-sections -fno-plt \
  -fmerge-all-constants -mno-fancy-math-387 -mno-ieee-fp
CXXOPTFLAGS=$(COPTFLAGS) -fno-exceptions \
  -fno-rtti -fno-enforce-eh-specs -fnothrow-opt -fno-use-cxa-get-exception-ptr \
  -fno-implicit-templates -fno-threadsafe-statics -fno-use-cxa-atexit

CFLAGS=-g -Wall -Wextra -Wpedantic -std=gnu11 -nostartfiles -fno-PIC $(COPTFLAGS) #-DUSE_DL_FINI
CXXFLAGS=-g -Wall -Wextra -Wpedantic -std=c++11 $(CXXOPTFLAGS) -nostartfiles -fno-PIC

COMMONFLAGS := -m$(BITS) $(shell pkg-config --cflags sdl2) $(shell pkg-config --cflags-only-I gtk+-3.0)

CFLAGS   += $(COMMONFLAGS)
CXXFLAGS += $(COMMONFLAGS)

ifeq ($(BITS),32)
# I think prescott is basically nocona but 32-bit only, althought I'm not sure
# if this one is optimal
CFLAGS += -march=prescott
else
# I've heard nocona gets slightly smaller binaries than core2
CFLAGS += -march=nocona
endif

LIBS_hello-_start := -lc
LIBS_hello := -lm -lc
LIBS_flag := -lX11 -lm -lc
LIBS_sdl := $(shell pkg-config --libs-only-l sdl2) -lc
LIBS_gtkgl := $(shell pkg-config --libs-only-l gtk+-3.0) -lGL -lc
LIBS_gtkgl-_start := $(LIBS_gtkgl)

PWD ?= .

SMOLFLAGS = --smolrt "$(PWD)/rt" --smolld "$(PWD)/ld" \
  --verbose -g #--hang-on-startup #-fuse-dlfixup-loader #-fuse-nx #--keeptmp
# -fuse-dnload-loader -fskip-zero-value -fuse-nx -fskip-entries -fuse-dt-debug
# -fuse-dl-fini -fno-start-arg -funsafe-dynamic

PYTHON3 ?= python3

all: $(BINDIR)/hello-crt $(BINDIR)/sdl-crt $(BINDIR)/flag $(BINDIR)/hello-_start $(BINDIR)/gtkgl-_start $(BINDIR)/gtkgl-crt

clean:
	@$(RM) -vrf $(OBJDIR) $(BINDIR)

%/:
	@mkdir -vp "$@"

.SECONDARY:

$(OBJDIR)/%.lto.o: $(SRCDIR)/%.c $(OBJDIR)/
	$(CC) -flto $(CFLAGS) -c "$<" -o "$@"
$(OBJDIR)/%.lto.o: $(TESTDIR)/%.c $(OBJDIR)/
	$(CC) -flto $(CFLAGS) -c "$<" -o "$@"

$(OBJDIR)/%.o: $(SRCDIR)/%.c $(OBJDIR)/
	$(CC) $(CFLAGS) -c "$<" -o "$@"
$(OBJDIR)/%.o: $(TESTDIR)/%.c $(OBJDIR)/
	$(CC) $(CFLAGS) -c "$<" -o "$@"

$(BINDIR)/%.dbg $(BINDIR)/%: $(OBJDIR)/%.o $(BINDIR)/
	$(PYTHON3) ./smold.py --debugout "$@.dbg" $(SMOLFLAGS) --ldflags=-Wl,-Map=$(BINDIR)/$*.map $(LIBS_$*) "$<" "$@"
	$(PYTHON3) ./smoltrunc.py "$@" "$(OBJDIR)/$(notdir $@)" && mv "$(OBJDIR)/$(notdir $@)" "$@" && chmod +x "$@"

$(BINDIR)/%-crt.dbg $(BINDIR)/%-crt: $(OBJDIR)/%.lto.o $(OBJDIR)/crt1.lto.o $(BINDIR)/
	$(PYTHON3) ./smold.py --debugout "$@.dbg" $(SMOLFLAGS) --ldflags=-Wl,-Map=$(BINDIR)/$*-crt.map $(LIBS_$*) "$<" $(OBJDIR)/crt1.lto.o "$@"
	$(PYTHON3) ./smoltrunc.py "$@" "$(OBJDIR)/$(notdir $@)" && mv "$(OBJDIR)/$(notdir $@)" "$@" && chmod +x "$@"

.PHONY: all clean

