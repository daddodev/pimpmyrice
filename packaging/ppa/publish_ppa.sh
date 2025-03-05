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

echo "::group::Installing build dependencies..."
sudo apt-get update &&
    sudo apt-get install -y gpg debmake debhelper devscripts equivs \
        distro-info-data distro-info software-properties-common
echo "::endgroup::"

echo "::group::Importing GPG private key..."
echo "Importing GPG private key..."

GPG_KEY_ID=$(echo "$GPG_PRIVATE_KEY" | gpg --import-options show-only --import | sed -n '2s/^\s*//p')
echo "$GPG_PRIVATE_KEY" | gpg --batch --passphrase "$GPG_PASSPHRASE" --import

echo "Checking GPG expirations..."
if [[ $(gpg --list-keys | grep expired) ]]; then
    echo "GPG key has expired. Please update your GPG key." >&2
    exit 1
fi

echo "::endgroup::"
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

if [[ -n $DEBIAN_DIR ]]; then
    cp -r $DEBIAN_DIR /tmp/workspace/debian
fi

for s in $SERIES; do
    ubuntu_version=$(distro-info --series $s -r | cut -d' ' -f1)


    # TODO
    debuild -us -uc

    debuild -S -sa \
        -k"$GPG_KEY_ID" \
        -p"gpg --batch --passphrase "$GPG_PASSPHRASE" --pinentry-mode loopback"



    dput ppa:$REPOSITORY ../*.changes
    echo "Uploaded $package to $REPOSITORY"

    echo "::endgroup::"
done
