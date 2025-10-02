#!/bin/bash
# Quick MySQL connection script
# MySQL is running on port 3306 (default MySQL port)

mysql -u root -ppassword -h 127.0.0.1 --port=3306 "$@"

