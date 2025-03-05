#!/usr/bin/env bash

# https://github.com/yuezk/publish-ppa-package/blob/main/build.sh

set -e

echo "::group::Get input variables..."
if [ $# -ne 5 ]; then
    echo "Usage: $0 <deb_dir> <tarball> <email> <gpg_private_key> <gpg_passphrase>" >&2
    exit 1
fi

DEBIAN_DIR=$1
TARBALL=$2
DEBEMAIL=$3
GPG_PRIVATE_KEY=$4
GPG_PASSPHRASE=$5


export DEBEMAIL=$DEBEMAIL
export DEBMAKE_ARGUMENTS="-b :python3"
export DEBIAN_FRONTEND=noninteractive
echo "::endgroup::"

# TODO remove
apt-get update && apt-get install sudo -y


echo "::group::Installing build dependencies..."
sudo apt-get update &&
    sudo apt-get install -y gpg debmake debhelper devscripts equivs \
        distro-info-data distro-info software-properties-common
echo "::endgroup::"

# echo "::group::Importing GPG private key..."
# echo "Importing GPG private key..."
#
# GPG_KEY_ID=$(echo "$GPG_PRIVATE_KEY" | gpg --import-options show-only --import | sed -n '2s/^\s*//p')
# echo "$GPG_PRIVATE_KEY" | gpg --batch --passphrase "$GPG_PASSPHRASE" --import
#
# echo "Checking GPG expirations..."
# if [[ $(gpg --list-keys | grep expired) ]]; then
#     echo "GPG key has expired. Please update your GPG key." >&2
#     exit 1
# fi
#
# echo "::endgroup::"
#
echo "::group::Adding PPA..."
# Add extra PPA if it's been set
if [[ -n "$EXTRA_PPA" ]]; then
    for ppa in $EXTRA_PPA; do
        echo "Adding PPA: $ppa"
        sudo add-apt-repository -y ppa:$ppa
    done
fi
sudo apt-get update
echo "::endgroup::"

if [[ -z "$SERIES" ]]; then
    SERIES=$(distro-info --supported)
fi
#
# Add extra series if it's been set
if [[ -n "$EXTRA_SERIES" ]]; then
    SERIES="$EXTRA_SERIES $SERIES"
fi

mkdir -p /tmp/debs
mkdir -p /tmp/workspace/source
cp $TARBALL /tmp/workspace/source
if [[ -n $DEBIAN_DIR ]]; then
    cp -r $DEBIAN_DIR /tmp/workspace/debian
fi

for s in $SERIES; do
    ubuntu_version=$(distro-info --series $s -r | cut -d' ' -f1)

    echo "::group::Building deb for: $ubuntu_version ($s)"

    cp -r /tmp/workspace /tmp/$s && cd /tmp/$s/source
    tar -xf ./* && cd ./*/

    echo "Making non-native package..."
    debmake $DEBMAKE_ARGUMENTS

    if [[ -n $DEBIAN_DIR ]]; then
        cp -r /tmp/$s/debian/* debian/
    fi

    # Extract the package name from the debian changelog
    package=$(dpkg-parsechangelog --show-field Source)
    pkg_version=$(dpkg-parsechangelog --show-field Version | cut -d- -f1)
    changes="New upstream release"

    # Create the debian changelog
    rm -rf debian/changelog
    dch --create --distribution $s --package $package --newversion $pkg_version-ppa$REVISION~ubuntu$ubuntu_version "$changes"

    # Install build dependencies
    sudo mk-build-deps --install --remove --tool='apt-get -o Debug::pkgProblemResolver=yes --no-install-recommends --yes' debian/control

    # TODO
    debuild -us -uc

    # debuild -S -sa \
    #     -k"$GPG_KEY_ID" \
    #     -p"gpg --batch --passphrase "$GPG_PASSPHRASE" --pinentry-mode loopback"
    #

    cp ../*.deb /tmp/debs
    echo "copied $s .deb to /tmp/debs"

    # dput ppa:$REPOSITORY ../*.changes
    # echo "Uploaded $package to $REPOSITORY"

    echo "::endgroup::"
done
