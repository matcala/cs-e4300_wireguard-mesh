#!/bin/bash
for KILLPID in `ps ax | grep 'manager' | awk '{print $1;}'`; do
kill -9 $KILLPID;
done