#!/bin/bash

mkdir -p x.dir
rm -f x.dir/*

echo add x.dir 768

touch x.dir/hoge > /dev/null
sleep 1 > /dev/null

# xx pick up the wd from add call above
echo rm 1
sleep 1 >/dev/null

echo quit
