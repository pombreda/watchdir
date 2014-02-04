
name=watchdir

all: $(name)
clean:
	rm -f $(name)

# $(name): $(name).c

%: %.c
	gcc -g -Wall -o $@ $<

test: all
	./test.sh

u: watchdir
	./watchdir

t-watchdir: watchdir
	./driver.sh | ./watchdir

t-watchdir2: watchdir
	./driver2.sh | ./watchdir
d:
	./watchdir.py watch x.dir/

w:
	./watchdir.py watch x.dir/

reg:
	./test.sh > x.out.ref 2>&1
	diff x.out x.out.ref

t: watchdir
	./test.sh

