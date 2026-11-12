# Ending table: builder, checks and the search built against the table.
# Portable flags: no -march=native, so the same build runs on x86-64 and Apple silicon.
CXX ?= g++
# ARCH: -march=native on x86-64 (BMI2 pext, hardware popcount); use ARCH=-mcpu=native or ARCH= on Apple silicon.
# The table bytes do not depend on these flags (integer arithmetic only).
ARCH ?= -march=native
CXXFLAGS ?= -O2 -std=c++17 $(ARCH) -Wall -Wextra -Wno-unused-parameter
LDFLAGS ?= -pthread

all: endtable_build endtable_tool sure_cpp_table

endtable_build: endtable_build.cpp endtable.h endtable_eval.h sha256.h
	$(CXX) $(CXXFLAGS) -o $@ endtable_build.cpp $(LDFLAGS)

endtable_tool: endtable_tool.cpp endtable.h endtable_eval.h sha256.h
	$(CXX) $(CXXFLAGS) -o $@ endtable_tool.cpp $(LDFLAGS)

# sure.cpp with the hook switched on (T7). Built from the parent directory so that its #include "endtable/endtable.h" resolves.
sure_cpp_table: ../sure.cpp endtable.h
	cd .. && $(CXX) -O2 -march=native -std=c++17 -DENDTABLE -o endtable/sure_cpp_table sure.cpp

clean:
	rm -f endtable_build endtable_tool sure_cpp_table

.PHONY: all clean
