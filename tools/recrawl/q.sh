#!/bin/bash
# q.sh SQLFILE : run a read query file through ./nz psql (unaligned, '|' separated)
cd /mnt/e/Nizam_e_Qanoon; ./nz psql -tA -F '|' < "$1"
