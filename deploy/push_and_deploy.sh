#!/usr/bin/env bash
# Локальный деплой на VPS: ./deploy/push_and_deploy.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SERVER="root@201.51.16.202"
APP_DIR="/opt/prediction-sport-bot"
PASSWORD="${DEPLOY_PASSWORD:?Задайте DEPLOY_PASSWORD}"

export COPYFILE_DISABLE=1
tar czf /tmp/psb-deploy.tgz \
  --exclude='./venv' \
  --exclude='./.git' \
  --exclude='**/__pycache__' \
  --exclude='**/._*' \
  --exclude='**/.DS_Store' \
  --exclude='./bin/ngrok' \
  --exclude='./.env' \
  -C "$ROOT" .

expect <<EXPECT_EOF
set timeout 180
set password "$PASSWORD"

proc scp_file {local remote} {
    global password
    spawn scp -o StrictHostKeyChecking=no \$local \$remote
    expect {
        -re "password:|Password:" { send "\$password\\r"; exp_continue }
        eof
    }
}

proc ssh_cmd {cmd} {
    global password
    spawn ssh -o StrictHostKeyChecking=no $SERVER \$cmd
    expect {
        -re "password:|Password:" { send "\$password\\r"; exp_continue }
        eof
    }
}

ssh_cmd "mkdir -p $APP_DIR/credentials"
scp_file "/tmp/psb-deploy.tgz" "$SERVER:/tmp/psb-deploy.tgz"
scp_file "$ROOT/.env" "$SERVER:$APP_DIR/.env" 
scp_file "$ROOT/credentials/google-service-account.json" "$SERVER:$APP_DIR/credentials/google-service-account.json"
ssh_cmd "cd $APP_DIR && tar xzf /tmp/psb-deploy.tgz && chmod +x deploy/remote_setup.sh && bash deploy/remote_setup.sh"
EXPECT_EOF
