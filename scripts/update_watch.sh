#!/bin/bash
# Run the Python script as cron job
python3 "${@}" "${@}" > /tmp/cninfo-$(date +%Y%m%d_%H%M%S).txt 2>&1
