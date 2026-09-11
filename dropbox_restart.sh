#!/usr/bin/env bash

STATUS="$(dropbox status 2>&1)"

echo "Current Dropbox status: $STATUS"

if echo "$STATUS" | grep -qiE 'Starting|not running|isn.t running'; then
    echo "Dropbox is stuck. Restarting..."

    dropbox stop >/dev/null 2>&1 || true
    pkill -f '[d]ropbox' >/dev/null 2>&1 || true

    sleep 2

    dropbox start >/dev/null 2>&1

    sleep 5
fi

echo
echo "Dropbox status:"
dropbox status
