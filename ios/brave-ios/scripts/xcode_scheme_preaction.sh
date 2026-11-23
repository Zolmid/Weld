# Copyright (c) 2024 The Brave Authors. All rights reserved.
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at https://mozilla.org/MPL/2.0/.

# This script is run by Xcode and assumes Xcode build settings are injected
# into the environment.

# $ACTION is empty for Xcode builds unfortunately
# $RUN_CLANG_STATIC_ANALYZER is NO for builds, YES for cleans
if [[ $RUN_CLANG_STATIC_ANALYZER = "NO" ]]; then
  # Do not inject Xcode build configs into the GN build
  env -i PATH="$PATH" BRAVE_IOS_PREBUILT_CORE_DIR="${BRAVE_IOS_PREBUILT_CORE_DIR:-}" \
    BRAVE_IOS_SLIM="${BRAVE_IOS_SLIM:-0}" BRAVE_IOS_REQUIRE_SELECTED_CORE=1 python3 \
    "${PROJECT_DIR}/../scripts/scheme_preaction.py" \
    --platform_name "$PLATFORM_NAME" \
    "$@"
fi
