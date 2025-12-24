#!/bin/bash
cd /home/ubuntu/outlook-email-export
source venv/bin/activate
exec python mcp_server/server.py
