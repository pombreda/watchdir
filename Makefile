
all: $(engine)

-include local.mk

engine?=watchdir
exe=$(engine) watchdir.py
prefix?=/usr/local
version?=0.1

clean:
	rm -f $(engine)

%: %.c
	gcc -Wall -o $@ $<

test: watchdir
	./test.sh

install: $(exe)
	install $^ $(prefix)/bin/

debify.py:
	wget https://raw.githubusercontent.com/tengu/debify/master/debify.py

debian: watchdir_$(version).deb

watchdir_$(version).deb: debify.py
	echo $(exe) | tr ' ' '\n' | sed 's|^|$(prefix)/bin/|' \
	| python debify.py pack_paths watchdir_$(version) 'command that watches for events under a directory'
