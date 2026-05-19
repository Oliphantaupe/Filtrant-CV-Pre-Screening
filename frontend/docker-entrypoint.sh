#!/bin/sh
set -e
PORT="${PORT:-8080}"
envsubst '${PORT}' < /etc/nginx/nginx.template.conf > /etc/nginx/conf.d/default.conf
exec nginx -g 'daemon off;'
