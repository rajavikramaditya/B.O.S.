#!/usr/bin/env bash
{
  echo '---'
  date -Is
  uptime
  free -h
  df -h /
  docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}' 2>/dev/null || true
} >> /var/log/neena-health.log
