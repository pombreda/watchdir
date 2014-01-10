#!/bin/bash

./watchdir x.dir y.dir -for create delete hoge &
watcher_pid=$!
sleep 0.1

rm -f x.dir/*
sleep 0.1

touch x.dir/foo
sleep 0.1

rm x.dir/foo
sleep 0.1

mkdir x.dir/bar
sleep 0.1

rmdir x.dir/bar
sleep 0.1

kill $watcher_pid
