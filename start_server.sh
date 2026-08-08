#!/bin/bash
cd /workspace/project/dece_msg
python -m decemsg > server.log 2>&1 &
sleep 3
curl -s http://localhost:8000/health
