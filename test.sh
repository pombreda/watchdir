#!/bin/bash

rm -fr x.dir/
mkdir -p x.dir/pre-existing-subdir
touch x.dir/pre-existing-file

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

# remove a regular file
rm x.dir/foo
sleep 0.2

# rmdir
rm -fr x.dir/pre-existing-subdir
sleep 0.2

# xx not getting delete events for descendents in recursive delete.
#    seems like recursive clean up must be implemented.
mkdir x.dir/subdir/grand-sub-dir
echo hi > x.dir/subdir/grand-sub-dir/hoge

rm -fr x.dir/subdir
sleep 0.2

#kill $!
#wait $!

