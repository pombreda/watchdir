
name=watchdir

all: $(name)
clean:
	rm -f $(name)

# $(name): $(name).c

%: %.c
	gcc -g -Wall -o $@ $<

t-watchdir: $(name)
	./$(name) x.dir y.dir -for create delete

test: all
	./test.sh

u: watchdir
	./watchdir

t: watchcore
	./driver.sh | ./watchcore


