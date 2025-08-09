#!/usr/bin/env bash

# Check if the user provided enough arguments
if [ $# -ne 6 ]; then
  echo "Usage: $0 <package_name> <version> <release> <license> <author_name> <author_email>" >&2
  exit 1
fi

PACKAGE_NAME="$1"
VERSION="$2"
RELEASE="$3"
LICENSE="$4"
AUTHOR_NAME="$5"
AUTHOR_EMAIL="$6"
DATE=$(date +"%a %b %d %Y")

# Set paths for RPM packaging
RPMBUILD_DIR="/home/builder/rpmbuild"
SPEC_FILE="${RPMBUILD_DIR}/SPECS/${PACKAGE_NAME}.spec"
SOURCE_DIR="${RPMBUILD_DIR}/SOURCES"
BUILD_DIR="${RPMBUILD_DIR}/BUILD"
BUILDROOT_DIR="${RPMBUILD_DIR}/BUILDROOT"
RPM_DIR="${RPMBUILD_DIR}/RPMS"

# Install required tools and build dependencies
dnf install -y rpmdevtools || exit 1

# Ensure build user exists and has a home directory
if ! id builder &>/dev/null; then
  useradd -m -s /bin/bash builder
fi

# Create necessary directories
su builder -c "rpmdev-setuptree"
# rpmdev-setuptree

# Copy the tarball from the dist folder to SOURCES
TARBALL="dist/${PACKAGE_NAME}-${VERSION}.tar.gz"
if [[ ! -f "$TARBALL" ]]; then
  echo "Error: Source tarball $TARBALL not found!"
  exit 1
fi
cp "$TARBALL" "$SOURCE_DIR/"

# Check if the spec.template file exists
SPEC_TEMPLATE_FILE="packaging/copr/spec.template"
if [[ ! -f "$SPEC_TEMPLATE_FILE" ]]; then
  echo "Error: Spec template file $SPEC_TEMPLATE_FILE not found!"
  exit 1
fi

# Create the .spec file from the template
cp "$SPEC_TEMPLATE_FILE" "$SPEC_FILE"

# Replace placeholders in the spec file template
sed -i "s|%{name}|$PACKAGE_NAME|g" "$SPEC_FILE"
sed -i "s|%{version}|$VERSION|g" "$SPEC_FILE"
sed -i "s|%{release}|$RELEASE|g" "$SPEC_FILE"
sed -i "s|%{license}|$LICENSE|g" "$SPEC_FILE"
sed -i "s|%{author_name}|$AUTHOR_NAME|g" "$SPEC_FILE"
sed -i "s|%{author_email}|$AUTHOR_EMAIL|g" "$SPEC_FILE"
sed -i "s|%{date}|$DATE|g" "$SPEC_FILE"
echo "✅ Created spec file: $SPEC_FILE"
echo "📦 Source tarball: $SOURCE_DIR/${PACKAGE_NAME}-${VERSION}.tar.gz"

dnf builddep -y "$SPEC_FILE" || exit 1
echo "✅ Installed build dependencies"

# Build the RPM package as 'builder'
chown -R builder:builder $RPMBUILD_DIR
su builder -c "
  set -euo pipefail
  rpmbuild -ba /home/builder/rpmbuild/SPECS/${PACKAGE_NAME}.spec
"
echo "✅ Built RPM package"

# Copy RPM to dist directory
mkdir -p {rpms,srpms}
find /home/builder/rpmbuild/RPMS/ -name '*.rpm' -exec cp {} ./rpms/ \;
echo "📦 Copied RPM package to ./rpms/"
find /home/builder/rpmbuild/SRPMS/ -name '*.src.rpm' -exec cp {} ./srpms/ \;
echo "📦 Copied SRPM package to ./srpms/"
