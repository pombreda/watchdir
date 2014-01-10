
name=watchdir

all: $(name)
clean:
	rm -f $(name)

$(name): $(name).c
	gcc -g -Wall -o $@ $(name).c

t: $(name)
	./$(name) x.dir y.dir -for create delete


tt: all
	./test.sh

u: watchdir
	./watchdir

