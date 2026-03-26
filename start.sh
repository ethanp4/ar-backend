#!/bin/bash

echo starting discovery_server.py and receive_image.py

python3 discovery_server.py &
PID1=$!

python3 receive_image.py &
PID2=$!

#this will kill both scripts when ctrl c is pressed
trap "kill $PID1 $PID2; exit" INT

#exit the script once both 
wait $PID1 $PID2