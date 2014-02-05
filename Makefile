
name=watchdir

all: $(name)
clean:
	rm -f $(name)

# $(name): $(name).c

%: %.c
	gcc -g -Wall -o $@ $<

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

test: watchdir
	./test.sh


t:
	python watchdir.py watch /var/log

tt:
	find /var/log/ctv -type d \
	| grep -v twitter \
	| python watchdir.py watch - \
	| tee x.log


ttt:
	cat x.log \
	| python watchdir.py tailall 

ta:
	find /var/log/ctv -type d \
	| grep -v twitter \
	| python watchdir.py watch - \
	| python watchdir.py tailall \



m:
	cat x.log \
	| python watchdir.py _modified
 
