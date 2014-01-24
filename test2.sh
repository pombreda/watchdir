#!/bin/bash

rm -fr x.dir/
mkdir x.dir

./watchdir.py watch x.dir/ &
watchdir_pid=$!
sleep 0.1

# create a file
echo hi > x.dir/foo
sleep 0.1

# append to a file
echo ho >> x.dir/foo
sleep 0.1

# mkdir
mkdir x.dir/subdir
sleep 0.1

# write to a deeper file
(echo hi; sleep 0.1) > x.dir/subdir/bar
sleep 0.2

# kill $!
# wait $!

