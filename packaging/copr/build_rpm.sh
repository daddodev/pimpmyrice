#!/bin/bash

# Arguments:
# 1: Package Name
# 2: Version
# 3: Release (e.g., 1, 2)
# 4: License
# 5: Author Name
# 6: Author Email

PACKAGE_NAME=$1
VERSION=$2
RELEASE=$3
LICENSE=$4
AUTHOR_NAME=$5
AUTHOR_EMAIL=$6
DATE=$(date +"%a %b %d %Y")

# Check if the user provided enough arguments
if [ $# -ne 6 ]; then
  echo "Usage: $0 <package_name> <version> <release> <license> <author_name> <author_email" >&2
  exit 1
fi

# Set paths for RPM packaging
RPMBUILD_DIR=~/rpmbuild
SPEC_FILE="${RPMBUILD_DIR}/${PACKAGE_NAME}.spec"
SOURCE_DIR="${RPMBUILD_DIR}/SOURCES"
BUILD_DIR="${RPMBUILD_DIR}/BUILD"
INSTALL_DIR="${RPMBUILD_DIR}/BUILDROOT"
RPM_DIR="${RPMBUILD_DIR}/RPMS"

# Create necessary directories
mkdir -p "$RPMBUILD_DIR" "$SOURCE_DIR" "$BUILD_DIR" "$INSTALL_DIR"

# Copy the tarball from the dist folder to SOURCES
cp "dist/${PACKAGE_NAME}-${VERSION}.tar.gz" "$SOURCE_DIR/"

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

echo "Created spec file: $SPEC_FILE"

echo "Source tarball: $SOURCE_DIR/${PACKAGE_NAME}-$VERSION.tar.gz"

# Install build dependencies
dnf install -y rpmdevtools
rpmdev-setuptree
echo "Installed build dependencies"

# Install build dependencies in pimpmyrice.spec
dnf builddep -y ~/rpmbuild/pimpmyrice.spec
echo "Installed build dependencies for pimpmyrice.spec"

# Build the RPM package
rpmbuild -ba "$SPEC_FILE"
echo "Built RPM package"

# Move the RPM package to the RPMS directory
mv $RPM_DIR/noarch/*.rpm ./dist/
echo "Moved RPM package to dist directory"
