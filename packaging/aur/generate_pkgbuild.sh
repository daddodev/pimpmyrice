#!/bin/bash

# Check if the user provided enough arguments
if [ $# -ne 5 ]; then
    echo "Usage: $0 <pkgname> <pkgver> <author_name> <email> <license>" >&2
    exit 1
fi

# Variables from command line arguments
PKGNAME=$1
PKGVER=$2
AUTHOR=$3
EMAIL=$4
LICENSE=$5

# Read the template and replace placeholders with actual values
sed \
    -e "s/{{pkgname}}/$PKGNAME/g" \
    -e "s/{{pkgver}}/$PKGVER/g" \
    -e "s/{{author}}/$AUTHOR/g" \
    -e "s/{{email}}/$EMAIL/g" \
    -e "s/{{license}}/$LICENSE/g" \
    PKGBUILD.template > PKGBUILD

echo "PKGBUILD generated successfully!"
exit 0
