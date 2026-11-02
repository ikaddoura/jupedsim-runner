#!/usr/bin/env bash
# Signs every Mach-O file in dist/jps-runner with a Developer ID, packs a DMG, notarizes and
# staples it. Run locally on a Mac; the certificate and the credentials never go to CI.
#
#   DEVELOPER_ID="Developer ID Application: <Name> (<TEAMID>)" \
#   NOTARY_PROFILE=<keychain profile> \
#   scripts/sign-and-notarize-macos.sh <version> <arch>
#
# Create the keychain profile once:
#   xcrun notarytool store-credentials <profile> --apple-id <id> --team-id <TEAMID>
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION="$1"; ARCH="$2"
: "${DEVELOPER_ID:?}" "${NOTARY_PROFILE:?}"
DIR=dist/jps-runner
ENT=packaging/entitlements.plist
DMG="dist/jps-runner-${VERSION}-macos-${ARCH}.dmg"

# Inside out: libraries first, the executable last (its signature covers nothing else,
# but signing it last keeps the order obvious).
find "$DIR" -type f \( -name '*.dylib' -o -name '*.so' \) -print0 |
  xargs -0 -n 20 codesign --force --timestamp --options runtime --sign "$DEVELOPER_ID"
# Other Mach-O files without the usual suffix (e.g. Python's own library).
find "$DIR" -type f -perm +111 ! -name '*.dylib' ! -name '*.so' -print0 |
  while IFS= read -r -d '' f; do
    if file -b "$f" | grep -q 'Mach-O'; then
      codesign --force --timestamp --options runtime --entitlements "$ENT" --sign "$DEVELOPER_ID" "$f"
    fi
  done
codesign --verify --strict --verbose=2 "$DIR/jps-runner"

rm -f "$DMG"
hdiutil create -volname "jps-runner $VERSION" -srcfolder "$DIR" -ov -format UDZO "$DMG"
codesign --force --timestamp --sign "$DEVELOPER_ID" "$DMG"
xcrun notarytool submit "$DMG" --keychain-profile "$NOTARY_PROFILE" --wait
xcrun stapler staple "$DMG"
xcrun stapler validate "$DMG"
spctl --assess --type open --context context:primary-signature -v "$DMG"
echo "Done: $DMG"
