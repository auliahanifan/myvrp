#!/bin/bash
ssh jetorbit_aulia << 'EOF'
cd myvrp
git pull origin main
sh docker_run.sh
EOF
