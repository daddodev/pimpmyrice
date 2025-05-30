#!/usr/bin/env bash

set -e

echo "::group::Get input variables..."
if [ $# -ne 3 ]; then
    echo "Usage: $0 <deb_dir> <tarball> <email>" >&2
    exit 1
fi

DEBIAN_DIR=$1
TARBALL=$2
DEBEMAIL=$3


export DEBMAKE_ARGUMENTS="-b :python3"
export DEBEMAIL=$DEBEMAIL
echo "::endgroup::"

export DEBIAN_FRONTEND=noninteractive

sudo apt-get update &&
    sudo apt-get install -y debmake debhelper devscripts equivs \
        software-properties-common

rm -rf /tmp/workspace
mkdir -p /tmp/workspace/source
cp $TARBALL /tmp/workspace/source
if [[ -n $DEBIAN_DIR ]]; then
    cp -r $DEBIAN_DIR /tmp/workspace/debian
fi

cd /tmp/workspace/source
tar -xf ./* && cd ./*/

echo "Making non-native package..."
debmake $DEBMAKE_ARGUMENTS

if [[ -n $DEBIAN_DIR ]]; then
    cp -r /tmp/workspace/debian/* debian/
fi

package=$(dpkg-parsechangelog --show-field Source)
pkg_version=$(dpkg-parsechangelog --show-field Version | cut -d- -f1)

rm -rf debian/changelog
dch --create --distribution "$(lsb_release -cs)" \
    --package "$package" \
    --newversion "$pkg_version" \
    "New upstream release"

# Install build dependencies
sudo mk-build-deps --install --remove --tool='apt-get -o Debug::pkgProblemResolver=yes --no-install-recommends --yes' debian/control

debuild -b -us -uc

echo "Build completed for $package"

rm -rf /tmp/debs/
mkdir /tmp/debs/
cp ../*.deb /tmp/debs/
echo "copied .deb to /tmp/debs"
