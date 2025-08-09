#!/usr/bin/env bash

# Check if the user provided enough arguments
if [ $# -ne 2 ]; then
  echo "Usage: $0 <copr_project> <srpm_file>" >&2
  exit 1
fi

COPR_PROJECT="$1"
SRPM_FILE="$2"


dnf install -y copr-cli rpm-build

mkdir -p ~/.config
cat <<EOF > ~/.config/copr
[copr-cli]
login = ${COPR_LOGIN}
username = ${COPR_USERNAME}
token = ${COPR_TOKEN}
copr_url = https://copr.fedorainfracloud.org
EOF

if ! copr build "${COPR_PROJECT}" "$SRPM_FILE" --chroot fedora-42-x86_64; then
  echo "Error: Failed to submit SRPM to COPR project '$COPR_PROJECT'" >&2
  exit 1
fi

echo "SRPM submitted to COPR project '$COPR_PROJECT'."