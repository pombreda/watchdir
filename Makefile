
name=watchdir

all: $(name)
clean:
	rm -f $(name)

# $(name): $(name).c

%: %.c
	gcc -g -Wall -o $@ $<

test: watchdir
	./test.sh

tailall:
	find /var/log/ -type d \
	| python watchdir.py watch - \
	| python watchdir.py tailall \
	2> x.err > x.out
