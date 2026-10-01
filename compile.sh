#!/usr/bin/env bash
# Builds `build/macos/Financial Tracker.app` and packages it into `Financial Tracker.dmg`.
set -euo pipefail
cd "$(dirname "$0")"

# Flet's macOS template targets macOS 11.0 (and Flutter's FlutterMacOS pod 10.15), but Xcode 27
# only supports 12.0+. There is no flet setting for it, and flet re-renders `build/flutter` from
# the template whenever its build inputs change (flet version, project version, ...), resetting
# any fix made there. So the bump is applied before building, and re-applied after a failed
# build in case that build re-rendered the template.
MACOS_DEPLOYMENT_TARGET="12.0"
FLUTTER_MACOS_DIR="build/flutter/macos"

patch_deployment_target() {
    local podfile="$FLUTTER_MACOS_DIR/Podfile"
    local pbxproj="$FLUTTER_MACOS_DIR/Runner.xcodeproj/project.pbxproj"
    [[ -f "$podfile" && -f "$pbxproj" ]] || return 1

    sed -i '' -E "s/^platform :osx, '[0-9.]+'/platform :osx, '$MACOS_DEPLOYMENT_TARGET'/" "$podfile"
    sed -i '' -E "s/MACOSX_DEPLOYMENT_TARGET = [0-9.]+;/MACOSX_DEPLOYMENT_TARGET = $MACOS_DEPLOYMENT_TARGET;/" "$pbxproj"
    # Pods keep their own podspec's target regardless of the Podfile's `platform`, so force it.
    if ! grep -q "build_settings\['MACOSX_DEPLOYMENT_TARGET'\]" "$podfile"; then
        perl -0pi -e "s/^(\s*)(flutter_additional_macos_build_settings\(target\)\n)/\$1\$2\$1target.build_configurations.each { |config| config.build_settings['MACOSX_DEPLOYMENT_TARGET'] = '$MACOS_DEPLOYMENT_TARGET' }\n/m" "$podfile"
    fi
}

patch_deployment_target || true
if ! uv run flet build macos; then
    echo "Build failed - re-applying the macOS $MACOS_DEPLOYMENT_TARGET deployment target and retrying"
    patch_deployment_target
    uv run flet build macos
fi

echo "Creating DMG"
uv run --with dmgbuild dmgbuild -s dmg_settings.py "Financial Tracker" "Financial Tracker.dmg"
