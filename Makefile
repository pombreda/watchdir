
name=watchdir

all: $(name)
clean:
	rm -f $(name)

# $(name): $(name).c

%: %.c
	gcc -g -Wall -o $@ $<

test: watchdir
	./test.sh

-include local.mk
