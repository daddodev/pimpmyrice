#!/usr/bin/env bash
set -euo pipefail

# Ensure dependencies are installed (for Ubuntu GitHub runner)
echo "Installing required packages..."
sudo apt-get update
sudo apt-get install -y rpm copr-cli

# Usage: publish_copr.sh <copr_project> <rpm_dir> <email>
COPR_PROJECT="$1"
RPM_DIR="$2"
EMAIL="$3"

if [[ -z "$COPR_PROJECT" || -z "$RPM_DIR" || -z "$EMAIL" ]]; then
  echo "Usage: $0 <copr_project> <rpm_dir> <email>"
  exit 1
fi

if ! command -v copr-cli &>/dev/null; then
  echo "Error: copr-cli is not installed. Please install it and configure authentication."
  exit 2
fi

if [[ ! -d "$RPM_DIR" ]]; then
  echo "Error: RPM directory '$RPM_DIR' does not exist."
  exit 3
fi

# Generate SRPM
SPEC_FILE="packaging/rpm/pimpmyrice.spec"
TARBALL=$(ls dist/pimpmyrice-*.tar.gz | head -n1)

if [[ ! -f "$SPEC_FILE" ]]; then
  echo "Error: Spec file '$SPEC_FILE' not found."
  exit 5
fi

if [[ ! -f "$TARBALL" ]]; then
  echo "Error: Source tarball '$TARBALL' not found."
  exit 6
fi

echo "Generating SRPM from $SPEC_FILE and $TARBALL..."
rpmbuild --define "_sourcedir $(pwd)/dist" \
         --define "_srcrpmdir $RPM_DIR" \
         -bs "$SPEC_FILE"

SRPM_FILES=("$RPM_DIR"/*.src.rpm)
if [[ ! -e "${SRPM_FILES[0]}" ]]; then
  echo "Error: No SRPM files found in '$RPM_DIR'."
  exit 4
fi

echo "Uploading SRPMs to COPR project: $COPR_PROJECT"
for srpm in "${SRPM_FILES[@]}"; do
  echo "Uploading $srpm..."
  copr-cli build "$COPR_PROJECT" "$srpm" --chroot fedora-39-x86_64
  # Remove or adjust --chroot as needed for your project
  # Optionally, you can add more chroots or make it a parameter
  # The email argument is not directly used by copr-cli, but could be used for logging or notifications
  # echo "Submitted by: $EMAIL"
done

echo "All SRPMs submitted to COPR project '$COPR_PROJECT'."
